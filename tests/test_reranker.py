
import time

from shopmate_agent.reranker import rerank_candidates


TEXTS = ["耳机", "退货政策", "机械键盘"]


class FakeReranker:
    def predict(self, pairs, **kwargs):
        return [0.1, 0.9, 0.3]


class BrokenReranker:
    def predict(self, pairs, **kwargs):
        raise RuntimeError("Model error")


class SlowReranker:
    def predict(self, pairs, **kwargs):
        time.sleep(0.2)
        return [0.1, 0.9, 0.3]


def test_rerank_order():
    result = rerank_candidates(
        "退货", [0, 1, 2], TEXTS,
        FakeReranker(), top_k=3,
    )

    assert result.status == "RERANKED"
    assert result.indices == [1, 2, 0]


def test_rerank_disabled_by_candidate_count():
    result = rerank_candidates(
        "退货", [], TEXTS, FakeReranker(),
    )

    assert result.status == "EMPTY"
    assert result.indices == []


def test_model_error_falls_back():
    result = rerank_candidates(
        "退货", [0, 1, 2], TEXTS,
        BrokenReranker(),
    )

    assert result.status == "FALLBACK_ERROR"
    assert result.indices == [0, 1, 2]


def test_timeout_falls_back():
    result = rerank_candidates(
        "退货", [0, 1, 2], TEXTS,
        SlowReranker(),
        timeout_seconds=0.01,
    )

    assert result.status == "FALLBACK_TIMEOUT"
    assert result.indices == [0, 1, 2]
