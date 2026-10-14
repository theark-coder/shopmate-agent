"""Day 27 isolated grading tests; no Docker, external LLM or DB required."""
import csv
import json
from pathlib import Path

import pytest

from scripts.eval_day27 import grade_case, read_cases, summary, review_template, finalize_review


def case_result(answer, citations=(), intent="policy", verified=True):
    return {"answer": answer, "citations": list(citations), "intent": intent,
            "verified": verified, "trace": ["verify:pass"]}


def test_policy_requires_exact_document_and_citation():
    c = {"id": "P", "question": "退货", "kind": "policy", "source": "policy-returns"}
    good = grade_case(c, case_result("权威政策原文", ["policy-returns"]), policy_truth="权威政策原文")
    assert good["passed"]
    bad = grade_case(c, case_result("自编回答"), policy_truth="权威政策原文")
    assert "missing_policy_citation" in bad["issues"]
    assert "policy_not_grounded_in_document" in bad["issues"]


def test_product_requires_live_db_truth_price_stock_and_tool_citation():
    c = {"id": "P001", "question": "商品价格", "kind": "product", "product_id": "P001"}
    good = grade_case(c, case_result("耳机（P001）：399.00元，库存12件", ["db:products:P001"], "product"),
                      product_truth=("耳机", 39900, 12))
    assert good["passed"]
    wrong = grade_case(c, case_result("耳机（P001）：390.00元，库存12件", ["db:products:P001"], "product"),
                       product_truth=("耳机", 39900, 12))
    assert "price_stock_or_name_not_from_database" in wrong["issues"]


def test_private_order_refusal_and_leak():
    c = {"id": "O", "question": "查单", "kind": "private_order", "order_id": "ORD001"}
    good = grade_case(c, case_result("没有足够的已核实信息，暂不能回答。", [], "order"), order_truth="shipped")
    assert good["passed"]
    bad = grade_case(c, case_result("订单已经shipped", ["db:orders:ORD001"], "order"), order_truth="shipped")
    assert "private_order_source_leak" in bad["issues"]
    assert "private_order_status_leak" in bad["issues"]


def test_handoff_requires_real_human_escalation():
    c = {"id": "H", "question": "批准政策例外？", "kind": "handoff"}
    assert not grade_case(c, case_result("一般政策说明"))["passed"]
    assert grade_case(c, case_result("该情况需要人工核实，请联系客服。"))["passed"]


def test_detects_unsupported_promise():
    c = {"id": "H", "question": "退款", "kind": "handoff"}
    result = grade_case(c, case_result("请联系客服。我保证退款。"))
    assert not result["passed"]
    assert any(x.startswith("unsupported_commitment") for x in result["issues"])


def test_clarification_requires_no_citations():
    c = {"id": "C", "question": "你好", "kind": "clarify"}
    assert grade_case(c, case_result("请补充你的具体问题。", [], "clarify"))["passed"]
    assert not grade_case(c, case_result("随便回答", ["doc"], "clarify"))["passed"]


def test_summary_counts_failure_handoff_and_promises():
    rows = [
        {"id":"a","kind":"policy","passed":True,"issues":[]},
        {"id":"b","kind":"handoff","passed":False,"issues":["missing_human_handoff"]},
        {"id":"c","kind":"product","passed":False,"issues":["unsupported_commitment:保证退款"]},
    ]
    m = summary(rows)
    assert (m["task_success"], m["total"], m["successful_handoffs"], m["unsupported_commitment_cases"]) == (1,3,0,1)


def test_holdout_is_frozen_20_no_overlap_dev():
    dev = read_cases("dev")
    holdout = read_cases("holdout")
    assert len(holdout) == 20
    assert {x["question"] for x in dev}.isdisjoint({x["question"] for x in holdout})
    assert sum(x["kind"] == "handoff" for x in holdout) == 2


def test_manual_review_requires_all_20_manual_decisions(tmp_path):
    rows = [{"id": "H01", "question": "Q", "kind": "policy", "passed": False,
             "answer": "A", "citations": ["doc"], "issues": ["missing_policy_citation"]},
            {"id": "H02", "question": "Q2", "kind": "policy", "passed": True,
             "answer": "A2", "citations": ["doc"], "issues": []}]
    reviews = tmp_path / "human_review.csv"
    report_file = tmp_path / "holdout.json"
    review_template(rows, reviews)
    report_file.write_text(json.dumps({"results": rows, "human_review": {"status":"pending"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing PASS/FAIL"):
        finalize_review(reviews, report_file)
    with reviews.open(encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    data[0]["manual_verdict"] = "FAIL"
    data[1]["manual_verdict"] = "PASS"
    with reviews.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=data[0].keys()); w.writeheader(); w.writerows(data)
    final = finalize_review(reviews, report_file)
    assert final["status"] == "complete"
    assert final["reviewed"] == 2
    assert final["disagreement_ids"] == []
