
import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from shopmate_agent.llm_metrics import create_with_metrics
from shopmate_agent.agent_loop import run_agent_loop
from shopmate_agent.tool_registry import build_registry


def fake_client(with_usage=True):
    client = Mock()

    usage = (
        SimpleNamespace(
            prompt_tokens=25,
            completion_tokens=15,
            total_tokens=40,
        )
        if with_usage else None
    )

    client.chat.completions.create.return_value = (
        SimpleNamespace(
            id="mock_request_001",
            model="qwen-plus",
            usage=usage,
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Token 是文本处理单位。",
                        tool_calls=None,
                    )
                )
            ],
        )
    )

    return client


def test_token_usage_and_latency(caplog):
    client = fake_client()

    with caplog.at_level(
        logging.INFO, logger="shopmate.llm"
    ):
        response, metrics = create_with_metrics(
            client,
            model="qwen-plus",
            messages=[{"role": "user", "content": "你好"}],
        )

    assert response.id == "mock_request_001"
    assert metrics["prompt_tokens"] == 25
    assert metrics["completion_tokens"] == 15
    assert metrics["total_tokens"] == 40
    assert metrics["duration_ms"] >= 0

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "shopmate.llm"
    ]

    assert records[0]["event"] == "llm_usage"


def test_missing_usage_is_not_fabricated():
    _, metrics = create_with_metrics(
        fake_client(with_usage=False),
        model="qwen-plus",
    )

    assert metrics["prompt_tokens"] is None
    assert metrics["completion_tokens"] is None
    assert metrics["total_tokens"] is None


def test_api_error_is_raised():
    client = Mock()
    client.chat.completions.create.side_effect = (
        RuntimeError("API failed")
    )

    with pytest.raises(RuntimeError, match="API failed"):
        create_with_metrics(
            client,
            model="qwen-plus",
        )


def test_agent_loop_uses_metrics_wrapper(caplog):
    client = fake_client()

    with caplog.at_level(
        logging.INFO, logger="shopmate.llm"
    ):
        result = run_agent_loop(
            client,
            build_registry(),
            "请解释Token",
        )

    assert result.status == "COMPLETED"
    assert result.tokens_used == 40

    assert any(
        '"event": "llm_usage"' in record.message
        for record in caplog.records
    )
