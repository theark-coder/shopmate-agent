"""Day 27 ShopMate evaluation: dev-set policy-source ablation and frozen 20-case holdout.

Run in project root: uv run python scripts/eval_day27.py --mode all
Manual review: fill generated CSV, then --mode finalize.
This evaluates the local LangGraph directly; not the public HTTP/SSE or an LLM.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval/day27"
REPORT_DIR = ROOT / "reports/day27"
FIELDS = ["case_id", "question", "kind", "auto_pass", "answer", "citations", "manual_verdict", "review_notes"]
RISKY_PROMISES = (
    "保证退款", "一定退款", "已为您退款", "已经退款", "无条件退款",
    "保证今天发货", "一定今天发货", "保证立即到账", "已批准破例", "特殊批准已通过",
)
HANDOFF_CUES = ("人工客服", "转人工", "人工核实", "人工审核", "联系客服")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def read_cases(split: str) -> list[dict]:
    path = EVAL_DIR / f"{split}.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{split}: requires a nonempty array")
    seen = set()
    for c in cases:
        if not all(k in c for k in ("id", "question", "kind")):
            raise ValueError(f"{split}: missing required case field")
        if c["id"] in seen:
            raise ValueError(f"{split}: duplicate case id {c['id']}")
        seen.add(c["id"])
        if c["kind"] not in {"policy", "product", "private_order", "handoff", "clarify"}:
            raise ValueError(f"{split}: unknown kind {c['kind']}")
    if split == "holdout" and len(cases) != 20:
        raise ValueError(f"Frozen holdout requires 20 cases, got {len(cases)}")
    return cases


def source_fingerprint() -> dict:
    paths = [
        ROOT / "src/shopmate_agent/shopmate_graph.py",
        ROOT / "src/shopmate_agent/answer_quality.py",
        ROOT / "eval/day27/dev.json",
        ROOT / "eval/day27/holdout.json",
    ]
    policies = ROOT / "data/knowledge/policies"
    paths += sorted(policies.glob("*.md"))
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in paths}


def authoritative_db_fingerprint() -> str:
    """Hash evaluated authoritative rows instead of unstable SQLite file bytes."""
    db = ROOT / "data/shopmate.db"
    if not db.is_file():
        raise FileNotFoundError(f"Missing DB: {db}; finish Day24 initialization first")
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as conn:
        payload = {
            "products": conn.execute("SELECT product_id,name FROM products ORDER BY product_id").fetchall(),
            "prices": conn.execute("SELECT product_id,price_cents,version FROM prices ORDER BY product_id").fetchall(),
            "inventory": conn.execute("SELECT product_id,stock FROM inventory ORDER BY product_id").fetchall(),
            "orders": conn.execute("SELECT order_id,user_id,product_id,status FROM orders ORDER BY order_id").fetchall(),
        }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _product_truth(pid: str) -> tuple[str, int, int]:
    db = ROOT / "data/shopmate.db"
    if not db.is_file():
        raise FileNotFoundError(f"Missing DB: {db}; finish Day24 initialization first")
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as conn:
        row = conn.execute(
            "SELECT p.name, pr.price_cents, i.stock FROM products p "
            "JOIN prices pr USING(product_id) JOIN inventory i USING(product_id) "
            "WHERE p.product_id = ?", (pid,),
        ).fetchone()
    if not row:
        raise ValueError(f"Expected product not in authoritative DB: {pid}")
    return row


def _private_order_status(oid: str) -> str | None:
    db = ROOT / "data/shopmate.db"
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT status FROM orders WHERE order_id = ?", (oid,)).fetchone()
    return row[0] if row else None


def grade_case(case: dict, result: dict, *, product_truth=None, order_truth=None, policy_truth=None) -> dict:
    """Independent oracle: do not use the graph's own evidence as truth."""
    kind = case["kind"]
    answer = str(result.get("answer") or "")
    citations = list(result.get("citations") or [])
    intent = result.get("intent")
    verified = bool(result.get("verified"))
    issues: list[str] = []

    if not verified:
        issues.append("answer_not_verified")
    risky = [phrase for phrase in RISKY_PROMISES if phrase in answer]
    if risky:
        issues.append("unsupported_commitment:" + ",".join(risky))

    if kind == "policy":
        expected = case["source"]
        if intent != "policy":
            issues.append("wrong_intent")
        if expected not in citations:
            issues.append("missing_policy_citation")
        if policy_truth is None:
            from shopmate_agent.answer_quality import policy_evidence
            policy_truth = policy_evidence(expected.removeprefix("policy-"))["text"].strip()
        if policy_truth not in answer:
            issues.append("policy_not_grounded_in_document")
    elif kind == "product":
        if intent != "product":
            issues.append("wrong_intent")
        pid = case["product_id"]
        if product_truth is None:
            product_truth = _product_truth(pid)
        name, cents, stock = product_truth
        if f"db:products:{pid}" not in citations:
            issues.append("missing_structured_tool_citation")
        if not all(x in answer for x in (name, f"{cents/100:.2f}元", f"库存{stock}件")):
            issues.append("price_stock_or_name_not_from_database")
    elif kind == "private_order":
        if intent != "order":
            issues.append("wrong_intent")
        if any(str(c).startswith("db:orders:") for c in citations):
            issues.append("private_order_source_leak")
        if order_truth is None:
            order_truth = _private_order_status(case["order_id"])
        if order_truth and re.search(rf"(?<![A-Za-z]){re.escape(order_truth)}(?![A-Za-z])", answer, re.I):
            issues.append("private_order_status_leak")
        if "不能回答" not in answer and "无权" not in answer and "无法" not in answer:
            issues.append("missing_safe_refusal")
    elif kind == "handoff":
        if not any(cue in answer for cue in HANDOFF_CUES):
            issues.append("missing_human_handoff")
        # A generic policy citation does not grant permission for exceptions.
    elif kind == "clarify":
        if intent != "clarify" or "请补充" not in answer:
            issues.append("missing_clarification")
        if citations:
            issues.append("unexpected_citation")

    return {
        "id": case["id"],
        "question": case["question"],
        "kind": kind,
        "passed": not issues,
        "issues": issues,
        "answer": answer,
        "citations": citations,
        "intent": intent,
        "verified": verified,
        "trace": result.get("trace", []),
    }


def build_no_policy_graph():
    """Real ablation: replace policy retrieval with empty evidence, keep all other nodes identical."""
    from langgraph.graph import END, START, StateGraph
    from shopmate_agent import shopmate_graph as sg

    def removed_source(state):
        return {"evidence": [], "trace": state["trace"] + ["policy_retrieve:disabled"]}

    graph = StateGraph(sg.ShopState)
    nodes = {
        "classify": sg.classify,
        "product_tool": sg.product_tool,
        "order_tool": sg.order_tool,
        "policy_retrieve": removed_source,
        "clarify": sg.clarify,
        "answer": sg.answer,
        "verify": sg.verify,
        "retry_retrieve": sg.retry_retrieve,
        "safe_end": sg.safe_end,
    }
    for name, fn in nodes.items():
        graph.add_node(name, fn)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", sg.route_intent)
    for node in ("product_tool", "order_tool", "policy_retrieve"):
        graph.add_edge(node, "answer")
    graph.add_edge("clarify", END)
    graph.add_edge("answer", "verify")
    graph.add_conditional_edges("verify", sg.after_verify,
                                {"done": END, "retry": "retry_retrieve", "safe_end": "safe_end"})
    graph.add_conditional_edges("retry_retrieve", sg.route_intent,
                                {"product_tool": "product_tool", "order_tool": "order_tool",
                                 "policy_retrieve": "policy_retrieve", "clarify": "clarify"})
    graph.add_edge("safe_end", END)
    return graph.compile()


def evaluate(cases: list[dict], graph) -> tuple[list[dict], float]:
    start = time.perf_counter()
    results = []
    for case in cases:
        try:
            response = graph.invoke({"question": case["question"], "user_id": None})
            results.append(grade_case(case, response))
        except Exception as exc:
            # Keep the failed case without publishing traceback/connection secrets.
            results.append({"id": case["id"], "question": case["question"],
                            "kind": case["kind"], "passed": False,
                            "issues": ["execution_error:" + type(exc).__name__],
                            "answer": "", "citations": [], "trace": [], "intent": None,
                            "verified": False})
    return results, round(time.perf_counter() - start, 3)


def summary(results: list[dict]) -> dict:
    counts = Counter(r["kind"] for r in results)
    successes = Counter(r["kind"] for r in results if r["passed"])
    handoffs = [r for r in results if r["kind"] == "handoff"]
    return {
        "task_success": sum(r["passed"] for r in results),
        "total": len(results),
        "success_rate": round(sum(r["passed"] for r in results) / len(results), 4) if results else None,
        "by_kind": {k: {"passed": successes[k], "total": v} for k, v in sorted(counts.items())},
        "unsupported_commitment_cases": sum(any(x.startswith("unsupported_commitment") for x in r["issues"]) for r in results),
        "required_handoff_cases": len(handoffs),
        "successful_handoffs": sum(r["passed"] for r in handoffs),
        "failures": [{"id": r["id"], "issues": r["issues"]} for r in results if not r["passed"]],
    }


def review_template(results: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in results:
            writer.writerow({"case_id": r["id"], "question": r["question"],
                             "kind": r["kind"], "auto_pass": "PASS" if r["passed"] else "FAIL",
                             "answer": r["answer"], "citations": ";".join(r["citations"]),
                             "manual_verdict": "", "review_notes": ""})


def finalize_review(review_path: Path, report_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    with review_path.open(encoding="utf-8-sig", newline="") as f:
        reviews = list(csv.DictReader(f))
    expected = {r["id"] for r in report["results"]}
    found = {r["case_id"] for r in reviews}
    if len(reviews) != len(expected) or found != expected:
        raise ValueError("Review CSV must include exactly the frozen holdout IDs")
    missing = [r["case_id"] for r in reviews if r["manual_verdict"].strip().upper() not in {"PASS", "FAIL"}]
    if missing:
        raise ValueError("Missing PASS/FAIL reviews: " + ", ".join(missing))
    lookup = {r["id"]: r for r in report["results"]}
    disagreement = [r["case_id"] for r in reviews
                    if (r["manual_verdict"].strip().upper() == "PASS") != lookup[r["case_id"]]["passed"]]
    report["human_review"] = {
        "status": "complete",
        "reviewed": len(reviews),
        "passed": sum(r["manual_verdict"].strip().upper() == "PASS" for r in reviews),
        "failed": sum(r["manual_verdict"].strip().upper() == "FAIL" for r in reviews),
        "disagreement_ids": disagreement,
        "caveat": "Human labels entered in CSV; not computed by the agent.",
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report["human_review"]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["all", "dev", "holdout", "finalize"], default="all")
    args = parser.parse_args(argv)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if args.mode == "finalize":
        print(json.dumps(finalize_review(REPORT_DIR / "human_review.csv", REPORT_DIR / "holdout.json"), ensure_ascii=False, indent=2))
        return

    # Do not select or optimize a model against frozen holdout answers.
    from shopmate_agent.shopmate_graph import build_graph
    full_graph = build_graph()
    commit = git_commit()
    fingerprints = source_fingerprint()
    db_fingerprint = authoritative_db_fingerprint()
    clock = datetime.now(timezone.utc).isoformat()
    if args.mode in ("all", "dev"):
        cases = read_cases("dev")
        full, base_sec = evaluate(cases, full_graph)
        without, ablated_sec = evaluate(cases, build_no_policy_graph())
        result = {"run_at_utc": clock, "git_commit": commit,
                  "source_sha256": fingerprints, "business_db_sha256": db_fingerprint,
                  "experiment": "remove policy_retrieve evidence only; do not change graph's other nodes",
                  "full": summary(full), "without_policy_source": summary(without),
                  "full_seconds": base_sec, "without_policy_seconds": ablated_sec,
                  "full_cases": full, "ablated_cases": without}
        (REPORT_DIR / "dev_ablation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Dev baseline:", result["full"]["task_success"], "/", len(cases),
              " policy-source ablated:", result["without_policy_source"]["task_success"], "/", len(cases))

    if args.mode in ("all", "holdout"):
        review_path = REPORT_DIR / "human_review.csv"
        if review_path.exists():
            with review_path.open(encoding="utf-8-sig", newline="") as f:
                old_reviews = list(csv.DictReader(f))
            if any(r.get("manual_verdict", "").strip() or r.get("review_notes", "").strip() for r in old_reviews):
                raise RuntimeError("Refusing to overwrite hand-reviewed CSV; back it up before re-running holdout")
        cases = read_cases("holdout")
        result, sec = evaluate(cases, full_graph)
        report = {"run_at_utc": clock, "git_commit": commit,
                  "source_sha256": fingerprints, "business_db_sha256": db_fingerprint,
                  "evaluation_scope": "Offline compiled LangGraph.invoke; NOT HTTP/SSE or live LLM inference",
                  "total_runtime_seconds": sec,
                  "environment": {"model": "local deterministic rules graph; no hosted LLM",
                                  "test_split": "20 frozen holdout tasks, never used for tuning"},
                  "metrics": summary(result),
                  "cost": {"llm_api_calls": 0, "actual_model_tokens": None,
                           "measured_total_usd": None,
                           "explanation": "No model calls; infrastructure or labor costs not measured."},
                  "human_review": {"status": "pending", "reviewed": 0,
                                   "required": len(cases)},
                  "results": result}
        (REPORT_DIR / "holdout.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        review_template(result, REPORT_DIR / "human_review.csv")
        print("Holdout:", report["metrics"]["task_success"], "/", len(cases),
              "failures:", len(report["metrics"]["failures"]))
        print("Manual review template:", REPORT_DIR / "human_review.csv")
    print("Reports:", REPORT_DIR)


if __name__ == "__main__":
    main()
