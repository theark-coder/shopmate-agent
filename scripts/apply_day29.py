"""Day 29 narrow, idempotent source update.

Patches only known Day 28 source anchors. Preflights all edits before writing;
read existing Git diffs before running if your working tree is dirty.
Run from the ShopMate repository root:
    uv run python scripts/apply_day29.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HANDOFF_DETECTOR = '''def needs_policy_handoff(question: str) -> bool:
    """Exceptions require a human, never an automatic refund/extension."""
    domains = ("退货", "退款", "保修")
    exceptions = (
        "破例", "过期", "超过期限", "超出期限", "特殊批准",
        "特殊情况", "例外批准", "过了退货期限", "延长保修",
    )
    return any(term in question for term in domains) and any(
        term in question for term in exceptions
    )


'''

HANDOFF_NODE = '''def human_handoff(state: ShopState) -> dict:
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


'''


def once(value: str, old: str, new: str, label: str) -> str:
    if new in value:
        return value  # idempotent re-run (old may be a substring of new)
    n = value.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one source anchor, got {n}; aborting without writing")
    return value.replace(old, new, 1)


def patch_graph(source: str) -> str:
    if 'def needs_policy_handoff(question: str)' not in source:
        source = once(source, 'def classify(state: ShopState) -> dict:\n',
                      HANDOFF_DETECTOR + 'def classify(state: ShopState) -> dict:\n', 'insert detector')
    source = once(source,
                  '    q = state["question"]\n\n    if (\n        "订单" in q',
                  '    q = state["question"]\n\n    if needs_policy_handoff(q):\n        intent = "handoff"\n    elif (\n        "订单" in q', 'route exception first')
    source = once(source, '        "product": "product_tool",\n',
                  '        "handoff": "human_handoff",\n        "product": "product_tool",\n',
                  'route lookup')
    if 'def human_handoff(state: ShopState)' not in source:
        source = once(source, 'def clarify(state: ShopState) -> dict:\n',
                      HANDOFF_NODE + 'def clarify(state: ShopState) -> dict:\n', 'insert handoff')
    source = once(source, '    g.add_node("clarify", clarify)\n',
                  '    g.add_node("clarify", clarify)\n    g.add_node("human_handoff", human_handoff)\n',
                  'register node')
    source = once(source, '    g.add_edge("clarify", END)\n',
                  '    g.add_edge("clarify", END)\n    g.add_edge("human_handoff", END)\n',
                  'register terminal edge')
    return source


def patch_stream(source: str) -> str:
    source = once(source,
                  'elif node in ("clarify", "safe_end"):',
                  'elif node in ("clarify", "safe_end", "human_handoff"):',
                  'stream handoff node')
    source = once(source,
                  '                        verified = node == "clarify"',
                  '                        verified = node in ("clarify", "human_handoff")',
                  'stream handoff verified')
    return source


def patch_web(source: str) -> str:
    existing = '<button class="secondary" data-question="订单ORD001现在什么状态？">匿名订单拒答</button>'
    added = (existing + '\n'
             '<button class="secondary" data-question="七天退货过期，能破例退款吗？">政策例外转人工</button>\n'
             '<button class="secondary" data-question="你好，可以帮我吗？">信息不足先澄清</button>')
    return once(source, existing, added, 'five first-visit presets')


def patch_readme(source: str) -> str:
    old = ('| 已知失败 | `七天退货过期，能破例退款吗？` | '
           '**当前尚未正确触发人工转接**；这是一项已记录的问题，非已实现能力 |')
    new = ('| 政策例外转人工（Day 29 修复） | `七天退货过期，能破例退款吗？` | '
           '明确提示需要人工客服核实，不自动批准退款；Day 27 留出集报告保留历史失败 |')
    source = once(source, old, new, 'update README example')
    source = once(source,
                  'H05 政策问题误识别；H18/H19 未触发人工转接；',
                  'H05 政策问题误识别；H18/H19 在 Day 27 冻结版未转人工，Day 29 已修复（以独立冒烟报告验证）；',
                  'update known issues')
    marker = '## 30 秒看价值\n'
    insertion = ('## Day 29 面试官首次访问（5 个预置任务）\n\n'
                 '启动 Day 26 叠加版后在无痕浏览器打开 `http://127.0.0.1:8080`，'
                 '使用本地设置的 `preview` 演示账号。首页包含政策引用、价格库存、'
                 '匿名查单拒答、政策例外转人工、信息不足澄清五个按钮。'
                 '详见 [Day 29 首访验收与冻结指南](docs/day29_acceptance.md)；'
                 '新版本结果见本机生成并提交的 `reports/day29/smoke.json`。'
                 '**Day 27 的 17/20 是修复前冻结基线，不代表 Day 29 最新成绩。**\n\n')
    source = once(source, marker, insertion + marker, 'insert reviewer guide')
    return source


def patch_day28_demo(source: str) -> str:
    # Label historical documentation explicitly rather than rewriting Day 28 results.
    marker = '# Three-minute ShopMate Demo / 三分钟演示脚本\n'
    note = ('\n> 历史版本说明：以下为 Day 28 原始演示脚本。Day 27 冻结评测中的 '
            'H18/H19 当时未正确转人工；Day 29 已添加专门的转人工分支。'
            '请使用 [Day 29 首访验收](day29_acceptance.md) 演示最新五项能力；'
            '原有失败记录仍然保留，不能改写成旧版本成功。\n')
    return once(source, marker, marker + note, 'label historical demo')


def patch_ci(source: str) -> str:
    return once(source, '            tests/test_day28_open_source.py\n',
                '            tests/test_day28_open_source.py\n            tests/test_day29_acceptance.py\n',
                'include Day29 regression in offline CI')


def apply(root: Path = ROOT, *, dry_run: bool = False) -> list[str]:
    targets = {
        'src/shopmate_agent/shopmate_graph.py': patch_graph,
        'src/shopmate_agent/stream_api.py': patch_stream,
        'web/day25.html': patch_web,
        'README.md': patch_readme,
        'docs/day28_demo.md': patch_day28_demo,
        '.github/workflows/offline-ci.yml': patch_ci,
    }
    planned: dict[Path, str] = {}
    for relative, edit in targets.items():
        path = root / relative
        before = path.read_text(encoding='utf-8')
        after = edit(before)
        compile(after, str(path), 'exec') if path.suffix == '.py' else None
        planned[path] = after
    changes = [str(path.relative_to(root)) for path, value in planned.items()
               if path.read_text(encoding='utf-8') != value]
    if not dry_run:
        for path, after in planned.items():
            if path.read_text(encoding='utf-8') != after:
                path.write_text(after, encoding='utf-8')
    return changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Preflight all anchors without writing')
    args = parser.parse_args()
    changes = apply(dry_run=args.check)
    print(('Day29 patch preflight: ' if args.check else 'Day29 patch applied: ')
          + (', '.join(changes) if changes else 'already up to date'))


if __name__ == '__main__':
    main()
