
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from shopmate_agent.tool_registry import (
    ToolRegistry,
    build_registry,
)


def run_agent(
    client,
    registry: ToolRegistry,
    question: str = "请计算 123 * 456",
) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "你是购物助手。数学计算必须使用工具。"
                "不要假装工具执行成功。"
            ),
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    first = client.chat.completions.create(
        model="qwen-plus",
        messages=messages,
        tools=registry.get_schemas(),
        tool_choice="required",
        temperature=0,
    )

    assistant_message = first.choices[0].message
    tool_calls = assistant_message.tool_calls

    if not tool_calls:
        raise RuntimeError("Model did not request a tool")

    messages.append(assistant_message)

    for call in tool_calls:
        result = registry.execute(
            call.function.name,
            call.function.arguments,
        )

        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(
                    result,
                    ensure_ascii=False,
                ),
            }
        )

    second = client.chat.completions.create(
        model="qwen-plus",
        messages=messages,
        temperature=0,
    )

    return second.choices[0].message.content or ""


def main():
    load_dotenv()

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing DASHSCOPE_API_KEY")

    client = OpenAI(
        api_key=api_key,
        base_url=(
            "https://dashscope.aliyuncs.com/"
            "compatible-mode/v1"
        ),
    )

    answer = run_agent(
        client=client,
        registry=build_registry(),
    )

    print("Final answer:", answer)


if __name__ == "__main__":
    main()
