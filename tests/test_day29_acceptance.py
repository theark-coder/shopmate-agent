"""Day29 handoff regression tests. No public tunnel, paid model or production data."""
from pathlib import Path

from fastapi.testclient import TestClient

from shopmate_agent.shopmate_graph import build_graph, needs_policy_handoff
from shopmate_agent.day26_app import app
from scripts.smoke_day29 import QUESTIONS, grade, parse_frame

ROOT = Path(__file__).resolve().parents[1]


def test_h18_exception_routes_to_human_without_auto_approval():
    graph = build_graph()
    state = graph.invoke({'question': '七天退货过期，能破例退款吗？', 'user_id': None})
    assert state['intent'] == 'handoff'
    assert 'human_handoff' in state['trace']
    assert '人工' in state['answer'] and '无法直接批准' in state['answer']
    assert state['citations'] == []


def test_h19_warranty_exception_routes_to_human():
    state = build_graph().invoke({'question': '保修超过期限可以特殊批准吗？', 'user_id': None})
    assert state['intent'] == 'handoff'
    assert 'human_handoff' in state['trace']
    assert state['citations'] == []


def test_fallback_does_not_grant_access_to_private_order():
    state = build_graph().invoke({'question': '订单ORD001现在什么状态？', 'user_id': None})
    assert 'shipped' not in state['answer']
    assert state['citations'] == []


def test_policy_and_product_paths_still_work():
    graph = build_graph()
    policy = graph.invoke({'question': '七天退货有什么条件？', 'user_id': None})
    product = graph.invoke({'question': '商品P001多少钱？', 'user_id': None})
    assert 'policy-returns' in policy['citations']
    assert 'db:products:P001' in product['citations']


def test_exception_detector_is_narrow_and_does_not_auto_approve():
    assert needs_policy_handoff('退款政策的特殊情况，可以破例由人工批准吗？')
    assert not needs_policy_handoff('七天退货有什么条件？')
    assert not needs_policy_handoff('你好，可以帮我吗？')


def test_http_sse_handoff_has_complete_event_and_no_citations():
    with TestClient(app) as client:
        response = client.post('/api/chat/stream', json={'question': '七天退货过期，能破例退款吗？'})
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    assert 'event: answer_delta' in response.text
    assert 'event: complete' in response.text
    assert '人工' in response.text
    assert '"citations": []' in response.text
    assert 'event: error' not in response.text


def test_five_presets_visible_on_default_caddy_landing_page():
    page = (ROOT / 'web/day25.html').read_text(encoding='utf-8')
    for _, question, _ in QUESTIONS:
        assert f'data-question="{question}"' in page
    assert page.count('data-question=') == 5
    caddy = (ROOT / 'deploy/Caddyfile.day25').read_text(encoding='utf-8')
    assert 'rewrite @home /day25' in caddy
    assert 'path /api/secure /api/secure/*' in caddy


def test_sse_grader_detects_handoff_and_leak():
    events = [('start', {}), ('answer_delta', {'text': '人工核实，无法直接批准'}),
              ('complete', {'citations': [], 'status': 'VERIFIED'})]
    assert grade('human_handoff', events, '人工核实，无法直接批准') == []
    assert 'missing_human_handoff' in grade('human_handoff', events, '普通政策说明')
    assert 'anonymous_order_leak' in grade('anonymous_order', events, '订单已经shipped')


def test_sse_parser():
    assert parse_frame('event: complete\ndata: {"citations":[]}\n') == ('complete', {'citations': []})


def test_day27_baseline_retained_as_historical_not_regraded():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'Day 27' in text and '17/20' in text
    assert 'Day 29' in text and 'H18/H19' in text
    assert (ROOT / 'reports/day27/holdout.json').is_file()


def test_ci_covers_day29_offline_regression():
    workflow = (ROOT / '.github/workflows/offline-ci.yml').read_text(encoding='utf-8')
    assert 'tests/test_day29_acceptance.py' in workflow
