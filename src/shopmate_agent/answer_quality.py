
import re
from dataclasses import dataclass
from pathlib import Path

from shopmate_agent.chunking import parse_markdown


ROOT = Path(__file__).resolve().parents[2]
POLICIES = ROOT / "data" / "knowledge" / "policies"


@dataclass(frozen=True)
class Reply:
    status: str
    rewritten_query: str
    answer: str
    citations: list[dict]


def rewrite_query(question: str, history: list[str]) -> str:
    """只根据明确出现过的商品 ID 补全多轮指代。"""
    question = question.strip()

    if not question:
        return question

    if not re.search(r"它|这个|这款|那个", question):
        return question

    # 最新的上下文优先；不从模型猜测商品
    for message in reversed(history):
        match = re.search(
        r"(?<![A-Za-z0-9])P\d{3}(?![A-Za-z0-9])",
        message,
        re.I,
    )
        if match:
            pid = match.group().upper()
            return f"关于商品 {pid}，{question}"

    return question


def policy_evidence(name: str):
    """读取真实 Markdown 政策及其来源元数据。"""
    path = POLICIES / f"{name}.md"

    metadata, body = parse_markdown(path)

    return {
        "doc_id": metadata["doc_id"],
        "version": metadata["version"],
        "source": metadata["source"],
        "source_path": path.relative_to(ROOT).as_posix(),
        "text": body.strip(),
    }


def reply_to_customer(
    question: str,
    history: list[str] | None = None,
    authorized_order_id: str | None = None,
) -> Reply:
    history = history or []
    query = rewrite_query(question, history)

    if not query:
        return Reply(
            "CLARIFY",
            query,
            "请说明你想咨询的商品、订单或售后问题。",
            [],
        )

    # 识别需要人工判断的政策例外
    if any(term in query for term in (
        "破例", "特殊情况", "超过期限",
        "过了退货期限", "例外批准",
    )):
        return Reply(
            "HANDOFF",
            query,
            "该情况需要人工核实。"
            "我无法自行批准政策例外，"
            "请联系人工客服进一步处理。",
            [],
        )

    # 拒绝无依据的确定性承诺
    wants_guarantee = any(
        term in query
        for term in ("保证", "一定", "承诺", "立即")
    )
    sensitive_action = any(
        term in query
        for term in ("退款", "赔偿", "优惠", "到账", "发货")
    )

    if wants_guarantee and sensitive_action:
        return Reply(
            "REFUSE_UNSUPPORTED",
            query,
            "目前没有足够的已核实信息支持该承诺。"
            "我不能保证优惠、退款金额、到账时间或发货时间。",
            [],
        )

    order_pattern = r"(?<![A-Za-z0-9])ORD\d+(?![A-Za-z0-9])"

    if "订单" in query or re.search(order_pattern, query, re.I):
        order = (
            re.search(order_pattern, query, re.I)
            or (
                re.search(order_pattern, authorized_order_id, re.I)
                if authorized_order_id else None
            )
        )

        if not order:
            return Reply(
                "CLARIFY",
                query,
                "请提供订单编号。"
                "查询时还需要核实你是否有权查看该订单。",
                [],
            )

        return Reply(
            "NEED_ORDER_TOOL",
            query,
            f"需要通过授权订单查询工具核实"
            f" {order.group().upper()} 的实际状态，"
            "不能根据静态文档猜测。",
            [],
        )

    if "退货" in query or "七天" in query or "7天" in query:
        evidence = policy_evidence("returns")
        return Reply(
            "ANSWERED",
            query,
            "根据退货政策，符合条件的商品可在签收后"
            "7天内申请退货，商品应保持完好；"
            "定制商品等特殊类别可能不适用。"
            "是否符合条件仍需结合实际订单与商品状态判断。"
            f" [来源：{evidence['doc_id']}，"
            f"版本：{evidence['version']}]",
            [evidence],
        )

    if "保修" in query:
        evidence = policy_evidence("warranty")
        return Reply(
            "ANSWERED",
            query,
            "保修范围和期限以对应商品说明及订单凭证为准。"
            f" [来源：{evidence['doc_id']}，"
            f"版本：{evidence['version']}]",
            [evidence],
        )

    return Reply(
        "CLARIFY",
        query,
        "当前信息不足以给出可靠答复。"
        "请补充具体商品、订单编号或需要咨询的政策。",
        [],
    )
