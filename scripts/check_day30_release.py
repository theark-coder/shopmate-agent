"""Day 30: dependency-free ShopMate v1.0 release audit and evidence manifest.

No Docker, network, model API, credentials, or GitHub mutations. The day27
held-out report remains historical; day29 smoke is not a replacement for it.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPORTS = (
    "reports/day26/performance.json",
    "reports/day27/holdout.json",
    "reports/day29/smoke.json",
)
REQUIRED = (
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "docs/day28_architecture.md",
    "docs/day28_api_examples.md",
    "docs/day29_acceptance.md",
    "docs/day30_publication.md",
    "docs/day30_release_notes.md",
    "scripts/smoke_day29.py",
    "src/shopmate_agent/shopmate_graph.py",
    "compose.yaml",
    "compose.day25.yaml",
    "compose.day26.yaml",
    *REPORTS,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_public_https(url: str) -> bool:
    """Reject obvious local/secret-bearing URLs; not an online reachability test."""
    try:
        p = urlsplit(url)
        host = p.hostname
        if p.scheme != "https" or not host or p.username or p.password:
            return False
        if p.query or p.fragment or p.path not in ("", "/"):
            return False
        if host.lower() == "localhost" or host.lower().endswith((".localhost", ".local")):
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return "." in host and all(part for part in host.split("."))
        return ip.is_global
    except (ValueError, TypeError):
        return False


def audit(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing artifact: {relative}")
    if errors:
        return errors

    holdout = json.loads((root / REPORTS[1]).read_text(encoding="utf-8"))
    metrics = holdout.get("metrics", {})
    if (metrics.get("total"), metrics.get("task_success")) != (20, 17):
        errors.append("Day27 historical holdout must be reported as 17/20")
    if {item.get("id") for item in metrics.get("failures", [])} != {"H05", "H18", "H19"}:
        errors.append("Day27 failure IDs changed: do not overwrite held-out results")
    manual = holdout.get("human_review", {})
    if manual.get("status") != "complete" or manual.get("reviewed") != 20:
        errors.append("Day27 human review not finalized")

    smoke = json.loads((root / REPORTS[2]).read_text(encoding="utf-8"))
    if (smoke.get("task_count"), smoke.get("passed"), smoke.get("failed")) != (5, 5, 0):
        errors.append("Day29 smoke must be 5/5 before v1.0 release")
    cases = smoke.get("cases", [])
    if len(cases) != 5 or {c.get("case_id") for c in cases} != {
        "S01", "S02", "S03", "S04", "S05"
    } or not all(c.get("passed") is True for c in cases):
        errors.append("Day29 five smoke cases are incomplete")
    actual_source = sha256_file(root / "src/shopmate_agent/shopmate_graph.py")
    if smoke.get("implementation_sha256") != actual_source:
        errors.append("Day29 smoke source fingerprint differs from current graph; rerun smoke against rebuilt app")

    perf = json.loads((root / REPORTS[0]).read_text(encoding="utf-8"))
    pm = perf.get("metrics", {})
    if perf.get("run_configuration", {}).get("concurrency") != 20:
        errors.append("Day26 concurrency evidence missing")
    if (pm.get("total_requests"), pm.get("completed_requests"), pm.get("status_counts", {}).get("503")) != (40, 4, 36):
        errors.append("Day26 historical overload numbers changed; preserve real results")
    if pm.get("actual_model_tokens", "NOT_NULL") is not None:
        errors.append("Do not claim measured LLM token usage for the rules-based demo")

    readme = (root / "README.md").read_text(encoding="utf-8")
    for claim in ("17/20", "H05", "H18/H19", "规则式 LangGraph"):
        if claim not in readme:
            errors.append(f"README missing important limitation or result: {claim}")

    return errors


def make_manifest(root: Path, url: str, *, timestamp: str | None = None) -> dict:
    if not is_public_https(url):
        raise ValueError("Use an HTTPS public homepage URL without credentials, query strings, or paths")
    errors = audit(root)
    if errors:
        raise ValueError("Release preflight failed: " + "; ".join(errors))
    smoke = json.loads((root / REPORTS[2]).read_text(encoding="utf-8"))
    return {
        "project": "shopmate-agent",
        "release": "v1.0.0",
        "prepared_at_utc": timestamp or datetime.now(timezone.utc).isoformat(),
        "repository_url": "https://github.com/theark-coder/shopmate-agent",
        "demo_url": url.rstrip("/"),
        "demo_url_notice": "Temporary ngrok HTTPS; online access depends on host/tunnel uptime. Must verify separately from a second device.",
        "evidence": {
            "day27_frozen_holdout": {"passed": 17, "total": 20, "failed_ids": ["H05", "H18", "H19"]},
            "day29_http_sse_smoke": {"passed": 5, "total": 5, "source_sha256": smoke["implementation_sha256"]},
            "day26_20_concurrency": {"successful": 4, "total": 40, "http_503": 36},
            "report_sha256": {r: sha256_file(root / r) for r in REPORTS},
        },
        "data_scope": "Synthetic products, policies, accounts and orders; no real merchant data",
        "architecture_scope": "Deterministic LangGraph live answers; pgvector used in offline index, not live answering; model tokens not measured",
        "external_checks": "PENDING: user must verify public HTTPS, fresh app restart, rollback, and latest GitHub CI before publishing",
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Prepare a factual v1.0 release evidence manifest")
    parser.add_argument("--demo-url", required=True, help="Currently reachable HTTPS homepage, not a secret")
    parser.add_argument("--output", default="reports/day30/release_manifest.json")
    args = parser.parse_args(argv)
    data = make_manifest(ROOT, args.demo_url)
    dest = ROOT / args.output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Day30 local release evidence: PASS")
    print("Day27 frozen holdout: 17/20; Day29 real SSE smoke: 5/5; Day26 overload: 36/40 HTTP 503")
    print("Manifest:", dest)
    print("PENDING manual checks: public URL, restart/rollback, GitHub green CI, published Release")


if __name__ == "__main__":
    main()
