
import pytest

from shopmate_agent.shopmate_graph import (
    build_graph,
    after_verify,
    product_id,
    order_id,
)


@pytest.fixture(scope="module")
def graph():
    return build_graph()


def test_product_route(graph):
    result = graph.invoke({
        "question": "预算300元以内，推荐商品",
        "user_id": None,
    })

    assert result["intent"] == "product"
    assert "product_tool" in result["trace"]
    assert result["verified"] is True
    assert result["citations"]
    assert "db:products:" in result["citations"][0]


def test_order_route_authorized(graph):
    result = graph.invoke({
        "question": "订单ORD001现在什么状态？",
        "user_id": "demo_user_001",
    })

    assert result["intent"] == "order"
    assert "order_tool" in result["trace"]
    assert "shipped" in result["answer"]
    assert result["verified"] is True


def test_order_cannot_leak_to_other_user(graph):
    result = graph.invoke({
        "question": "订单ORD001现在什么状态？",
        "user_id": "other_user",
    })

    assert "shipped" not in result["answer"]
    assert result["citations"] == []
    assert result["verified"] is True


def test_policy_route_with_citation(graph):
    result = graph.invoke({
        "question": "七天退货有什么条件？",
        "user_id": None,
    })

    assert result["intent"] == "policy"
    assert "policy-returns" in result["citations"]
    assert result["verified"] is True
    assert "verify:pass" in result["trace"]


def test_unknown_question_asks_clarification(graph):
    result = graph.invoke({
        "question": "你好",
        "user_id": None,
    })

    assert result["intent"] == "clarify"
    assert result["verified"] is True
    assert result["citations"] == []


def test_id_patterns_support_adjacent_chinese():
    assert product_id("商品P001多少钱") == "P001"
    assert order_id("订单ORD001状态") == "ORD001"
    assert product_id("P001ABC") is None


def test_verification_retry_is_bounded():
    state = {"verified": False, "retries": 0}
    assert after_verify(state) == "retry"

    state["retries"] = 1
    assert after_verify(state) == "safe_end"

    state["verified"] = True
    assert after_verify(state) == "done"
