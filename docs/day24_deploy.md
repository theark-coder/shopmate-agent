# ShopMate Day 24: App + PostgreSQL/pgvector

## Scope

- **HTTP app**: existing FastAPI/SSE + LangGraph; live business data and conversations continue using SQLite as designed on Days 20–23.
- **pgvector**: an additional durable, real 512-dimensional copy of the Day 13 embedding index. This day does **not** silently switch the production retrieval path to PostgreSQL.
- **Persistence**: `./data:/app/data` bind mount stores SQLite, policies, and `chunks.npz`; `pg_data` named volume stores PostgreSQL; `hf_cache` named volume saves model downloads.
- **Migration**: `deploy/migrations/001_vectors.sql`, version tracked by `schema_migrations`.
- The `init` service runs a one-shot idempotent bootstrap; first run may download the pinned BGE model on CPU if `data/index/chunks.npz` is absent.

## Fresh start on Windows PowerShell

1. Install and start Docker Desktop (Linux containers), and verify `docker compose version`.
2. From the project root, run `uv add 'psycopg[binary]>=3.2,<4'` and ensure `uv.lock` is updated; this is necessary before a Docker build using `uv sync --locked`.
3. `Copy-Item .env.example .env` (local only). Edit the local credentials as appropriate. Do not commit `.env`.
4. `docker compose config --quiet`
5. `docker compose up -d --build` 
6. `docker compose logs -f init` (Ctrl+C exits log viewer, not containers). First start can take significant time due to Python dependencies and model download. If `init` fails, use `docker compose logs init` and do not assume the app is ready.
7. `docker compose ps`. Open <http://127.0.0.1:8000> after `app` is running.

## Database and index check

```powershell
docker compose exec -T db psql -U shopmate -d shopmate -c 'SELECT COUNT(*) AS total, MIN(vector_dims(embedding)) AS dimension FROM knowledge_vectors;'
docker compose exec -T db psql -U shopmate -d shopmate -c 'SELECT chunk_id, doc_id FROM knowledge_vectors ORDER BY embedding <=> (SELECT embedding FROM knowledge_vectors ORDER BY chunk_id LIMIT 1) LIMIT 3;'
```

Expected approximately 30 imported real vectors, dimension 512; exact count is controlled by `chunks_meta.json`.

## Persistence test: test beyond a simple restart

Create a **manual sentinel not created by the init service**:

```powershell
docker compose exec -T db psql -U shopmate -d shopmate -c "INSERT INTO deployment_probe(key,note) VALUES ('restart-check','must survive') ON CONFLICT (key) DO UPDATE SET note=EXCLUDED.note;"
docker compose down
docker compose up -d
docker compose exec -T db psql -U shopmate -d shopmate -c "SELECT key,note FROM deployment_probe WHERE key='restart-check';"
docker compose exec -T db psql -U shopmate -d shopmate -c 'SELECT COUNT(*) FROM knowledge_vectors;'
```

Check that `'restart-check'` is still present and that the vector count remains unchanged. The original SQLite data and `chunks.npz` live under local `data/`, so they remain after recreating containers.

With the **local demo token only**, also confirm Day 21's SQLite session remains available after container recreation:

```powershell
curl.exe -s -H "Authorization: Bearer local-a-23" http://127.0.0.1:8000/api/secure/sessions/day24-persist
```

The result should include the preserved `policy-returns` source ID. This demo token must not be used for a public deployment.

## Safety and troubleshooting

- Do **not** use `docker compose down -v`: the `-v` option deletes PostgreSQL and model cache named volumes.
- `docker compose down` alone keeps the named volumes.
- `docker compose config --quiet` catches config and environment interpolation errors.
- `docker compose logs db init app` helps identify database readiness, migration, model downloads, and app startup problems.
- `data/` is excluded from the image and mounted from the host. Never commit `.env`, `.db`, `.npz` or logs.
- Expose only 127.0.0.1:8000 for this local exercise; HTTPS / proxy / public access belong to Day 25.
- First build can be resource-intensive because the existing project includes machine-learning libraries. Ensure Docker Desktop has sufficient disk space and memory.
