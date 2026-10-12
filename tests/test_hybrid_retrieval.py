
from rank_bm25 import BM25Okapi

from shopmate_agent.hybrid_retrieval import (
    tokenize,
    sparse_ranking,
    rrf_fuse,
)
from shopmate_agent.retrieval_eval import metrics_at_k


def test_chinese_tokenization():
    tokens = tokenize("蓝牙降噪耳机支持什么功能？")

    assert tokens
    assert any("耳机" in token for token in tokens)


def test_bm25_matches_keywords():
    documents = [
        "蓝牙降噪耳机支持主动降噪",
        "机械键盘支持热插拔",
        "无线鼠标支持静音按键",
    ]

    bm25 = BM25Okapi(
        [tokenize(text) for text in documents]
    )

    ranking = sparse_ranking(
        bm25, "机械键盘热插拔", limit=3
    )

    assert ranking[0] == 1


def test_rrf_rewards_multiple_rankings():
    fused = rrf_fuse(
        [
            [0, 1, 2],
            [1, 3],
        ],
        k=60,
    )

    # 文档1同时出现在两份排名中
    assert fused[0][0] == 1


def test_rrf_does_not_double_count_duplicates():
    fused = rrf_fuse(
        [[0, 0, 1]],
        k=60,
    )

    assert [item[0] for item in fused] == [0, 1]


def test_recall_metric_can_detect_regression():
    relevant = ["policy-returns", "FAQ003"]

    old = metrics_at_k(
        ["policy-returns", "FAQ003"],
        relevant,
        k=2,
    )
    new = metrics_at_k(
        ["FAQ001", "policy-returns"],
        relevant,
        k=2,
    )

    assert old["recall"] == 1.0
    assert new["recall"] == 0.5
