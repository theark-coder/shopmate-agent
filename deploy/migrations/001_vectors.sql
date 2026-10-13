CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_vectors (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    model_revision TEXT NOT NULL,
    embedding VECTOR(512) NOT NULL
);

CREATE INDEX IF NOT EXISTS knowledge_vectors_cosine_idx
ON knowledge_vectors USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS deployment_probe (
    key TEXT PRIMARY KEY,
    note TEXT NOT NULL
);
