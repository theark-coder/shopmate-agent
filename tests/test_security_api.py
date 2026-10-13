
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from shopmate_agent import security_api as sec
from shopmate_agent.stream_api import app


@pytest.fixture
def clients(tmp_path, monkeypatch):
    db = tmp_path / "shopmate.db"
    sessions = tmp_path / "sessions.db"

    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                status TEXT NOT NULL
            );

            INSERT INTO products VALUES
                ('P001', '耳机'),
                ('P002', '键盘');

            INSERT INTO orders VALUES
                ('ORD001', 'demo_user_001', 'P001', 'shipped');
        """)

    sec.seed_demo_security(db, sessions)

    monkeypatch.setattr(sec, "DB_FILE", db)
    monkeypatch.setattr(sec, "SESSION_DB", sessions)

    monkeypatch.setenv(
        "SHOPMATE_DEMO_TOKENS_JSON",
        json.dumps({
            "token-a": {
                "user_id": "demo_user_001",
                "merchant_id": "merchant-a",
            },
            "token-b": {
                "user_id": "demo_user_002",
                "merchant_id": "merchant-b",
            },
        }),
    )

    client = TestClient(app)

    def ask(token, path):
        return client.get(
            path,
            headers={
                "Authorization": f"Bearer {token}"
            },
        )

    return client, ask


def test_no_auth_cannot_read_order(clients):
    client, _ = clients

    response = client.get(
        "/api/secure/orders/ORD001"
    )

    assert response.status_code == 401


def test_users_can_read_their_own_orders(clients):
    _, ask = clients

    a = ask("token-a", "/api/secure/orders/ORD001")
    b = ask("token-b", "/api/secure/orders/ORD002")

    assert a.status_code == 200
    assert a.json()["status"] == "shipped"

    assert b.status_code == 200
    assert b.json()["status"] == "pending"


def test_cross_owner_and_merchant_are_denied(clients):
    _, ask = clients

    a = ask("token-a", "/api/secure/orders/ORD002")
    b = ask("token-b", "/api/secure/orders/ORD001")
    missing = ask(
        "token-b",
        "/api/secure/orders/ORD999",
    )

    assert a.status_code == 404
    assert b.status_code == 404
    assert missing.status_code == 404

    # 不通过响应暴露订单是否存在
    assert a.text == missing.text


def test_merchant_product_isolation(clients):
    _, ask = clients

    own = ask("token-a", "/api/secure/products/P001")
    other = ask("token-b", "/api/secure/products/P001")
    reverse = ask("token-a", "/api/secure/products/P002")

    assert own.status_code == 200
    assert other.status_code == 404
    assert reverse.status_code == 404


def test_prompt_injection_cannot_change_permissions(clients):
    _, ask = clients

    product = ask(
        "token-a",
        "/api/secure/products/P001",
    )

    description = product.json()["description"]

    assert "忽略权限" in description

    # 文案要求切换商家，但服务端权限不变
    forbidden = ask(
        "token-a",
        "/api/secure/orders/ORD002",
    )

    assert forbidden.status_code == 404


def test_session_owner_isolation(clients):
    _, ask = clients

    own = ask(
        "token-a",
        "/api/secure/sessions/day23-session-a",
    )
    foreign = ask(
        "token-b",
        "/api/secure/sessions/day23-session-a",
    )

    assert own.status_code == 200
    assert foreign.status_code == 404


def test_client_cannot_choose_identity(clients):
    _, ask = clients

    forged = ask(
        "token-a",
        "/api/secure/orders/ORD002"
        "?user_id=demo_user_002"
        "&merchant_id=merchant-b",
    )

    invalid = ask(
        "invalid-token",
        "/api/secure/me",
    )

    assert forged.status_code == 404
    assert invalid.status_code == 401
