
from shopmate_agent.shopmate_graph import build_graph


graph = build_graph()

cases = [
    {
        "name": "导购",
        "question": "预算300元以内，推荐商品",
        "user_id": None,
    },
    {
        "name": "查单",
        "question": "订单ORD001现在什么状态？",
        "user_id": "demo_user_001",
    },
    {
        "name": "售后政策",
        "question": "七天退货有什么条件？",
        "user_id": None,
    },
]

for case in cases:
    result = graph.invoke({
        "question": case["question"],
        "user_id": case["user_id"],
    })

    print(f"\n=== {case['name']} ===")
    print("问题：", case["question"])
    print("意图：", result["intent"])
    print("答案：", result["answer"])
    print("来源：", result["citations"])
    print("校验通过：", result["verified"])
    print("重新检索次数：", result["retries"])
    print("执行轨迹：", " → ".join(result["trace"]))
