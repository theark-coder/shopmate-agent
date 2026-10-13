import numpy as np
import pytest

from deploy.bootstrap_day24 import MIGRATION, vector_literal


def test_vector_literal_shape_and_values():
    vector = np.zeros(512, dtype=np.float32)
    vector[3] = 1.0
    result = vector_literal(vector)
    assert result.startswith("[0,0,0,1,")
    assert len(result[1:-1].split(",")) == 512


def test_invalid_vector_rejected():
    with pytest.raises(ValueError):
        vector_literal(np.ones(3))
    with pytest.raises(ValueError):
        vector_literal(np.full(512, np.nan))
    with pytest.raises(ValueError):
        vector_literal(np.zeros(512))


def test_migration_declares_pgvector_and_durable_tables():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "embedding VECTOR(512) NOT NULL" in sql
    assert "deployment_probe" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
