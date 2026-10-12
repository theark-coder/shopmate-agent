
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "eval" / "tasks.json"


def product(pid):
    return [f"{pid}-description", f"{pid}-faq"]


# 每条数据：(用户问题, 相关文档, 预期工具)
SHOPPING = [
    ("想买主动降噪耳机，推荐哪款？", product("P001"), "search_products"),
    ("蓝牙降噪耳机续航多少小时？", product("P001"), "none"),
    ("有支持热插拔的机械键盘吗？", product("P002"), "search_products"),
    ("机械键盘是什么布局？", product("P002"), "none"),
    ("想选静音按键的无线鼠标。", product("P003"), "search_products"),
    ("无线鼠标支持哪种连接？", product("P003"), "none"),
    ("有15.6英寸的便携显示器吗？", product("P004"), "search_products"),
    ("便携显示器分辨率是多少？", product("P004"), "none"),
    ("有没有带HDMI的扩展坞？", product("P005"), "search_products"),
    ("USB-C扩展坞有哪些接口？", product("P005"), "none"),
    ("想买1TB的移动固态硬盘。", product("P006"), "search_products"),
    ("移动固态硬盘使用什么接口？", product("P006"), "none"),
    ("推荐一款可调节高度的笔记本支架。", product("P007"), "search_products"),
    ("笔记本支架是什么材质？", product("P007"), "none"),
    ("帮我找一款1080P摄像头。", product("P008"), "search_products"),
    ("高清摄像头有内置麦克风吗？", product("P008"), "none"),
    ("有没有心形指向的桌面麦克风？", product("P009"), "search_products"),
    ("桌面麦克风怎么连接电脑？", product("P009"), "none"),
    ("想买一个可以定时关闭的台灯。", product("P010"), "search_products"),
    ("智能台灯目前多少钱、还有库存吗？", product("P010"), "get_price_stock"),
]

ORDERS = [
    ("帮我看一下自己的订单状态。", ["FAQ002"], "get_order_status"),
    ("订单ORD001已经发货了吗？", ["FAQ002", "policy-shipping"], "get_order_status"),
    ("ORD001什么时候安排发货？", ["FAQ002", "policy-shipping"], "get_order_status"),
    ("想查看ORD001的物流处理进度。", ["FAQ002"], "get_order_status"),
    ("付款后通常多久发货？", ["policy-shipping"], "none"),
    ("昨天付款还没发货，怎么核对？", ["FAQ002", "policy-shipping"], "get_order_status"),
    ("如何确认ORD001现在的履约状态？", ["FAQ002"], "get_order_status"),
    ("如何查询我有权限查看的订单？", ["FAQ002", "policy-privacy"], "get_order_status"),
    ("我可以查看其他顾客的订单吗？", ["policy-privacy"], "none"),
    ("查询个人订单需要登录账户吗？", ["FAQ002", "policy-privacy"], "none"),
    ("ORD001是否已经进入配送流程？", ["FAQ002", "policy-shipping"], "get_order_status"),
    ("发货进度是不是以订单状态为准？", ["policy-shipping"], "none"),
    ("ORD001买的是什么商品？", ["FAQ002"], "get_order_status"),
    ("已发货订单如何核实配送进度？", ["FAQ002", "policy-shipping"], "get_order_status"),
    ("订单页面能不能看到当前处理状态？", ["FAQ002"], "get_order_status"),
    ("请核对我这笔ORD001订单。", ["FAQ002"], "get_order_status"),
    ("平台会把订单信息用于什么用途？", ["policy-privacy"], "none"),
    ("订单完成以后怎样申请电子发票？", ["FAQ004", "policy-invoice"], "none"),
    ("ORD001现在满足申请发票的条件吗？", ["FAQ004", "policy-invoice"], "get_order_status"),
    ("刚支付的订单适用什么发货规则？", ["policy-shipping"], "none"),
]

AFTERSALES = [
    ("签收七天内可以申请退货吗？", ["policy-returns"], "none"),
    ("退货商品需要保持完好吗？", ["policy-returns"], "none"),
    ("定制商品适用七天退货吗？", ["policy-returns"], "none"),
    ("耳机申请退货有哪些商品状态要求？", ["policy-returns"], "none"),
    ("我的ORD001订单符合退货条件吗？", ["policy-returns", "FAQ003"], "get_return_eligibility"),
    ("退货资格需要结合订单状态判断吗？", ["policy-returns", "FAQ003"], "get_return_eligibility"),
    ("超过七天还能申请退货吗？", ["policy-returns"], "none"),
    ("在哪里查看商品退货规则？", ["FAQ003", "policy-returns"], "none"),
    ("售后审核退货要核对哪些条件？", ["policy-returns", "FAQ003"], "get_return_eligibility"),
    ("七天退货的适用条件是什么？", ["policy-returns"], "none"),
    ("商品保修范围由什么决定？", ["policy-warranty"], "none"),
    ("这类商品的保修期限在哪里查询？", ["policy-warranty"], "none"),
    ("申请保修需要准备哪些信息？", ["FAQ005", "policy-warranty"], "none"),
    ("如何联系客服申请商品保修？", ["FAQ005"], "none"),
    ("售后保修的具体范围以什么为准？", ["policy-warranty"], "none"),
    ("售后发票可以申请电子版吗？", ["FAQ004", "policy-invoice"], "none"),
    ("怎样判断我的订单是否可退？", ["policy-returns", "FAQ003"], "get_return_eligibility"),
    ("定制产品可能有哪些退货例外？", ["policy-returns"], "none"),
    ("电子发票的申请有什么限制？", ["policy-invoice"], "none"),
    ("售后使用订单信息时如何保护隐私？", ["policy-privacy"], "none"),
]


def main():
    tasks = []

    # 14+13+13=40 条 dev；6+7+7=20 条 test
    groups = [
        ("shopping", "S", SHOPPING, 14),
        ("order", "O", ORDERS, 13),
        ("aftersales", "A", AFTERSALES, 13),
    ]

    for category, prefix, examples, dev_count in groups:
        assert len(examples) == 20

        for index, (query, relevant_docs, tool) in enumerate(
            examples, start=1
        ):
            tasks.append({
                "id": f"{prefix}{index:02d}",
                "split": "dev" if index <= dev_count else "test",
                "category": category,
                "query": query,
                "relevant_doc_ids": relevant_docs,
                "relevant_policy_ids": [
                    doc for doc in relevant_docs
                    if doc.startswith("policy-")
                ],
                "expected_tool": tool,
            })

    assert len(tasks) == 60
    assert sum(t["split"] == "dev" for t in tasks) == 40
    assert sum(t["split"] == "test" for t in tasks) == 20

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({
            "dataset_version": "1.0",
            "tasks": tasks,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Saved:", OUTPUT)
    print("Total: 60, Dev: 40, Test: 20")


if __name__ == "__main__":
    main()
