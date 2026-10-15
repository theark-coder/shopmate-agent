
import re
import sqlite3
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from shopmate_agent.answer_quality import policy_evidence
from shopmate_agent.embedding_index import ROOT


DB = ROOT / "data/shopmate.db"


class ShopState(TypedDict, total=False):
    question: str
    user_id: str | None
    intent: str
    evidence: list[dict]
    answer: str
    citations: list[str]
    verified: bool
    retries: int
    trace: list[str]


def product_id(text: str) -> str | None:
    match = re.search(
        r"(?<![A-Za-z0-9])P\d{3}(?![A-Za-z0-9])",
        text,
        re.I,
    )
    return match.group().upper() if match else None


def order_id(text: str) -> str | None:
    match = re.search(
        r"(?<![A-Za-z0-9])ORD\d+(?![A-Za-z0-9])",
        text,
        re.I,
    )
    return match.group().upper() if match else None


def needs_policy_handoff(question: str) -> bool:
    """Exceptions require a human, never an automatic refund/extension."""
    domains = ("退货", "退款", "保修")
    exceptions = (
        "破例", "过期", "超过期限", "超出期限", "特殊批准",
        "特殊情况", "例外批准", "过了退货期限", "延长保修",
    )
    return any(term in question for term in domains) and any(
        term in question for term in exceptions
    )


def classify(state: ShopState) -> dict:
    q = state["question"]

    if needs_policy_handoff(q):
        intent = "handoff"
    elif (
        "订单" in q or "物流" in q
        or order_id(q) is not None
    ):
        intent = "order"
    elif any(w in q for w in (
        "退货", "退款政策", "保修", "配送政策",
        "七天", "7天", "发票政策",
    )):
        intent = "policy"
    elif any(w in q for w in (
        "推荐", "预算", "价格", "多少钱",
        "库存", "商品", "买", "选购",
    )) or product_id(q):
        intent = "product"
    else:
        intent = "clarify"

    return {
        "intent": intent,
        "evidence": [],
        "answer": "",
        "citations": [],
        "verified": False,
        "retries": 0,
        "trace": ["classify:" + intent],
    }


def route_intent(state: ShopState) -> str:
    return {
        "handoff": "human_handoff",
        "product": "product_tool",
        "order": "order_tool",
        "policy": "policy_retrieve",
        "clarify": "clarify",
    }[state["intent"]]


def product_tool(state: ShopState) -> dict:
    q = state["question"]
    pid = product_id(q)

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row

        sql = """
            SELECT p.product_id, p.name,
                   pr.price_cents, i.stock
            FROM products p
            JOIN prices pr USING (product_id)
            JOIN inventory i USING (product_id)
        """

        rows = conn.execute(sql).fetchall()

    records = [dict(row) for row in rows]

    if pid:
        records = [
            r for r in records if r["product_id"] == pid
        ]

    # 只支持明确的人民币预算表达
    budget_match = re.search(
        r"(?:预算|不超过|以内|低于)\s*(\d+)\s*元",
        q,
    )

    if budget_match:
        budget_cents = int(budget_match.group(1)) * 100
        records = [
            r for r in records
            if r["price_cents"] <= budget_cents
        ]

    records = [r for r in records if r["stock"] > 0]
    records.sort(key=lambda r: (r["price_cents"], r["product_id"]))

    return {
        "evidence": records[:3],
        "trace": state["trace"] + ["product_tool"],
    }


def order_tool(state: ShopState) -> dict:
    oid = order_id(state["question"])
    uid = state.get("user_id")

    if not uid or not oid:
        return {
            "evidence": [],
            "trace": state["trace"] + ["order_tool:unauthorized_or_missing"],
        }

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT order_id, user_id, product_id, status
            FROM orders
            WHERE order_id = ? AND user_id = ?
            """,
            (oid, uid),
        ).fetchone()

    return {
        "evidence": [dict(row)] if row else [],
        "trace": state["trace"] + ["order_tool"],
    }


def policy_retrieve(state: ShopState) -> dict:
    q = state["question"]

    if "保修" in q:
        name = "warranty"
    elif "发票" in q:
        name = "invoice"
    elif "配送" in q or "发货政策" in q:
        name = "shipping"
    else:
        name = "returns"

    evidence = policy_evidence(name)

    return {
        "evidence": [evidence],
        "trace": state["trace"] + ["policy_retrieve:" + name],
    }


def human_handoff(state: ShopState) -> dict:
    """Safe explanation only. Do not claim a human ticket was opened."""
    return {
        "answer": (
            "这个请求涉及退货、退款或保修政策的例外，"
            "需要人工客服进一步核实。我无法直接批准退款、延期或特殊处理。"
            "请通过官方人工客服渠道说明情况；不要在公开演示中填写真实订单资料。"
        ),
        "citations": [],
        "verified": True,
        "trace": state["trace"] + ["human_handoff"],
    }


def clarify(state: ShopState) -> dict:
    return {
        "answer": "请补充具体商品、订单或政策问题。",
        "citations": [],
        "verified": True,
        "trace": state["trace"] + ["clarify"],
    }


def answer(state: ShopState) -> dict:
    evidence = state["evidence"]
    intent = state["intent"]

    if not evidence:
        return {
            "answer": "没有足够的已核实信息，暂不能回答。",
            "citations": [],
            "trace": state["trace"] + ["answer:no_evidence"],
        }

    if intent == "product":
        lines = [
            f"{r['name']}（{r['product_id']}）："
            f"{r['price_cents'] / 100:.2f}元，"
            f"库存{r['stock']}件"
            for r in evidence
        ]
        reply = "根据商品数据库：" + "；".join(lines)
        citations = [
            "db:products:" + r["product_id"]
            for r in evidence
        ]

    elif intent == "order":
        r = evidence[0]
        reply = (
            f"订单{r['order_id']}的当前状态为"
            f"{r['status']}，商品ID为{r['product_id']}。"
        )
        citations = ["db:orders:" + r["order_id"]]

    else:
        r = evidence[0]
        reply = (
            "以下是已登记的政策原文：\n"
            + r["text"].strip()
            + f"\n[来源：{r['doc_id']}，版本：{r['version']}]"
        )
        citations = [r["doc_id"]]

    return {
        "answer": reply,
        "citations": citations,
        "trace": state["trace"] + ["answer"],
    }


def verify(state: ShopState) -> dict:
    evidence = state["evidence"]
    intent = state["intent"]
    citations = state["citations"]
    response = state["answer"]

    if not evidence:
        valid = not citations and "不能回答" in response
    elif intent == "product":
        valid = all(
            "db:products:" + r["product_id"] in citations
            and r["product_id"] in response
            for r in evidence
        )
    elif intent == "order":
        r = evidence[0]
        valid = (
            "db:orders:" + r["order_id"] in citations
            and r["order_id"] in response
            and r["status"] in response
        )
    else:
        r = evidence[0]
        valid = (
            r["doc_id"] in citations
            and r["text"].strip() in response
        )

    return {
        "verified": valid,
        "trace": state["trace"] + [
            "verify:" + ("pass" if valid else "fail")
        ],
    }


def after_verify(state: ShopState) -> str:
    if state["verified"]:
        return "done"
    if state.get("retries", 0) < 1:
        return "retry"
    return "safe_end"


def retry_retrieve(state: ShopState) -> dict:
    # 本地离线演示：重新获取权威来源，并记录尝试次数。
    # 这里不声称改变了检索参数或使用了大模型。
    return {
        "retries": state.get("retries", 0) + 1,
        "trace": state["trace"] + ["retry_retrieve"],
    }


def safe_end(state: ShopState) -> dict:
    return {
        "answer": "答案校验未通过，请人工核实后再答复。",
        "citations": [],
        "trace": state["trace"] + ["safe_end"],
    }


def build_graph():
    g = StateGraph(ShopState)

    g.add_node("classify", classify)
    g.add_node("product_tool", product_tool)
    g.add_node("order_tool", order_tool)
    g.add_node("policy_retrieve", policy_retrieve)
    g.add_node("clarify", clarify)
    g.add_node("human_handoff", human_handoff)
    g.add_node("answer", answer)
    g.add_node("verify", verify)
    g.add_node("retry_retrieve", retry_retrieve)
    g.add_node("safe_end", safe_end)

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route_intent)

    for node in ("product_tool", "order_tool", "policy_retrieve"):
        g.add_edge(node, "answer")

    g.add_edge("clarify", END)
    g.add_edge("human_handoff", END)
    g.add_edge("answer", "verify")

    g.add_conditional_edges(
        "verify",
        after_verify,
        {
            "done": END,
            "retry": "retry_retrieve",
            "safe_end": "safe_end",
        },
    )

    g.add_conditional_edges(
        "retry_retrieve",
        route_intent,
        {
            "product_tool": "product_tool",
            "order_tool": "order_tool",
            "policy_retrieve": "policy_retrieve",
            "clarify": "clarify",
        },
    )

    g.add_edge("safe_end", END)

    return g.compile()
