
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_FILE = ROOT / "data" / "eval" / "hybrid_dev.json"


def best_relevant_rank(doc_ids, relevant_ids):
    """返回排名最靠前的相关文档位置，未命中返回4。"""
    for rank, doc_id in enumerate(doc_ids, start=1):
        if doc_id in relevant_ids:
            return rank
    return 4


def print_cases(title, cases, limit=2):
    """打印某一类案例，最多展示2条。"""
    print(f"\n{'=' * 50}")
    print(f"{title}：共 {len(cases)} 条")
    print("=" * 50)

    if not cases:
        print("没有符合条件的案例")
        return

    for row in cases[:limit]:
        print(f"\n任务ID：{row['task_id']}")
        print(f"问题：{row['query']}")
        print(f"相关文档：{row['relevant_doc_ids']}")

        print(
            "Dense Top3：",
            row["dense"]["doc_ids"],
        )
        print(
            "Hybrid Top3：",
            row["hybrid"]["doc_ids"],
        )

        print(
            "Dense Recall@3：",
            row["dense"]["recall"],
        )
        print(
            "Hybrid Recall@3：",
            row["hybrid"]["recall"],
        )
        print(
            "Recall 变化：",
            row["delta_recall"],
        )
        print(
            "最佳相关文档排名变化：",
            row["rank_change"],
        )


def main():
    result = json.loads(
        RESULT_FILE.read_text(encoding="utf-8")
    )

    records = result["records"]

    for row in records:
        old_rank = best_relevant_rank(
            row["dense"]["doc_ids"],
            row["relevant_doc_ids"],
        )

        new_rank = best_relevant_rank(
            row["hybrid"]["doc_ids"],
            row["relevant_doc_ids"],
        )

        # 正数代表相关文档排名提升
        row["rank_change"] = old_rank - new_rank

    recall_improved = [
        row for row in records
        if row["delta_recall"] > 0
    ]

    recall_regressed = [
        row for row in records
        if row["delta_recall"] < 0
    ]

    rank_improved = [
        row for row in records
        if row["rank_change"] > 0
    ]

    rank_regressed = [
        row for row in records
        if row["rank_change"] < 0
    ]

    print_cases("Recall@3 提升案例", recall_improved)
    print_cases("Recall@3 退步案例", recall_regressed)
    print_cases("相关文档排名提升案例", rank_improved)
    print_cases("相关文档排名退步案例", rank_regressed)


if __name__ == "__main__":
    main()
