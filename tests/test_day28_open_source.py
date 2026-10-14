"""Day28 publication tests; safe and offline (no HTTP, Docker or model weights)."""
from pathlib import Path

from scripts.check_day28_repo import validate, ROOT


def test_repository_preflight_passes():
    assert validate() == []


def test_license_and_model_notices_exist():
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "BAAI/bge-small-zh-v1.5" in notices
    assert "ngrok" in notices
    assert "own" in notices.lower()  # No blanket license grant to dependencies


def test_mermaid_keeps_pgvector_off_live_answer_path():
    arch = (ROOT / "docs/day28_architecture.md").read_text(encoding="utf-8")
    assert "```mermaid" in arch
    assert "pgvector" in arch
    assert "Current customer response paths do not perform online pgvector retrieval" in arch


def test_demo_has_three_minute_walkthrough_and_known_failure():
    demo = (ROOT / "docs/day28_demo.md").read_text(encoding="utf-8")
    assert "00:00" in demo and "03:00" in demo
    assert "ORD001" in demo and "H18" in demo and "policy-returns" in demo


def test_api_example_includes_sse_and_health_probes():
    api = (ROOT / "docs/day28_api_examples.md").read_text(encoding="utf-8")
    for expected in ("/health/live", "/health/ready", "/api/chat/stream", "curl.exe -N", "policy-returns"):
        assert expected in api


def test_ci_is_offline_key_path_with_no_model_dependency():
    ci = (ROOT / ".github/workflows/offline-ci.yml").read_text(encoding="utf-8")
    assert "actions/checkout@" in ci
    assert "pytest" in ci
    assert "test_day27_eval.py" in ci
    assert "test_day28_open_source.py" in ci
    assert "seed_demo_data.py" in ci
    assert "torch" not in ci
    assert "api_key" not in ci.lower()


def test_readme_is_not_empty_and_exposes_real_failures():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in ("17/20", "H05", "H18", "H19", "LICENSE", ".env.example", "docker compose", "规则式 LangGraph"):
        assert needle in readme


def test_license_guardrails_are_documented():
    docs = (ROOT / "docs/day28_open_source.md").read_text(encoding="utf-8")
    assert "CI" in docs and "GitHub" in docs
    assert "H05" in docs and "manual_verdict=FAIL" in docs
