"""Day30 release checks are offline and must never modify previous results."""
import copy
import hashlib
import json

import pytest

from scripts.check_day30_release import audit, is_public_https, make_manifest


def dummy_repo(tmp_path):
    from scripts.check_day30_release import REQUIRED
    root = tmp_path
    for relative in REQUIRED:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    graph = root / "src/shopmate_agent/shopmate_graph.py"
    graph.write_text("# fixed Day29 implementation\n", encoding="utf-8")
    fp = hashlib.sha256(graph.read_bytes()).hexdigest()
    holdout = {"metrics": {"total": 20, "task_success": 17,
                           "failures": [{"id": i} for i in ("H05", "H18", "H19")]},
               "human_review": {"status": "complete", "reviewed": 20}}
    smoke = {"task_count": 5, "passed": 5, "failed": 0,
             "implementation_sha256": fp,
             "cases": [{"case_id": f"S{i:02d}", "passed": True} for i in range(1, 6)]}
    perf = {"run_configuration": {"concurrency": 20},
            "metrics": {"total_requests": 40, "completed_requests": 4,
                        "status_counts": {"503": 36}, "actual_model_tokens": None}}
    for name, obj in (("day26/performance", perf), ("day27/holdout", holdout), ("day29/smoke", smoke)):
        (root / "reports" / f"{name}.json").write_text(json.dumps(obj), encoding="utf-8")
    (root / "README.md").write_text("17/20 H05 H18/H19 规则式 LangGraph", encoding="utf-8")
    return root


def test_preflight_passes_on_consistent_reports(tmp_path):
    assert audit(dummy_repo(tmp_path)) == []


def test_rejects_changed_day27_history(tmp_path):
    root = dummy_repo(tmp_path)
    path = root / "reports/day27/holdout.json"
    d = json.loads(path.read_text()); d["metrics"]["task_success"] = 19
    path.write_text(json.dumps(d))
    assert any("historical holdout" in e for e in audit(root))


def test_rejects_unverified_smoke(tmp_path):
    root = dummy_repo(tmp_path)
    path = root / "reports/day29/smoke.json"
    d = json.loads(path.read_text()); d["cases"][3]["passed"] = False
    path.write_text(json.dumps(d))
    assert any("smoke cases" in e for e in audit(root))


def test_rejects_stale_code_fingerprint(tmp_path):
    root = dummy_repo(tmp_path)
    (root / "src/shopmate_agent/shopmate_graph.py").write_text("changed graph")
    assert any("fingerprint" in e for e in audit(root))


def test_rejects_overload_result_polishing(tmp_path):
    root = dummy_repo(tmp_path)
    path = root / "reports/day26/performance.json"
    d = json.loads(path.read_text()); d["metrics"]["status_counts"]["503"] = 0
    path.write_text(json.dumps(d))
    assert any("overload" in e for e in audit(root))

@pytest.mark.parametrize("url,expected", [
    ("https://example.ngrok-free.dev", True),
    ("https://demo.example.com/", True),
    ("http://example.com", False),
    ("http://127.0.0.1:8080", False),
    ("https://localhost:8080", False),
    ("https://192.168.1.10", False),
    ("https://user:password@example.com", False),
    ("https://demo.example.com?authtoken=secret", False),
    ("https://demo.example.com/admin", False),
])
def test_public_link_validation(url, expected):
    assert is_public_https(url) is expected


def test_manifest_includes_real_sources_and_pending_checks(tmp_path):
    root = dummy_repo(tmp_path)
    result = make_manifest(root, "https://public.example.com", timestamp="2026-10-15T00:00:00Z")
    assert result["evidence"]["day27_frozen_holdout"]["passed"] == 17
    assert result["evidence"]["day29_http_sse_smoke"]["passed"] == 5
    assert result["evidence"]["day26_20_concurrency"]["http_503"] == 36
    assert "PENDING" in result["external_checks"]
    assert result["demo_url"] == "https://public.example.com"


def test_manifest_never_claims_model_usage(tmp_path):
    d = make_manifest(dummy_repo(tmp_path), "https://demo.example.com")
    assert "not live answering" in d["architecture_scope"]
    assert "Synthetic" in d["data_scope"]
