
import numpy as np
import pytest

from shopmate_agent.embedding_index import (
    normalize,
    search,
)


class FakeEncoder:
    def encode(self, texts, **kwargs):
        return np.asarray(
            [
                [2.0, 0.0] if "退货" in text
                else [0.0, 3.0]
                for text in texts
            ],
            dtype=np.float32,
        )


def test_l2_normalization():
    vectors = normalize([[3, 4], [0, 2]])

    assert np.allclose(
        np.linalg.norm(vectors, axis=1),
        [1.0, 1.0],
    )


def test_cosine_retrieval_order():
    vectors = normalize([[2, 0], [0, 3]])

    chunks = [
        {"doc_id": "policy-returns", "text": "退货政策"},
        {"doc_id": "policy-shipping", "text": "配送政策"},
    ]

    results = search(
        FakeEncoder(),
        vectors,
        chunks,
        "退货有什么要求？",
        top_k=2,
    )

    assert results[0]["doc_id"] == "policy-returns"
    assert results[0]["score"] == pytest.approx(1.0)
    assert results[1]["score"] == pytest.approx(0.0)


def test_dimension_mismatch():
    vectors = np.asarray([[1, 0, 0]], dtype=np.float32)
    chunks = [{"doc_id": "test"}]

    with pytest.raises(ValueError, match="dimension"):
        search(
            FakeEncoder(),
            vectors,
            chunks,
            "退货",
        )


def test_zero_vector_rejected():
    with pytest.raises(ValueError, match="Zero"):
        normalize([[0, 0]])

