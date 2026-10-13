
from shopmate_agent.answer_quality import (
    reply_to_customer,
    rewrite_query,
)


def test_query_rewrite_uses_known_product_id():
    rewritten = rewrite_query(
        "它多少钱？",
        ["我正在看商品P001"],
    )

    assert "P001" in rewritten
    assert "多少钱" in rewritten


def test_query_rewrite_does_not_invent_id():
    rewritten = rewrite_query(
        "它多少钱？",
        [],
    )

    assert rewritten == "它多少钱？"


def test_clarification_for_missing_order_id():
    result = reply_to_customer("帮我查一下订单。")

    assert result.status == "CLARIFY"
    assert not result.citations


def test_unsupported_refund_guarantee_is_refused():
    result = reply_to_customer(
        "你能保证给我退款500元吗？"
    )

    assert result.status == "REFUSE_UNSUPPORTED"
    assert "不能保证" in result.answer


def test_policy_exception_requires_human():
    result = reply_to_customer(
        "过了退货期限，有特殊情况能破例吗？"
    )

    assert result.status == "HANDOFF"
    assert "人工" in result.answer


def test_return_policy_has_traceable_citation():
    result = reply_to_customer(
        "七天退货有哪些条件？"
    )

    assert result.status == "ANSWERED"
    assert len(result.citations) == 1

    citation = result.citations[0]

    assert citation["doc_id"] == "policy-returns"
    assert citation["version"] == "1.0"
    assert "data/knowledge/policies/returns.md" in (
        citation["source_path"]
    )
    assert "定制商品" in citation["text"]
    assert "定制商品" in result.answer


def test_order_status_needs_authorized_tool():
    result = reply_to_customer(
        "订单ORD001发货了吗？"
    )

    assert result.status == "NEED_ORDER_TOOL"
    assert "授权订单查询工具" in result.answer
    assert not result.citations
