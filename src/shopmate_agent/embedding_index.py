
import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from shopmate_agent.chunking import chunk_directory


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "data" / "knowledge"
INDEX_DIR = ROOT / "data" / "index"
VECTOR_FILE = INDEX_DIR / "chunks.npz"
META_FILE = INDEX_DIR / "chunks_meta.json"

MODEL_ID = "BAAI/bge-small-zh-v1.5"
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def normalize(vectors):
    arr = np.asarray(vectors, dtype=np.float32)

    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    if arr.ndim != 2 or not np.isfinite(arr).all():
        raise ValueError("Invalid embedding vectors")

    norms = np.linalg.norm(arr, axis=1, keepdims=True)

    if np.any(norms == 0):
        raise ValueError("Zero embedding vector")

    return arr / norms


def search(encoder, vectors, chunks, query, top_k=3):
    if top_k < 1:
        raise ValueError("top_k must be positive")

    if len(vectors) != len(chunks):
        raise ValueError("Index and metadata count mismatch")

    query_vector = normalize(
        encoder.encode(
            [QUERY_PREFIX + query],
            normalize_embeddings=True,
        )
    )[0]

    if vectors.shape[1] != len(query_vector):
        raise ValueError("Embedding dimension mismatch")

    scores = vectors @ query_vector
    indices = np.argsort(-scores, kind="stable")[:top_k]

    return [
        {
            **chunks[int(i)],
            "score": round(float(scores[i]), 4),
        }
        for i in indices
    ]


def build_index():
    # 大模型依赖只在真正构建时导入
    from huggingface_hub import HfApi
    from sentence_transformers import SentenceTransformer

    chunks = chunk_directory(
        KNOWLEDGE,
        max_chars=300,
        overlap=40,
    )

    if not chunks:
        raise RuntimeError("No knowledge chunks found")

    # 获取模型仓库的真实提交版本
    revision = HfApi().model_info(MODEL_ID).sha

    encoder = SentenceTransformer(
        MODEL_ID,
        revision=revision,
        device="cpu",
    )

    vectors = normalize(
        encoder.encode(
            [chunk.text for chunk in chunks],
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
    )

    documents = []

    for chunk in chunks:
        item = asdict(chunk)

        # 记录相对于项目根目录的路径，便于克隆后复现
        item["source_path"] = (
            Path(item["source_path"])
            .relative_to(ROOT)
            .as_posix()
        )

        documents.append(item)

    metadata = {
        "model_id": MODEL_ID,
        "model_revision": revision,
        "dimension": int(vectors.shape[1]),
        "normalized": True,
        "max_chars": 300,
        "overlap": 40,
        "query_prefix": QUERY_PREFIX,
        "chunks": documents,
    }

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(VECTOR_FILE, vectors=vectors)

    META_FILE.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Model:", MODEL_ID)
    print("Model revision:", revision)
    print("Chunks:", len(chunks))
    print("Vector shape:", vectors.shape)
    print("Index saved:", VECTOR_FILE)


QUERIES = [
    ("蓝牙耳机支持主动降噪吗？", {"P001-description", "P001-faq"}),
    ("机械键盘支持热插拔吗？", {"P002-description", "P002-faq"}),
    ("无线鼠标有什么连接方式？", {"P003-description", "P003-faq"}),
    ("便携显示器的分辨率是多少？", {"P004-description", "P004-faq"}),
    ("移动固态硬盘容量是多少？", {"P006-description", "P006-faq"}),
    ("笔记本支架可以调节几档？", {"P007-description", "P007-faq"}),
    ("付款后什么时候发货？", {"FAQ001", "policy-shipping"}),
    ("签收七天内退货有什么条件？", {"policy-returns"}),
    ("可以申请电子发票吗？", {"FAQ004", "policy-invoice"}),
    ("如何申请商品保修？", {"FAQ005", "policy-warranty"}),
]


def evaluate_index():
    from sentence_transformers import SentenceTransformer

    metadata = json.loads(
        META_FILE.read_text(encoding="utf-8")
    )

    with np.load(VECTOR_FILE, allow_pickle=False) as data:
        vectors = data["vectors"]

    if vectors.shape != (
        len(metadata["chunks"]),
        metadata["dimension"],
    ):
        raise ValueError("Saved index shape mismatch")

    encoder = SentenceTransformer(
        metadata["model_id"],
        revision=metadata["model_revision"],
        device="cpu",
    )

    print("Model:", metadata["model_id"])
    print("Revision:", metadata["model_revision"])

    hits = 0

    for number, (query, expected_ids) in enumerate(QUERIES, 1):
        results = search(
            encoder,
            vectors,
            metadata["chunks"],
            query,
            top_k=3,
        )

        matched = any(
            item["doc_id"] in expected_ids
            for item in results
        )

        hits += int(matched)

        print(f"\nQuery {number}: {query}")
        print("Hit@3:", matched)

        for item in results:
            print(
                f"  score={item['score']:.4f}",
                f"doc_id={item['doc_id']}",
                f"version={item['version']}",
                f"source={item['source']}",
                f"path={item['source_path']}",
                f"chunk={item['chunk_id']}",
            )
            print("  text:", item["text"][:100].strip())

    print(f"\nBaseline Hit@3: {hits}/{len(QUERIES)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "eval"])
    args = parser.parse_args()

    if args.command == "build":
        build_index()
    else:
        evaluate_index()


if __name__ == "__main__":
    main()
