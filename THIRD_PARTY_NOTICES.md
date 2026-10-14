# Third-party notices / 第三方许可与服务说明

This project's MIT license only covers original repository code whose contributors have rights to license it. Third-party software, model weights, container images, and external services are governed by their **own** licenses and terms; no provider API key or commercial right is granted here.

| Dependency or service | Purpose | Upstream licensing / terms | Redistribution within this repo |
|---|---|---|---|
| [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5) | 512-D local embedding, pinned revision `7999e1d3359715c523056ef9478215996d62a620` | Model card reports **MIT** | Weights are downloaded separately; not committed |
| [BAAI/bge-reranker-base](https://huggingface.co/BAAI/bge-reranker-base) | Optional offline reranking experiment | Model card reports **MIT** | Weights not committed |
| [pgvector](https://github.com/pgvector/pgvector) / [PostgreSQL](https://www.postgresql.org/about/licence/) | Containerized durable vectors | Check corresponding PostgreSQL/pgvector licenses and image notices | Docker pulls image independently |
| [Caddy](https://github.com/caddyserver/caddy) | Local Basic Auth / reverse proxy | Check Caddy LICENSE and the selected image's notices | Docker pulls image independently |
| [FastAPI](https://github.com/fastapi/fastapi), [LangGraph](https://github.com/langchain-ai/langgraph), [uv](https://github.com/astral-sh/uv), [NumPy](https://numpy.org/) | Python app and tools | Respect each project's upstream LICENSE | Resolved via Python packaging |
| [ngrok](https://ngrok.com/terms) | Optional HTTPS demo tunnel | Commercial service terms; **not open-sourced or relicensed by this repository** | No ngrok binary, account or authtoken committed |

## Synthetic corpus and data

All 30 Markdown files under `data/knowledge/` are synthetic ShopMate examples produced from `scripts/seed_demo_data.py`. These are for learning and reproducible evaluation, not real merchant policies. Item prices, inventory and order status are likewise demo values. Do not use them for a real store without replacing and validating authoritative data.

GitHub Actions uses upstream actions whose versions and licensing should be reviewed at release time. Review dependency and model licenses again when updating images, wheels, or model revisions.

## Safe release checklist

- [ ] Confirm maintainers own or have rights to license the repository code as MIT; change the copyright line if required.
- [ ] Confirm no secrets or actual customer data are tracked (`.env`, `.env.day25`, SQLite databases, ngrok tokens).
- [ ] Keep LICENSE / this notice / relevant model attribution with released source.
- [ ] Do not claim that any third-party model weights or external service are governed by our LICENSE.
