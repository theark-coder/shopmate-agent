
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from shopmate_agent.embedding_index import (
    ROOT,
    META_FILE,
    VECTOR_FILE,
    normalize,
)


DATASET_FILE = ROOT / "data" / "eval" / "tasks.json"
ALLOWED_TOOLS = {
    "none",
    "search_products",
    "get_price_stock",
    "get_order_status",
    "get_return_eligibility",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics_at_k(retrieved_ids, relevant_ids, k=3):
    if k < 1 or not relevant_ids:
        raise ValueError("Invalid evaluation labels or k")

    found = set(retrieved_ids[:k])
    relevant = set(relevant_ids)

    return {
        "hit": int(bool(found & relevant)),
        "recall": len(found & relevant) / len(relevant),
    }


def validate_dataset(tasks, available_doc_ids):
    if len(tasks) != 60:
        raise ValueError("Expected 60 tasks")

    splits = Counter(task["split"] for task in tasks)
    if splits != {"dev": 40, "test": 20}:
        raise ValueError("Expected a fixed 40/20 split")

    ids = [task["id"] for task in tasks]
    queries = [task["query"].strip() for task in tasks]

    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate task ID")

    if len(set(queries)) != len(queries):
        raise ValueError("Duplicate query")

    for task in tasks:
        if task["category"] not in {
            "shopping", "order", "aftersales"
        }:
            raise ValueError("Invalid task category")

        if task["expected_tool"] not in ALLOWED_TOOLS:
            raise ValueError("Invalid expected tool")

        relevant = task["relevant_doc_ids"]

        if not relevant or not set(relevant) <= available_doc_ids:
            raise ValueError(
                f"Invalid relevance labels: {task['id']}"
            )

        expected_policies = {
            doc for doc in relevant
            if doc.startswith("policy-")
        }

        if set(task["relevant_policy_ids"]) != expected_policies:
            raise ValueError(
                f"Invalid policy labels: {task['id']}"
            )

    return True


def evaluate(split: str, top_k: int = 3):
    if top_k < 1:
        raise ValueError("top_k must be positive")

    from sentence_transformers import SentenceTransformer

    dataset = json.loads(
        DATASET_FILE.read_text(encoding="utf-8")
    )
    metadata = json.loads(
        META_FILE.read_text(encoding="utf-8")
    )

    with np.load(VECTOR_FILE, allow_pickle=False) as data:
        vectors = data["vectors"]

    chunks = metadata["chunks"]

    if vectors.shape != (
        len(chunks), metadata["dimension"]
    ):
        raise ValueError("Index and metadata mismatch")

    available_ids = {chunk["doc_id"] for chunk in chunks}

    validate_dataset(
        dataset["tasks"],
        available_ids,
    )

    selected = [
        task for task in dataset["tasks"]
        if task["split"] == split
    ]

    encoder = SentenceTransformer(
        metadata["model_id"],
        revision=metadata["model_revision"],
        device="cpu",
    )

    prompts = [
        metadata["query_prefix"] + task["query"]
        for task in selected
    ]

    # 批量编码查询，复用 Day 13 的归一化方法
    query_vectors = normalize(
        encoder.encode(
            prompts,
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
    )

    if vectors.shape[1] != query_vectors.shape[1]:
        raise ValueError("Embedding dimension mismatch")

    records = []

    for task, query_vector in zip(selected, query_vectors):
        scores = vectors @ query_vector
        indices = np.argsort(-scores, kind="stable")[:top_k]

        retrieved = [
            {
                "doc_id": chunks[int(i)]["doc_id"],
                "chunk_id": chunks[int(i)]["chunk_id"],
                "source_path": chunks[int(i)]["source_path"],
                "version": chunks[int(i)]["version"],
                "score": round(float(scores[i]), 4),
            }
            for i in indices
        ]

        metrics = metrics_at_k(
            [item["doc_id"] for item in retrieved],
            task["relevant_doc_ids"],
            top_k,
        )

        records.append({
            "task_id": task["id"],
            "category": task["category"],
            "query": task["query"],
            "expected_tool": task["expected_tool"],
            "relevant_doc_ids": task["relevant_doc_ids"],
            "retrieved": retrieved,
            **metrics,
        })

    total = len(records)

    summary = {
        "count": total,
        "hit_at_3": sum(r["hit"] for r in records) / total,
        "recall_at_3": sum(r["recall"] for r in records) / total,
        "by_category": {},
    }

    for category in ("shopping", "order", "aftersales"):
        group = [
            r for r in records
            if r["category"] == category
        ]
        if group:
            summary["by_category"][category] = {
                "count": len(group),
                "hit_at_3": sum(r["hit"] for r in group) / len(group),
                "recall_at_3": sum(r["recall"] for r in group) / len(group),
            }

    result = {
        "dataset_version": dataset["dataset_version"],
        "dataset_sha256": sha256_file(DATASET_FILE),
        "index_sha256": sha256_file(VECTOR_FILE),
        "index_metadata_sha256": sha256_file(META_FILE),
        "model_id": metadata["model_id"],
        "model_revision": metadata["model_revision"],
        "split": split,
        "top_k": top_k,
        "summary": summary,
        "records": records,
    }

    output = ROOT / "data" / "eval" / f"baseline_{split}.json"

    output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print(f"Split: {split}")
    print(f"Queries: {total}")
    print(f"Hit@3: {summary['hit_at_3']:.3f}")
    print(f"Recall@3: {summary['recall_at_3']:.3f}")
    print("Model revision:", metadata["model_revision"])
    print("Saved:", output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
    )

    args = parser.parse_args()
    evaluate(args.split)


if __name__ == "__main__":
    main()
