
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from shopmate_agent.calculator import safe_calculate


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算加减乘除数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "如 123 * 456",
                    }
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    }
]


def run_demo():
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

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个购物助手。需要数学计算时，"
                "请调用 calculate 工具，不要自行猜测结果。"
            ),
        },
        {
            "role": "user",
            "content": "请计算 123 * 456",
        },
    ]

    # 第一次模型请求：让模型提出工具调用
    first = client.chat.completions.create(
        model="qwen-plus",
        messages=messages,
        tools=TOOLS,
        tool_choice="required",
        temperature=0,
    )

    assistant_message = first.choices[0].message

    if not assistant_message.tool_calls:
        raise RuntimeError("Model did not call a tool")

    messages.append(assistant_message)

    # Python 执行模型请求的工具
    for call in assistant_message.tool_calls:
        if call.function.name != "calculate":
            raise ValueError("Unknown tool")

        try:
            arguments = json.loads(
                call.function.arguments
            )

            if (
                not isinstance(arguments, dict)
                or set(arguments) != {"expression"}
            ):
                raise ValueError("Invalid tool arguments")

            result = safe_calculate(
                arguments["expression"]
            )
            tool_result = str(result)

        except (ValueError, TypeError, KeyError) as exc:
            tool_result = f"Tool error: {exc}"

        print("Tool name:", call.function.name)
        print("Tool result:", tool_result)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": tool_result,
            }
        )

    # 第二次请求：把执行结果返回模型
    second = client.chat.completions.create(
        model="qwen-plus",
        messages=messages,
        temperature=0,
    )

    print(
        "Final answer:",
        second.choices[0].message.content,
    )


if __name__ == "__main__":
    run_demo()
