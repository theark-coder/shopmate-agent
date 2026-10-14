"""Dependency-free Day28 release preflight; verifies facts, not running services."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    ".env.example", ".env.day25.example",
    "Dockerfile", "compose.yaml", "compose.day25.yaml", "compose.day26.yaml",
    ".github/workflows/offline-ci.yml",
    "docs/day28_architecture.md", "docs/day28_demo.md",
    "docs/day28_api_examples.md", "docs/day28_open_source.md",
    "docs/day24_deploy.md", "docs/day25_release.md",
    "docs/day26_performance.md", "docs/day27_evaluation.md",
    "scripts/seed_demo_data.py", "scripts/eval_day27.py",
    "data/index/chunks_meta.json", "eval/day27/holdout.json",
    "reports/day27/holdout.json", "reports/day27/human_review.csv",
    "reports/day26/performance.json", ".gitignore", ".dockerignore",
]


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append("Missing " + relative)
    if errors:
        return errors  # Do not crash on missing files; report actionable failures.

    readme = (root / "README.md").read_text(encoding="utf-8")
    for reference in (
        "docs/day28_architecture.md", "docs/day28_demo.md",
        "docs/day28_api_examples.md", "reports/day27/holdout.json",
        "LICENSE", "THIRD_PARTY_NOTICES.md",
    ):
        if reference not in readme:
            errors.append("README missing link to " + reference)
    if "17/20" not in readme or "H18" not in readme:
        errors.append("README must disclose holdout score and failing H18")

    m = json.loads((root / "data/index/chunks_meta.json").read_text(encoding="utf-8"))
    if m.get("dimension") != 512 or len(m.get("chunks", [])) != 30:
        errors.append("Expected 30 chunks of dimension 512")
    docs = list((root / "data/knowledge").rglob("*.md"))
    if len(docs) != 30:
        errors.append(f"Expected 30 tracked synthetic documents, got {len(docs)}")

    report = json.loads((root / "reports/day27/holdout.json").read_text(encoding="utf-8"))
    metrics = report.get("metrics", {})
    if metrics.get("total") != 20 or metrics.get("task_success") != 17:
        errors.append("README score must match frozen Day27 17/20 baseline")
    actual_failures = {x.get("id") for x in metrics.get("failures", [])}
    if actual_failures != {"H05", "H18", "H19"}:
        errors.append("Day27 failures changed: reconcile README and report")
    if report.get("human_review", {}).get("status") != "complete":
        errors.append("Day27 manual review not finalized")

    with (root / "reports/day27/human_review.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 20 or any(r.get("manual_verdict", "").strip() not in {"PASS", "FAIL"} for r in rows):
        errors.append("Manual review must contain 20 PASS/FAIL rows")

    for ignored in (".env", ".env.day25", "data/index/*.npz", "data/*.db"):
        if ignored not in (root / ".gitignore").read_text(encoding="utf-8"):
            errors.append(".gitignore must ignore " + ignored)

    return errors


def main() -> None:
    errors = validate()
    if errors:
        for message in errors:
            print("FAIL:", message)
        raise SystemExit(1)
    print("Day28 open-source release preflight: PASS")
    print("Checked README links, 30x512 index metadata, 30 synthetic docs, Day27 report/reviews and secret ignores.")


if __name__ == "__main__":
    main()
