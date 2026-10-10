
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = DATA / "knowledge"
DB = DATA / "shopmate.db"

PRODUCTS = [
    ("P001", "蓝牙降噪耳机", "支持主动降噪，续航30小时", 39900, 12),
    ("P002", "机械键盘", "87键布局，支持热插拔", 29900, 25),
    ("P003", "无线鼠标", "支持2.4GHz连接，静音按键", 12900, 40),
    ("P004", "便携显示器", "15.6英寸，1080P分辨率", 79900, 8),
    ("P005", "USB-C扩展坞", "提供HDMI、USB-A接口", 19900, 30),
    ("P006", "移动固态硬盘", "1TB容量，USB 3.2接口", 49900, 15),
    ("P007", "笔记本支架", "六档高度调节，铝合金材质", 8900, 50),
    ("P008", "高清摄像头", "1080P画质，内置麦克风", 25900, 18),
    ("P009", "桌面麦克风", "USB连接，心形指向拾音", 34900, 10),
    ("P010", "智能台灯", "支持亮度调节和定时关闭", 15900, 22),
]

FAQS = [
    ("配送", "什么时候发货？", "付款成功后通常在48小时内发货。"),
    ("订单", "如何查询订单？", "登录账户后可查询本人订单状态。"),
    ("售后", "如何申请退货？", "请先查看退货政策及订单状态。"),
    ("发票", "可以开发票吗？", "可在订单完成后申请电子发票。"),
    ("保修", "如何申请保修？", "提供订单号并联系客服申请。"),
]

POLICIES = [
    ("returns", "退货政策",
     "符合条件的商品可在签收后7天内申请退货。"
     "商品应保持完好；定制商品等特殊类别可能不适用。"),
    ("shipping", "配送政策",
     "付款成功后通常48小时内发货，具体以订单状态为准。"),
    ("warranty", "保修政策",
     "保修范围和期限以对应商品说明及订单凭证为准。"),
    ("privacy", "隐私政策",
     "订单信息仅用于授权的订单处理、查询和售后服务。"),
    ("invoice", "发票政策",
     "支持符合条件的订单申请电子发票。"),
]


def write_doc(category, name, doc_id, title, body):
    folder = DOCS / category
    folder.mkdir(parents=True, exist_ok=True)

    text = (
        "---\n"
        f"doc_id: {doc_id}\n"
        "version: 1.0\n"
        "source: shopmate-demo\n"
        "updated_at: 2026-10-09\n"
        "---\n\n"
        f"# {title}\n\n{body}\n"
    )
    (folder / name).write_text(text, encoding="utf-8")


def generate_documents():
    for pid, name, feature, price, stock in PRODUCTS:
        write_doc(
            "products",
            f"{pid}.md",
            f"{pid}-description",
            f"{name} - 商品说明",
            f"商品ID：{pid}\n\n名称：{name}\n\n"
            f"产品特点：{feature}\n\n"
            "实际售价和库存请查询结构化商品数据。",
        )

        write_doc(
            "products",
            f"{pid}-faq.md",
            f"{pid}-faq",
            f"{name} - 常见问题",
            f"商品ID：{pid}\n\n"
            f"问：{name}有什么特点？\n\n答：{feature}。\n\n"
            "问：现在多少钱、还有库存吗？\n\n"
            "答：请查询实时价格和库存工具。",
        )

    for index, (category, question, answer) in enumerate(FAQS, 1):
        write_doc(
            "faqs",
            f"FAQ{index:03d}.md",
            f"FAQ{index:03d}",
            f"{category} FAQ",
            f"问：{question}\n\n答：{answer}",
        )

    for pid, title, content in POLICIES:
        write_doc(
            "policies",
            f"{pid}.md",
            f"policy-{pid}",
            title,
            f"政策名称：{title}\n\n适用说明：{content}\n\n"
            "具体是否符合条件，需结合订单和商品状态判断。",
        )


def generate_database():
    DATA.mkdir(exist_ok=True)

    with sqlite3.connect(DB) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prices (
                product_id TEXT PRIMARY KEY,
                price_cents INTEGER NOT NULL,
                version INTEGER NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(product_id)
            );

            CREATE TABLE IF NOT EXISTS inventory (
                product_id TEXT PRIMARY KEY,
                stock INTEGER NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(product_id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(product_id)
            );
        """)

        for pid, name, _, price, stock in PRODUCTS:
            conn.execute(
                "INSERT OR REPLACE INTO products VALUES (?, ?)",
                (pid, name),
            )
            conn.execute(
                "INSERT OR REPLACE INTO prices VALUES (?, ?, ?)",
                (pid, price, 1),
            )
            conn.execute(
                "INSERT OR REPLACE INTO inventory VALUES (?, ?)",
                (pid, stock),
            )

        conn.execute(
            "INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?)",
            ("ORD001", "demo_user_001", "P001", "shipped"),
        )


if __name__ == "__main__":
    generate_documents()
    generate_database()

    docs = list(DOCS.rglob("*.md"))
    print(f"Knowledge documents: {len(docs)}")
    print(f"Database created: {DB}")
