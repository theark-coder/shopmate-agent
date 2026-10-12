
import argparse
import json
import time

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from shopmate_agent.embedding_index import (
    ROOT, META_FILE, VECTOR_FILE, normalize,
)
from shopmate_agent.hybrid_retrieval import (
    CANDIDATE_K, RRF_K, rrf_fuse,
    sparse_ranking, tokenize,
)
from shopmate_agent.retrieval_eval import (
    DATASET_FILE, metrics_at_k, sha256_file,
    validate_dataset,
)
from shopmate_agent.reranker import (
    MODEL_ID, load_reranker, rerank_candidates,
)


BASELINE = ROOT / "data/eval/hybrid_dev.json"
OUTPUT = ROOT / "data/eval/rerank_dev.json"


def average(records, method, field):
    return sum(row[method][field] for row in records) / len(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rerank", choices=["on", "off"], default="on")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--candidate-k", type=int, default=10)
    args = parser.parse_args()

    if args.candidate_k < 3 or args.candidate_k > CANDIDATE_K:
        raise ValueError("candidate-k must be between 3 and 15")

    dataset = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    previous = json.loads(BASELINE.read_text(encoding="utf-8"))

    with np.load(VECTOR_FILE, allow_pickle=False) as data:
        vectors = data["vectors"]

    chunks = meta["chunks"]
    texts = [chunk["text"] for chunk in chunks]

    if vectors.shape != (len(chunks), meta["dimension"]):
        raise ValueError("Index shape mismatch")

    validate_dataset(
        dataset["tasks"],
        {chunk["doc_id"] for chunk in chunks},
    )

    if previous["dataset_sha256"] != sha256_file(DATASET_FILE):
        raise ValueError("Dataset changed")

    if previous["index_sha256"] != sha256_file(VECTOR_FILE):
        raise ValueError("Vector index changed")

    if previous["model_revision"] != meta["model_revision"]:
        raise ValueError("Embedding model changed")

    encoder = SentenceTransformer(
        meta["model_id"],
        revision=meta["model_revision"],
        device="cpu",
    )

    corpus = [tokenize(text) for text in texts]
    bm25 = BM25Okapi(corpus)

    reranker = load_reranker() if args.rerank == "on" else None

    tasks = [t for t in dataset["tasks"] if t["split"] == "dev"]
    old_records = {
        row["task_id"]: row for row in previous["records"]
    }

    records = []

    for task in tasks:
        t0 = time.perf_counter()

        q = normalize(
            encoder.encode(
                [meta["query_prefix"] + task["query"]],
                normalize_embeddings=True,
            )
        )[0]

        dense_scores = vectors @ q
        dense_order = np.argsort(
            -dense_scores, kind="stable"
        ).tolist()

        sparse_order = sparse_ranking(
            bm25, task["query"], CANDIDATE_K
        )

        fused = rrf_fuse(
            [dense_order[:CANDIDATE_K], sparse_order],
            k=RRF_K,
        )

        hybrid_candidates = [
            i for i, _ in fused[:args.candidate_k]
        ]
        hybrid_top3 = hybrid_candidates[:3]

        expected = old_records[task["id"]]["hybrid"]["doc_ids"]
        actual = [chunks[i]["doc_id"] for i in hybrid_top3]

        if actual != expected:
            raise ValueError(
                f"Hybrid baseline changed: {task['id']}"
            )

        retrieval_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()

        if reranker is None:
            selected = hybrid_top3
            status = "DISABLED"
        else:
            rerank_result = rerank_candidates(
                task["query"],
                hybrid_candidates,
                texts,
                reranker,
                top_k=3,
                timeout_seconds=args.timeout,
            )
            selected = rerank_result.indices
            status = rerank_result.status

        rerank_ms = (time.perf_counter() - t1) * 1000

        rerank_ids = [chunks[i]["doc_id"] for i in selected]

        relevant = task["relevant_doc_ids"]

        dense = old_records[task["id"]]["dense"]
        hybrid = old_records[task["id"]]["hybrid"]
        measured = metrics_at_k(rerank_ids, relevant, 3)

        records.append({
            "task_id": task["id"],
            "query": task["query"],
            "relevant_doc_ids": relevant,
            "dense": {
                "doc_ids": dense["doc_ids"],
                "hit": dense["hit"],
                "recall": dense["recall"],
            },
            "hybrid": {
                "doc_ids": hybrid["doc_ids"],
                "hit": hybrid["hit"],
                "recall": hybrid["recall"],
            },
            "rerank": {
                "doc_ids": rerank_ids,
                "hit": measured["hit"],
                "recall": measured["recall"],
                "status": status,
                "retrieval_ms": round(retrieval_ms, 2),
                "rerank_ms": round(rerank_ms, 2),
            },
        })

    summary = {}

    for method in ("dense", "hybrid", "rerank"):
        summary[method] = {
            "hit_at_3": average(records, method, "hit"),
            "recall_at_3": average(records, method, "recall"),
        }

    summary["rerank"]["avg_rerank_ms"] = round(
        average(records, "rerank", "rerank_ms"), 2
    )
    summary["rerank"]["avg_retrieval_ms"] = round(
        average(records, "rerank", "retrieval_ms"), 2
    )

    result = {
        "split": "dev",
        "dataset_sha256": sha256_file(DATASET_FILE),
        "index_sha256": sha256_file(VECTOR_FILE),
        "embedding_model": meta["model_id"],
        "embedding_revision": meta["model_revision"],
        "reranker_model": MODEL_ID if reranker else None,
        "rerank_enabled": bool(reranker),
        "candidate_k": args.candidate_k,
        "top_k": 3,
        "summary": summary,
        "records": records,
    }

    target = (
        OUTPUT if reranker
        else ROOT / "data/eval/rerank_off_dev.json"
    )

    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Saved:", target)


if __name__ == "__main__":
    main()
