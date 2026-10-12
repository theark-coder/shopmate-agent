
import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

from shopmate_agent.llm_metrics import create_with_metrics


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

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
        max_retries=0,
        timeout=30.0,
    )

    response, metrics = create_with_metrics(
        client,
        model="qwen-plus",
        messages=[
            {
                "role": "system",
                "content": "请简洁回答用户问题。",
            },
            {
                "role": "user",
                "content": "用一句话解释什么是Token。",
            },
        ],
        temperature=0,
        max_tokens=128,
    )

    answer = response.choices[0].message.content

    print("Model response:", answer)
    print("Prompt tokens:", metrics["prompt_tokens"])
    print("Completion tokens:", metrics["completion_tokens"])
    print("Total tokens:", metrics["total_tokens"])
    print("Duration ms:", metrics["duration_ms"])

    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ):
        if metrics[key] is None:
            raise RuntimeError(
                f"Provider did not return {key}"
            )


if __name__ == "__main__":
    main()
