"""Day 25 liveness / readiness probes for the existing ShopMate deployment.

Avoid returning stack traces or credentials in public probe responses.
"""
import json
import logging
import sqlite3
from pathlib import Path

import numpy as np
import psycopg
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from shopmate_agent.embedding_index import ROOT, META_FILE, VECTOR_FILE

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _sqlite_check(path: Path, table: str) -> None:
    # Opening read-only prevents silently creating an absent DB.
    if not path.is_file():
        raise FileNotFoundError(path.name)
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2) as conn:
        conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()


def _business_check() -> None:
    _sqlite_check(ROOT / "data/shopmate.db", "orders")


def _sessions_check() -> None:
    _sqlite_check(ROOT / "data/sessions.db", "sessions")


def _expected_index_size() -> int:
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    if meta.get("dimension") != 512 or not meta.get("chunks"):
        raise ValueError("Unexpected index metadata")
    return len(meta["chunks"])


def _local_vectors_check() -> None:
    size = _expected_index_size()
    with np.load(VECTOR_FILE, allow_pickle=False) as f:
        vectors = f["vectors"]
    if vectors.shape != (size, 512) or not np.isfinite(vectors).all():
        raise ValueError("Local vector index unavailable")


def _pgvector_check() -> None:
    size = _expected_index_size()
    # libpq uses PGHOST/PGUSER/PGPASSWORD/PGDATABASE from app environment.
    with psycopg.connect(connect_timeout=3) as conn:
        count, lo, hi = conn.execute("""
            SELECT COUNT(*), MIN(vector_dims(embedding)), MAX(vector_dims(embedding))
            FROM knowledge_vectors
        """).fetchone()
    if (count, lo, hi) != (size, 512, 512):
        raise ValueError("PostgreSQL vector index not ready")


@router.get("/health/live")
def live():
    """Process is accepting HTTP requests; does not require the database."""
    return {"status": "alive"}


@router.get("/health/ready")
def ready():
    """All resources required for the demo are accessible."""
    checks = {}
    for name, probe in (
        ("business_db", _business_check),
        ("sessions_db", _sessions_check),
        ("local_vectors", _local_vectors_check),
        ("pgvector", _pgvector_check),
    ):
        try:
            probe()
            checks[name] = "ok"
        except Exception as exc:
            checks[name] = "failed"
            # Only a category and exception type; never log DB URLs or secrets.
            logger.warning("health probe failed: %s (%s)", name, type(exc).__name__)

    if "failed" in checks.values():
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks},
        )
    return {"status": "ready", "checks": checks}
