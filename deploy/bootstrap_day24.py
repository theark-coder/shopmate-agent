"""Day 24 one-shot startup: seed SQLite, pinned embeddings, pgvector.

Run in the init container, not on every HTTP request.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import psycopg

from shopmate_agent.embedding_index import (
    ROOT, INDEX_DIR, META_FILE, VECTOR_FILE, normalize,
)
from shopmate_agent.conversation_memory import SessionMemory
from shopmate_agent.security_api import Principal, seed_demo_security


MIGRATION = ROOT / "deploy/migrations/001_vectors.sql"


def vector_literal(vector) -> str:
    arr = np.asarray(vector, dtype=np.float32)
    if arr.shape != (512,) or not np.isfinite(arr).all():
        raise ValueError("Expected a finite 512-dimensional vector")
    if not np.any(arr):
        raise ValueError("Cannot index a zero vector for cosine distance")
    return "[" + ",".join(format(float(v), ".9g") for v in arr) + "]"


def ensure_seed_data():
    sqlite_db = ROOT / "data/shopmate.db"
    if not sqlite_db.exists():
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/seed_demo_data.py")],
            check=True,
            cwd=ROOT,
        )

    policy_file = ROOT / "data/knowledge/policies/returns.md"
    if not policy_file.exists():
        raise RuntimeError(
            "SQLite exists but knowledge files are missing. "
            "Restore data/knowledge instead of resetting business data."
        )

    seed_demo_security()

    # One persistence probe in Day 21's actual SQLite session store.
    owner = Principal("demo_user_001", "merchant-a").session_owner
    memory = SessionMemory()
    try:
        memory.context("day24-persist", owner)
    except KeyError:
        memory.append_turn(
            "day24-persist", owner,
            "Day24 容器重启后还能看到这条消息吗？",
            "可以通过持久化会话读取来验证。",
            ["policy-returns"],
        )


def ensure_pinned_vectors():
    if VECTOR_FILE.exists():
        print(f"Reusing existing vectors: {VECTOR_FILE}")
        return

    if not META_FILE.exists():
        raise RuntimeError(
            "Missing data/index/chunks_meta.json. "
            "Restore committed metadata before bootstrapping."
        )

    # Reconstruct the same embedding model revision as Day 13, no model training.
    from sentence_transformers import SentenceTransformer

    metadata = json.loads(META_FILE.read_text(encoding="utf-8"))
    print("Building missing vectors with pinned revision:", metadata["model_revision"])
    encoder = SentenceTransformer(
        metadata["model_id"],
        revision=metadata["model_revision"],
        device="cpu",
    )
    vectors = normalize(encoder.encode(
        [chunk["text"] for chunk in metadata["chunks"]],
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=False,
    ))
    expected = (len(metadata["chunks"]), metadata["dimension"])
    if vectors.shape != expected:
        raise ValueError(f"Embedding shape {vectors.shape} != {expected}")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(VECTOR_FILE, vectors=vectors)
    print("Saved pinned vectors:", VECTOR_FILE)


def migrate(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY
        )
    """)
    version = MIGRATION.name
    applied = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version=%s", (version,)
    ).fetchone()
    if applied:
        return

    # Fixed, project-owned SQL file; each statement is simple DDL.
    for statement in MIGRATION.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            conn.execute(statement.strip())
    conn.execute(
        "INSERT INTO schema_migrations(version) VALUES (%s)",
        (version,),
    )
    print("Applied migration:", version)


def import_vectors(conn):
    metadata = json.loads(META_FILE.read_text(encoding="utf-8"))
    with np.load(VECTOR_FILE, allow_pickle=False) as archive:
        vectors = archive["vectors"]

    expected = (len(metadata["chunks"]), 512)
    if vectors.shape != expected or metadata["dimension"] != 512:
        raise ValueError(f"Expected vector matrix {expected}, got {vectors.shape}")

    for chunk, embedding in zip(metadata["chunks"], vectors):
        conn.execute("""
            INSERT INTO knowledge_vectors
                (chunk_id, doc_id, source_path, model_revision, embedding)
            VALUES (%s, %s, %s, %s, %s::vector)
            ON CONFLICT (chunk_id) DO UPDATE SET
                doc_id = EXCLUDED.doc_id,
                source_path = EXCLUDED.source_path,
                model_revision = EXCLUDED.model_revision,
                embedding = EXCLUDED.embedding
        """, (
            chunk["chunk_id"],
            chunk["doc_id"],
            chunk["source_path"],
            metadata["model_revision"],
            vector_literal(embedding),
        ))

    count = conn.execute(
        "SELECT COUNT(*) FROM knowledge_vectors"
    ).fetchone()[0]
    print(f"pgvector rows: {count}; expected at least {len(vectors)}")
    if count < len(vectors):
        raise RuntimeError("pgvector import incomplete")


def main():
    ensure_seed_data()
    ensure_pinned_vectors()
    with psycopg.connect() as conn:  # PGHOST, PGUSER, PGPASSWORD, PGDATABASE
        migrate(conn)
        import_vectors(conn)
    print("Day 24 bootstrap complete")


if __name__ == "__main__":
    main()
