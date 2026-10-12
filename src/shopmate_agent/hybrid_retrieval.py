
import json
import re
import time
from pathlib import Path

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from shopmate_agent.embedding_index import (
    ROOT,
    META_FILE,
    VECTOR_FILE,
    normalize,
)
from shopmate_agent.retrieval_eval import (
    DATASET_FILE,
    metrics_at_k,
    sha256_file,
    validate_dataset,
)


BASELINE_FILE = ROOT / "data/eval/baseline_dev.json"
OUTPUT_FILE = ROOT / "data/eval/hybrid_dev.json"

TOP_K = 3
CANDIDATE_K = 15
RRF_K = 60


def tokenize(text: str) -> list[str]:
    """文档与查询采用相同的中文分词规则。"""
    words = jieba.lcut_for_search(text.lower(), HMM=False)

    return [
        word.strip()
        for word in words
        if re.search(r"[\u4e00-\u9fffA-Za-z0-9]", word)
    ]


def sparse_ranking(bm25, query, limit=15):
    scores = bm25.get_scores(tokenize(query))

    # 没有关键词匹配证据的文档不进入稀疏候选
    indices = [
        i for i, score in enumerate(scores)
        if score > 0
    ]

    indices.sort(key=lambda i: (-float(scores[i]), i))
    return indices[:limit]


def rrf_fuse(rankings, k=60):
    """输入多个文档索引排名，返回融合后的索引和分数。"""
    if k <= 0:
        raise ValueError("RRF k must be positive")

    scores = {}

    for ranking in rankings:
        for rank, doc_index in enumerate(
            dict.fromkeys(ranking), start=1
        ):
            scores[doc_index] = (
                scores.get(doc_index, 0.0)
                + 1.0 / (k + rank)
            )

    return sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0]),
    )


def summarize(records, method):
    count = len(records)

    return {
        "hit_at_3": sum(
            row[method]["hit"] for row in records
        ) / count,
        "recall_at_3": sum(
            row[method]["recall"] for row in records
        ) / count,
        "avg_latency_ms": round(
            sum(row[method]["latency_ms"] for row in records)
            / count,
            2,
        ),
    }


def evaluate_hybrid():
    from sentence_transformers import SentenceTransformer

    dataset = json.loads(
        DATASET_FILE.read_text(encoding="utf-8")
    )
    metadata = json.loads(
        META_FILE.read_text(encoding="utf-8")
    )
    baseline = json.loads(
        BASELINE_FILE.read_text(encoding="utf-8")
    )

    with np.load(VECTOR_FILE, allow_pickle=False) as data:
        vectors = data["vectors"]

    chunks = metadata["chunks"]

    if vectors.shape != (
        len(chunks), metadata["dimension"]
    ):
        raise ValueError("Index metadata mismatch")

    validate_dataset(
        dataset["tasks"],
        {chunk["doc_id"] for chunk in chunks},
    )

    # 固定数据集与索引，确保比较条件一致
    if baseline["dataset_sha256"] != sha256_file(DATASET_FILE):
        raise ValueError("Dataset changed since Day 14")

    if baseline["index_sha256"] != sha256_file(VECTOR_FILE):
        raise ValueError("Vector index changed since Day 14")

    if baseline["index_metadata_sha256"] != sha256_file(META_FILE):
        raise ValueError("Index metadata changed since Day 14")

    if baseline["model_revision"] != metadata["model_revision"]:
        raise ValueError("Model revision changed")

    tasks = [
        task for task in dataset["tasks"]
        if task["split"] == "dev"
    ]

    # 建立 BM25 索引
    started = time.perf_counter()
    corpus = [tokenize(chunk["text"]) for chunk in chunks]
    bm25 = BM25Okapi(corpus)
    bm25_build_ms = (
        time.perf_counter() - started
    ) * 1000

    encoder = SentenceTransformer(
        metadata["model_id"],
        revision=metadata["model_revision"],
        device="cpu",
    )

    baseline_records = {
        row["task_id"]: row
        for row in baseline["records"]
    }

    records = []

    for task in tasks:
        t0 = time.perf_counter()

        query_vector = normalize(
            encoder.encode(
                [metadata["query_prefix"] + task["query"]],
                normalize_embeddings=True,
            )
        )[0]

        dense_scores = vectors @ query_vector

        dense_order = np.argsort(
            -dense_scores,
            kind="stable",
        ).tolist()

        dense_ms = (time.perf_counter() - t0) * 1000

        # 用 Day 14 的固定结果校验纯向量结果
        expected = [
            item["doc_id"]
            for item in baseline_records[task["id"]]["retrieved"]
        ]
        actual = [
            chunks[i]["doc_id"]
            for i in dense_order[:TOP_K]
        ]

        if actual != expected:
            raise ValueError(
                f"Dense baseline changed: {task['id']}"
            )

        sparse_order = sparse_ranking(
            bm25, task["query"], CANDIDATE_K
        )

        fused = rrf_fuse(
            [
                dense_order[:CANDIDATE_K],
                sparse_order,
            ],
            k=RRF_K,
        )

        hybrid_order = [
            index for index, _ in fused[:TOP_K]
        ]

        hybrid_ms = (time.perf_counter() - t0) * 1000

        relevant = task["relevant_doc_ids"]

        dense_metrics = metrics_at_k(
            actual, relevant, TOP_K
        )
        hybrid_ids = [
            chunks[i]["doc_id"]
            for i in hybrid_order
        ]
        hybrid_metrics = metrics_at_k(
            hybrid_ids, relevant, TOP_K
        )

        records.append({
            "task_id": task["id"],
            "query": task["query"],
            "category": task["category"],
            "relevant_doc_ids": relevant,
            "dense": {
                **dense_metrics,
                "doc_ids": actual,
                "latency_ms": round(dense_ms, 2),
            },
            "hybrid": {
                **hybrid_metrics,
                "doc_ids": hybrid_ids,
                "latency_ms": round(hybrid_ms, 2),
            },
            "bm25_doc_ids": [
                chunks[i]["doc_id"]
                for i in sparse_order[:TOP_K]
            ],
            "delta_recall": round(
                hybrid_metrics["recall"]
                - dense_metrics["recall"],
                4,
            ),
        })

    improved = [
        row for row in records
        if row["delta_recall"] > 0
    ]
    regressed = [
        row for row in records
        if row["delta_recall"] < 0
    ]

    result = {
        "split": "dev",
        "dataset_sha256": sha256_file(DATASET_FILE),
        "model_id": metadata["model_id"],
        "model_revision": metadata["model_revision"],
        "index_sha256": sha256_file(VECTOR_FILE),
        "bm25_build_ms": round(bm25_build_ms, 2),
        "rrf_k": RRF_K,
        "candidate_k": CANDIDATE_K,
        "dense_summary": summarize(records, "dense"),
        "hybrid_summary": summarize(records, "hybrid"),
        "improved_task_ids": [
            row["task_id"] for row in improved
        ],
        "regressed_task_ids": [
            row["task_id"] for row in regressed
        ],
        "records": records,
    }

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Dense:", result["dense_summary"])
    print("Hybrid:", result["hybrid_summary"])
    print("BM25 build ms:", result["bm25_build_ms"])
    print("Improved tasks:", result["improved_task_ids"])
    print("Regressed tasks:", result["regressed_task_ids"])
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    evaluate_hybrid()
