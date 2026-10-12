
import numpy as np
import pytest

from shopmate_agent.attention_numpy import (
    project_qkv,
    scaled_dot_product_attention,
)


def test_qkv_shapes():
    x = np.ones((3, 4))
    w_q = np.ones((4, 2))
    w_k = np.ones((4, 2))
    w_v = np.ones((4, 3))

    q, k, v = project_qkv(x, w_q, w_k, w_v)

    assert q.shape == (3, 2)
    assert k.shape == (3, 2)
    assert v.shape == (3, 3)


def test_causal_mask_and_row_sums():
    q = np.zeros((3, 2))
    k = np.zeros((3, 2))
    v = np.array([[1, 0], [0, 2], [3, 4]])

    output, weights = scaled_dot_product_attention(
        q, k, v, causal=True
    )

    assert weights.shape == (3, 3)
    assert output.shape == (3, 2)

    # 每行 Attention 权重之和必须为 1
    assert np.allclose(weights.sum(axis=1), 1.0)

    # 未来位置的权重必须严格为 0
    assert np.all(
        weights[np.triu_indices(3, k=1)] == 0
    )

    # 第一个 Token 只能看到自己的 Value
    assert np.allclose(output[0], v[0])


def test_without_mask_can_see_future():
    q = np.zeros((3, 2))
    k = np.zeros((3, 2))
    v = np.array([[1.0], [2.0], [3.0]])

    output, weights = scaled_dot_product_attention(
        q, k, v, causal=False
    )

    assert np.allclose(
        weights,
        np.full((3, 3), 1 / 3),
    )
    assert np.allclose(output[:, 0], 2.0)


def test_scaled_softmax_values():
    q = np.eye(2)
    k = np.eye(2)
    v = np.eye(2)

    _, weights = scaled_dot_product_attention(
        q, k, v, causal=False
    )

    expected = np.exp(1 / np.sqrt(2))
    expected_probability = expected / (expected + 1)

    assert weights[0, 0] == pytest.approx(
        expected_probability
    )
    assert np.allclose(weights.sum(axis=1), 1)


def test_invalid_qk_dimension():
    q = np.ones((2, 3))
    k = np.ones((2, 2))
    v = np.ones((2, 2))

    with pytest.raises(ValueError, match="Q/K"):
        scaled_dot_product_attention(q, k, v)
