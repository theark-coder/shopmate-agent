
import json
from copy import deepcopy

import pytest

from shopmate_agent.embedding_index import META_FILE
from shopmate_agent.retrieval_eval import (
    DATASET_FILE,
    metrics_at_k,
    validate_dataset,
)


def test_hit_and_recall():
    result = metrics_at_k(
        retrieved_ids=["policy-returns", "FAQ001", "FAQ002"],
        relevant_ids=["policy-returns", "FAQ003"],
        k=3,
    )

    assert result["hit"] == 1
    assert result["recall"] == 0.5


def test_no_relevant_document():
    result = metrics_at_k(
        retrieved_ids=["P001-description", "P002-description"],
        relevant_ids=["policy-returns"],
        k=2,
    )

    assert result["hit"] == 0
    assert result["recall"] == 0.0


def test_fixed_split_and_labels():
    dataset = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
    metadata = json.loads(META_FILE.read_text(encoding="utf-8"))

    tasks = dataset["tasks"]
    doc_ids = {chunk["doc_id"] for chunk in metadata["chunks"]}

    assert validate_dataset(tasks, doc_ids)

    assert sum(t["split"] == "dev" for t in tasks) == 40
    assert sum(t["split"] == "test" for t in tasks) == 20

    assert {t["category"] for t in tasks} == {
        "shopping",
        "order",
        "aftersales",
    }


def test_duplicate_task_id_is_rejected():
    dataset = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
    metadata = json.loads(META_FILE.read_text(encoding="utf-8"))

    tasks = deepcopy(dataset["tasks"])
    tasks[1]["id"] = tasks[0]["id"]

    doc_ids = {chunk["doc_id"] for chunk in metadata["chunks"]}

    with pytest.raises(ValueError, match="Duplicate task ID"):
        validate_dataset(tasks, doc_ids)
