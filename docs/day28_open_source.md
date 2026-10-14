# Day 28 — Open-source delivery and offline CI

Exact spreadsheet row: README structure, License, third-party notice, CI, API examples; add architecture diagram, deployment, `.env.example`, synthetic corpus notes, 3-minute demo. Verify README home page, demo and evaluation links; clean environment can start, CI passes, demo includes a failure/refusal.

## Incremental files (Day24–Day27 runtime untouched)

- `README.md` (previously empty): architecture, reproducible startup, concrete examples, real evaluation metrics and limitations.
- `LICENSE` (MIT **draft default**; owner must confirm copyright and license).
- `THIRD_PARTY_NOTICES.md`: models/containers/runtime/services and their independent terms.
- `docs/day28_architecture.md`: Mermaid plus distinction between live rules/policy path and offline pgvector index.
- `docs/day28_api_examples.md`: Windows commands for health checks and raw SSE.
- `docs/day28_demo.md`: exact 3-minute route, successful citation, anonymous refusal, known H18 miss.
- `.github/workflows/offline-ci.yml`: offline **key-path** tests, no LLM calls or model downloads.
- `scripts/check_day28_repo.py`: stdlib repo, report, corpus and documentation checks.
- `tests/test_day28_open_source.py`: test repository delivery artifacts.

## Step 1. Verify the release surface

```powershell
cd E:\shopmate\shopmate-agent
uv run python scripts/check_day28_repo.py
uv run python -m pytest tests/test_day28_open_source.py -v
uv run python -m pytest -q
```

Keep the existing reports (`reports/day26/performance.json`, `reports/day27/holdout.json`) and failures. The README **does not** claim a model generates current answers.

## Step 2. Verify fresh Docker deployment (non-destructive)

A clean Git clone should contain `data/knowledge/`, `data/index/chunks_meta.json`, all Compose files, and `.env.example`. `.env`, `data/*.db` and `chunks.npz` are intentionally untracked. On a separate folder or machine, copy `.env.example` to `.env`, set a **local** password, and run `docker compose up -d --build`. First-time model download may be slow, and Docker should have enough storage. Check App at `127.0.0.1:8000` and 30/512 pgvector vectors. Don't recreate the primary environment just to prove clean startup; use a disposable clone and avoid conflicting `8000/8080` ports if testing on the same laptop.

CI is **not** a Docker E2E deployment test; smoke CI is isolated from large model and Docker pulls.

## Step 3. CI details and limitations

The GitHub Actions workflow runs on push/PR and uses Python 3.12, a seeded **synthetic** SQLite DB, `scripts/check_day28_repo.py`, and selected offline pytest files for docs/corpus, graph, SSE, health, rate limiter and evaluation. The workflow installs only dependencies needed for this subset, not `torch` or `sentence-transformers`, because runtime code lazy-loads the ML model in offline indexing paths. This reduces CI size and avoids model-weight downloads. **It does not prove the full pytest suite or public ngrok connectivity**; retain separate local full-suite and fresh Docker validation.

CI is considered passed only when the **actual** Actions run on GitHub is green. Do not mark it successful merely because the workflow YAML exists or local pytest passes.

GitHub workflow: https://github.com/theark-coder/shopmate-agent/actions/workflows/offline-ci.yml

## Step 4. Deal with Day 27 human score discrepancy

Source report recorded automatic 17/20, human 18/20, disagreement **H05**. `现在的发货政策是什么？` should not be a generic clarification. Recommend modifying **only H05** `manual_verdict=FAIL`, `review_notes=明确的配送政策问题被误判为澄清；未给出政策引用`, running `uv run python scripts/eval_day27.py --mode finalize`, committing updated report/CSV. Do **not** rerun the 20 questions or pretend the measured underlying model has improved.

## Step 5. Push, validate links, record evidence

```powershell
git add README.md LICENSE THIRD_PARTY_NOTICES.md .github/workflows/offline-ci.yml docs/day28_architecture.md docs/day28_api_examples.md docs/day28_demo.md docs/day28_open_source.md scripts/check_day28_repo.py tests/test_day28_open_source.py
# If you corrected H05, include the original human review and updated report:
git add reports/day27/human_review.csv reports/day27/holdout.json
git commit -m "docs: open source ShopMate with architecture offline CI and demo"
git push origin main
```

Open the GitHub homepage, architecture Mermaid, Day27 report, and Actions workflow; run local 3-minute demo through Caddy. Confirm public preview's anonymous-order refusal and H18 **known failure**. A GitHub Actions red run is a blocker and should be diagnosed, not waved through.

## Acceptance

Clean clone startup instructions are workable; CI green; README has architecture and API examples, synthetic corpus notice, license/third-party notice; verified report links; 3-minute demo has citations and one failure/refusal; HTTPS preview available when tunnel runs. No fake LLM usage, no overwritten databases and no real account credentials in Git.
