
import numpy as np


def project_qkv(x, w_q, w_k, w_v):
    """从输入 X 计算 Q、K、V。"""
    x = np.asarray(x, dtype=np.float64)
    w_q = np.asarray(w_q, dtype=np.float64)
    w_k = np.asarray(w_k, dtype=np.float64)
    w_v = np.asarray(w_v, dtype=np.float64)

    if any(a.ndim != 2 for a in (x, w_q, w_k, w_v)):
        raise ValueError("All inputs must be 2D matrices")

    d_model = x.shape[1]

    if any(w.shape[0] != d_model for w in (w_q, w_k, w_v)):
        raise ValueError("Projection dimension mismatch")

    if w_q.shape[1] != w_k.shape[1]:
        raise ValueError("Q and K dimensions must match")

    return x @ w_q, x @ w_k, x @ w_v


def scaled_dot_product_attention(q, k, v, causal=True):
    """返回 Attention 输出与权重矩阵。"""
    q = np.asarray(q, dtype=np.float64)
    k = np.asarray(k, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)

    if any(a.ndim != 2 for a in (q, k, v)):
        raise ValueError("Q, K, V must be 2D")

    if not all(
        a.shape[0] > 0 and a.shape[1] > 0
        for a in (q, k, v)
    ):
        raise ValueError("Empty Q, K or V")

    if q.shape[1] != k.shape[1]:
        raise ValueError("Q/K dimension mismatch")

    if k.shape[0] != v.shape[0]:
        raise ValueError("K/V sequence length mismatch")

    if causal and q.shape[0] != k.shape[0]:
        raise ValueError("Causal demo requires self-attention")

    if not all(np.isfinite(a).all() for a in (q, k, v)):
        raise ValueError("Non-finite input")

    d_k = q.shape[1]

    # 1. 缩放点积
    scores = (q @ k.T) / np.sqrt(d_k)

    # 2. 屏蔽未来 Token
    if causal:
        future_mask = np.triu(
            np.ones(scores.shape, dtype=bool),
            k=1,
        )
        scores = np.where(future_mask, -np.inf, scores)

    # 3. 数值稳定版 Softmax
    shifted = scores - np.max(
        scores, axis=-1, keepdims=True
    )

    exp_scores = np.exp(shifted)

    weights = exp_scores / np.sum(
        exp_scores, axis=-1, keepdims=True
    )

    # 4. 汇总 Value
    output = weights @ v

    return output, weights


def main():
    # 3 个 Token，每个 Token 的输入维度为 4
    x = np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
    ])

    w_q = np.array([
        [1, 0],
        [0, 1],
        [1, 1],
        [0, 0],
    ])

    w_k = w_q.copy()

    w_v = np.array([
        [2, 0],
        [0, 3],
        [4, 5],
        [0, 0],
    ])

    q, k, v = project_qkv(x, w_q, w_k, w_v)

    output, weights = scaled_dot_product_attention(
        q, k, v, causal=True
    )

    print("X shape:", x.shape)
    print("Q shape:", q.shape)
    print("K shape:", k.shape)
    print("V shape:", v.shape)

    print("Attention weights:")
    print(np.round(weights, 4))

    print("Output shape:", output.shape)
    print("Output:")
    print(np.round(output, 4))

    print("Row sums:", weights.sum(axis=-1))


if __name__ == "__main__":
    main()
