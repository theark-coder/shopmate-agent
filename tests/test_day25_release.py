"""Day 25 offline tests; no public URL or Docker daemon needed."""
from pathlib import Path

from fastapi.testclient import TestClient

from shopmate_agent import health_api
from shopmate_agent.public_demo import app

ROOT = Path(__file__).resolve().parents[1]


def _mock_ready(monkeypatch, failed=None):
    funcs = (
        "_business_check", "_sessions_check",
        "_local_vectors_check", "_pgvector_check",
    )
    for f in funcs:
        def run(name=f):
            if name == failed:
                raise RuntimeError("PRIVATE_CONNECTION_DETAILS")
        monkeypatch.setattr(health_api, f, run)


def test_liveness_needs_no_database():
    result = TestClient(app).get('/health/live')
    assert result.status_code == 200
    assert result.json() == {"status": "alive"}


def test_readiness_all_checks_ok(monkeypatch):
    _mock_ready(monkeypatch)
    result = TestClient(app).get('/health/ready')
    assert result.status_code == 200
    assert list(result.json()['checks'].values()) == ['ok']*4


def test_readiness_503_identifies_failed_check_without_secrets(monkeypatch):
    _mock_ready(monkeypatch, failed='_pgvector_check')
    result = TestClient(app).get('/health/ready')
    assert result.status_code == 503
    assert result.json()['checks']['pgvector'] == 'failed'
    assert 'PRIVATE_CONNECTION_DETAILS' not in result.text


def test_readiness_503_when_sessions_unavailable(monkeypatch):
    _mock_ready(monkeypatch, failed='_sessions_check')
    result = TestClient(app).get('/health/ready')
    assert result.status_code == 503
    assert result.json()['checks']['sessions_db'] == 'failed'


def test_demo_page_presets_and_sse_client():
    resp = TestClient(app).get('/day25')
    assert resp.status_code == 200
    assert '七天退货有什么条件？' in resp.text
    assert '商品P001多少钱？' in resp.text
    assert '订单ORD001现在什么状态？' in resp.text
    assert 'answer_delta' in resp.text


def test_proxy_config_blocks_private_routes_and_authenticates():
    conf = (ROOT / 'deploy/Caddyfile.day25').read_text(encoding='utf-8')
    assert 'path /api/secure /api/secure/*' in conf
    assert 'basic_auth' in conf
    assert 'reverse_proxy app:8000' in conf
    assert 'flush_interval -1' in conf


def test_compose_override_configures_healthcheck_and_proxy():
    conf = (ROOT / 'compose.day25.yaml').read_text(encoding='utf-8')
    assert 'shopmate_agent.public_demo:app' in conf
    assert '/health/ready' in conf
    assert 'service_healthy' in conf
    assert '127.0.0.1:8080:80' in conf
