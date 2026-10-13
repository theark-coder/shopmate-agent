
from uuid import uuid4

from shopmate_agent.conversation_memory import SessionMemory
from shopmate_agent.shopmate_graph import build_graph


def main():
    memory = SessionMemory()
    graph = build_graph()

    session_id = f"day21-{uuid4().hex[:12]}"
    owner_id = "demo_user_001"

    questions = [
        "商品P001多少钱？",
        "预算300元以内，不要推荐耳机",
    ]

    cycle = [
        "七天退货政策是什么？",
        "订单ORD001现在什么状态？",
        "推荐商品",
    ]

    while len(questions) < 20:
        questions.append(
            cycle[(len(questions) - 2) % len(cycle)]
        )

    for number, question in enumerate(questions, 1):
        result = graph.invoke({
            "question": question,
            "user_id": owner_id,
        })

        memory.append_turn(
            session_id=session_id,
            owner_id=owner_id,
            question=question,
            answer=result["answer"],
            source_ids=result["citations"],
        )

        context = memory.context(
            session_id,
            owner_id,
            token_budget=1200,
            recent_limit=6,
        )

        assert context["estimated_tokens"] <= 1200

        print(
            f"第{number:02d}轮："
            f"预算使用 {context['estimated_tokens']}/1200"
        )

    # 模拟重新启动进程后恢复数据
    reopened = SessionMemory()
    final = reopened.context(
        session_id,
        owner_id,
        token_budget=1200,
    )

    assert "预算300元以内" in final["constraints"]
    assert "不要推荐耳机" in final["constraints"]
    assert "db:products:P001" in final["source_ids"]
    assert "policy-returns" in final["source_ids"]

    print("\n=== Day 21 最终验证 ===")
    print("会话ID:", session_id)
    print("最近窗口消息数:", len(final["messages"]) - 1)
    print("保留约束:", final["constraints"])
    print("保留来源ID:", final["source_ids"])
    print("最后明确商品ID:", final["last_product_id"])
    print("预算使用:", final["estimated_tokens"], "/ 1200")
    print("20轮会话持久化及压缩验证通过")


if __name__ == "__main__":
    main()
