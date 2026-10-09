
from types import SimpleNamespace
from unittest.mock import Mock

from shopmate_agent.agent_loop import run_agent_loop
from shopmate_agent.tool_registry import build_registry


def fake_response(
    expression=None,
    content=None,
    tokens=20,
):
    if expression is None:
        message = SimpleNamespace(
            content=content,
            tool_calls=None,
        )
    else:
        message = SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="call_001",
                    function=SimpleNamespace(
                        name="calculate",
                        arguments=(
                            '{"expression": "' + expression + '"}'
                        ),
                    ),
                )
            ],
        )

    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(total_tokens=tokens),
    )


def make_client(*responses):
    client = Mock()
    client.chat.completions.create.side_effect = list(responses)
    return client


def test_different_arguments_can_continue():
    client = make_client(
        fake_response("100 + 20"),
        fake_response("200 - 50"),
        fake_response(content="两个计算均已完成"),
    )

    result = run_agent_loop(
        client,
        build_registry(),
        "分别计算两个价格表达式",
    )

    assert result.status == "COMPLETED"
    assert result.steps == 3
    assert len(result.trace) == 2

    # 同一工具使用不同参数，不应被误判为死循环
    assert result.trace[0]["tool"] == "calculate"
    assert result.trace[1]["tool"] == "calculate"
    assert result.trace[0]["action"] != result.trace[1]["action"]


def test_repeated_action_stops():
    client = make_client(
        fake_response("123 * 456"),
        fake_response("123 * 456"),
    )

    result = run_agent_loop(
        client,
        build_registry(),
        "计算 123 * 456",
    )

    assert result.status == "REPEATED_NO_PROGRESS"
    assert client.chat.completions.create.call_count == 2


def test_max_steps():
    client = make_client(
        fake_response("1 + 1"),
        fake_response("2 + 2"),
        fake_response("3 + 3"),
    )

    result = run_agent_loop(
        client,
        build_registry(),
        "执行多个计算",
        max_steps=2,
    )

    assert result.status == "MAX_STEPS_REACHED"
    assert result.steps == 2
    assert client.chat.completions.create.call_count == 2


def test_token_budget():
    client = make_client(
        fake_response("1 + 1", tokens=50),
    )

    result = run_agent_loop(
        client,
        build_registry(),
        "计算 1 + 1",
        token_budget=30,
    )

    assert result.status == "TOKEN_BUDGET_EXCEEDED"
    assert result.tokens_used == 50


def test_timeout():
    client = Mock()
    client.chat.completions.create.side_effect = TimeoutError()

    result = run_agent_loop(
        client,
        build_registry(),
        "计算 1 + 1",
        timeout_seconds=1,
    )

    assert result.status == "TIMEOUT"
