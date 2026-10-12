
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any

import numpy as np


MODEL_ID = "BAAI/bge-reranker-base"


@dataclass
class RerankResult:
    indices: list[int]
    status: str
    scores: list[float] | None = None


def rerank_candidates(
    query: str,
    candidates: list[int],
    texts: list[str],
    model: Any,
    top_k: int = 3,
    timeout_seconds: float = 30.0,
) -> RerankResult:
    """按 CrossEncoder 得分重排，出错则回退候选原顺序。"""
    if top_k < 1 or timeout_seconds <= 0:
        raise ValueError("Invalid rerank settings")

    if any(i < 0 or i >= len(texts) for i in candidates):
        raise ValueError("Candidate index out of range")

    fallback = candidates[:top_k]

    if not candidates:
        return RerankResult([], "EMPTY")

    pairs = [(query, texts[i]) for i in candidates]

    executor = ThreadPoolExecutor(max_workers=1)

    try:
        future = executor.submit(
            model.predict,
            pairs,
            batch_size=8,
            show_progress_bar=False,
        )

        raw = future.result(timeout=timeout_seconds)
        scores = np.asarray(raw, dtype=np.float64).reshape(-1)

        if len(scores) != len(candidates):
            raise ValueError("Reranker score count mismatch")

        if not np.isfinite(scores).all():
            raise ValueError("Non-finite reranker score")

        order = sorted(
            range(len(candidates)),
            key=lambda pos: (-scores[pos], pos),
        )

        return RerankResult(
            indices=[candidates[i] for i in order[:top_k]],
            status="RERANKED",
            scores=[round(float(scores[i]), 4) for i in order[:top_k]],
        )

    except TimeoutError:
        return RerankResult(fallback, "FALLBACK_TIMEOUT")
    except Exception:
        return RerankResult(fallback, "FALLBACK_ERROR")
    finally:
        # 不让等待中的主流程被阻塞；
        # 已开始的模型推理线程可能仍继续运行。
        executor.shutdown(wait=False, cancel_futures=True)


def load_reranker(model_id: str = MODEL_ID):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(
        model_id,
        device="cpu",
        max_length=512,
    )
