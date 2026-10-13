
from shopmate_agent.answer_quality import reply_to_customer


cases = [
    ("澄清", "帮我查一下订单。", []),
    ("拒答", "你能保证给我退款500元吗？", []),
    ("转人工", "过了退货期限，有特殊情况能破例吗？", []),
    ("政策引用", "七天退货有哪些条件？", []),
    ("多轮改写", "它多少钱？", ["我想了解商品P001"]),
]

for name, question, history in cases:
    reply = reply_to_customer(question, history)

    print(f"\n=== {name} ===")
    print("原问题:", question)
    print("改写后:", reply.rewritten_query)
    print("状态:", reply.status)
    print("回答:", reply.answer)
    print("引用文档:", [c["doc_id"] for c in reply.citations])
