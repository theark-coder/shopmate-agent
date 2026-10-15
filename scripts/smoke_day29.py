"""Day29 five-task reviewer smoke test: HTTP + actual SSE complete/citations.

Run against the *local-only* FastAPI port after rebuilding Day26 compose overlay.
Records no credentials or raw private database facts; synthetic questions only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = (
    ('S01', '七天退货有什么条件？', 'policy'),
    ('S02', '商品P001多少钱？', 'product'),
    ('S03', '订单ORD001现在什么状态？', 'anonymous_order'),
    ('S04', '七天退货过期，能破例退款吗？', 'human_handoff'),
    ('S05', '你好，可以帮我吗？', 'clarification'),
)


def parse_frame(frame: str) -> tuple[str, dict] | None:
    event = ''
    data = []
    for line in frame.splitlines():
        if line.startswith('event:'):
            event = line[6:].strip()
        elif line.startswith('data:'):
            data.append(line[5:].strip())
    if not event or not data:
        return None
    return event, json.loads(''.join(data))


def grade(kind: str, events: list[tuple[str, dict]], answer: str) -> list[str]:
    names = [name for name, _ in events]
    errors = []
    if 'start' not in names:
        errors.append('missing_start')
    if 'answer_delta' not in names:
        errors.append('missing_answer_delta')
    if 'error' in names:
        errors.append('sse_error')
    complete = next((data for name, data in events if name == 'complete'), None)
    if complete is None:
        errors.append('missing_complete')
        return errors
    citations = complete.get('citations', [])
    if kind == 'policy':
        if 'retrieval' not in names or 'policy-returns' not in citations:
            errors.append('missing_policy_source')
    elif kind == 'product':
        if 'tool' not in names or 'db:products:P001' not in citations or '399.00' not in answer:
            errors.append('missing_structured_product_facts')
    elif kind == 'anonymous_order':
        if citations or any(x in answer.lower() for x in ('shipped', '已发货', '已签收')):
            errors.append('anonymous_order_leak')
        if '不能回答' not in answer and '未核实' not in answer:
            errors.append('missing_safe_refusal')
    elif kind == 'human_handoff':
        if citations or '人工' not in answer or '无法直接批准' not in answer:
            errors.append('missing_human_handoff')
    elif kind == 'clarification':
        if citations or '请补充' not in answer:
            errors.append('missing_clarification')
    return errors


def invoke(client: httpx.Client, url: str, case: tuple[str, str, str]) -> dict:
    case_id, question, kind = case
    started = time.perf_counter()
    events: list[tuple[str, dict]] = []
    status = None
    error = None
    try:
        with client.stream('POST', url, json={'question': question}) as resp:
            status = resp.status_code
            if status != 200:
                error = f'http_{status}'
            else:
                if not resp.headers.get('content-type', '').startswith('text/event-stream'):
                    error = 'not_sse'
                payload: list[str] = []
                for line in resp.iter_lines():
                    if line == '':
                        if payload:
                            parsed = parse_frame('\n'.join(payload))
                            if parsed:
                                events.append(parsed)
                            payload = []
                    else:
                        payload.append(line)
                if payload:
                    parsed = parse_frame('\n'.join(payload))
                    if parsed:
                        events.append(parsed)
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        error = type(exc).__name__
    answer = ''.join(item.get('text', '') for name, item in events if name == 'answer_delta')
    issues = [error] if error else grade(kind, events, answer)
    complete = next((data for name, data in events if name == 'complete'), {})
    return {
        'case_id': case_id,
        'kind': kind,
        'question': question,
        'passed': not issues,
        'issues': issues,
        'http_status': status,
        'events': [name for name, _ in events],
        'citations': complete.get('citations', []),
        'answer_excerpt': answer[:240],
        'duration_ms': round((time.perf_counter()-started)*1000, 2),
    }


def run(base_url: str, *, timeout: float = 30) -> dict:
    url = base_url.rstrip('/') + '/api/chat/stream'
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        cases = [invoke(client, url, case) for case in QUESTIONS]
    sha = hashlib.sha256((ROOT / 'src/shopmate_agent/shopmate_graph.py').read_bytes()).hexdigest()
    return {
        'run_utc': datetime.now(timezone.utc).isoformat(),
        'target': base_url,
        'environment': 'local-only app endpoint, Day26 middleware, real HTTP SSE',
        'implementation_sha256': sha,
        'task_count': len(cases),
        'passed': sum(x['passed'] for x in cases),
        'failed': sum(not x['passed'] for x in cases),
        'cases': cases,
        'scope': 'first-visit five-task smoke only; not a rerun of Day27 frozen holdout',
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--output', default='reports/day29/smoke.json')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    data = run(args.url, timeout=args.timeout)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Day29 first-visit smoke: {data['passed']}/{data['task_count']} PASS; report={output}")
    for c in data['cases']:
        print(c['case_id'], 'PASS' if c['passed'] else 'FAIL', ','.join(c['issues']))
    if data['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
