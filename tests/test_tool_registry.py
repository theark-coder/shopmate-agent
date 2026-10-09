
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from shopmate_agent.tool_registry import build_registry
from shopmate_agent.function_calling_demo import run_agent


@pytest.mark.parametrize(
    ("name", "arguments", "error_code"),
    [
        ("missing_tool", "{}", "UNKNOWN_TOOL"),
        ("calculate", "{bad json", "INVALID_JSON"),
        ("calculate", "[]", "INVALID_ARGUMENTS"),
        ("calculate", "{}", "INVALID_ARGUMENTS"),
        ("calculate", '{"expression": 123}', "INVALID_ARGUMENTS"),
        ("calculate", '{"expression":"1+2","extra":1}', "INVALID_ARGUMENTS"),
        ("calculate", '{"expression":"1/0"}', "TOOL_EXECUTION_ERROR"),
        ("calculate", '{"expression":"__import__(1)"}', "TOOL_EXECUTION_ERROR"),
    ],
)
def test_invalid_tool_calls(name, arguments, error_code):
    registry = build_registry()

    result = registry.execute(name, arguments)

    assert result["ok"] is False
    assert result["error"]["code"] == error_code


def test_valid_tool_call():
    registry = build_registry()

    result = registry.execute(
        "calculate",
        '{"expression": "123 * 456"}',
    )

    assert result["ok"] is True
    assert result["data"] == 56088


def test_duplicate_registration():
    registry = build_registry()

    from shopmate_agent.tool_registry import ToolSpec

    with pytest.raises(ValueError, match="Duplicate tool"):
        registry.register(
            ToolSpec(
                "calculate",
                "重复的计算工具",
                {},
                lambda: None,
            )
        )


def test_agent_two_rounds_with_mock():
    # 模拟 Qwen 第一轮：要求调用 calculate
    tool_call = SimpleNamespace(
        id="call_001",
        function=SimpleNamespace(
            name="calculate",
            arguments='{"expression":"123 * 456"}',
        ),
    )

    first_message = SimpleNamespace(
        role="assistant",
        content=None,
        tool_calls=[tool_call],
    )

    # 模拟 Qwen 第二轮：最终回答
    second_message = SimpleNamespace(
        role="assistant",
        content="123 × 456 = 56088",
        tool_calls=None,
    )

    client = Mock()
    client.chat.completions.create.side_effect = [
        SimpleNamespace(
            choices=[SimpleNamespace(message=first_message)]
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=second_message)]
        ),
    ]

    answer = run_agent(
        client,
        build_registry(),
    )

    assert answer == "123 × 456 = 56088"

    # 验证确实发生两次模型调用
    assert client.chat.completions.create.call_count == 2

    # 验证第二轮请求包含真正的工具执行结果
    second_call = client.chat.completions.create.call_args_list[1]
    messages = second_call.kwargs["messages"]

    tool_message = next(
        message
        for message in messages
        if isinstance(message, dict)
        and message.get("role") == "tool"
    )

    assert tool_message["tool_call_id"] == "call_001"

    result = json.loads(tool_message["content"])
    assert result["ok"] is True
    assert result["data"] == 56088
