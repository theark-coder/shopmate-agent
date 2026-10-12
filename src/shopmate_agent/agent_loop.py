
import json
import time
from dataclasses import dataclass, field
from typing import Any
from shopmate_agent.llm_metrics import create_with_metrics
from shopmate_agent.tool_registry import ToolRegistry


@dataclass
class AgentResult:
    status: str
    answer: str
    steps: int
    tokens_used: int
    trace: list[dict] = field(default_factory=list)


def run_agent_loop(
    client: Any,
    registry: ToolRegistry,
    question: str,
    max_steps: int = 5,
    timeout_seconds: float = 30,
    token_budget: int = 3000,
) -> AgentResult:
    if max_steps < 1 or timeout_seconds <= 0 or token_budget < 1:
        raise ValueError("Invalid agent limits")

    deadline = time.monotonic() + timeout_seconds
    tokens_used = 0
    trace = []
    previous_action = None

    messages = [
        {
            "role": "system",
            "content": (
                "你是购物助手。需要计算时使用工具。"
                "每次获得工具结果后，判断是否可以直接回答。"
                "不要重复没有进展的工具调用。"
            ),
        },
        {"role": "user", "content": question},
    ]

    def stop(status: str, steps: int) -> AgentResult:
        return AgentResult(
            status=status,
            answer="",
            steps=steps,
            tokens_used=tokens_used,
            trace=trace,
        )

    for step in range(1, max_steps + 1):
        remaining_time = deadline - time.monotonic()
        if remaining_time <= 0:
            return stop("TIMEOUT", step - 1)

        remaining_tokens = token_budget - tokens_used
        if remaining_tokens <= 0:
            return stop("TOKEN_BUDGET_EXCEEDED", step - 1)

        # Model：决策
        try:
           response, metrics = create_with_metrics(
                client,
                model="qwen-plus",
                messages=messages,
                tools=registry.get_schemas(),
                tool_choice="auto",
                temperature=0,
                max_tokens=min(512, remaining_tokens),
                timeout=remaining_time,
            )
        except TimeoutError:
            return stop("TIMEOUT", step - 1)

        usage = getattr(response, "usage", None)
        if usage is not None:
            tokens_used += usage.total_tokens

        # 本次模型调用已经消耗完预算，则停止后续执行
        if tokens_used >= token_budget:
            return stop("TOKEN_BUDGET_EXCEEDED", step)

        if time.monotonic() >= deadline:
            return stop("TIMEOUT", step)

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        # 模型选择不再调用工具
        if not tool_calls:
            return AgentResult(
                status="COMPLETED",
                answer=message.content or "",
                steps=step,
                tokens_used=tokens_used,
                trace=trace,
            )

        messages.append(message)

        for call in tool_calls:
            # 生成动作标识：工具名 + 规范化参数
            try:
                parsed = json.loads(call.function.arguments)
                normalized = json.dumps(
                    parsed, sort_keys=True, ensure_ascii=False
                )
            except (ValueError, TypeError):
                normalized = call.function.arguments

            action = (call.function.name, normalized)

            # 同一动作连续出现：对当前确定性工具视为无进展
            if action == previous_action:
                trace.append({
                    "step": step,
                    "tool": call.function.name,
                    "action": normalized,
                    "status": "REPEATED_NO_PROGRESS",
                })
                return stop("REPEATED_NO_PROGRESS", step)

            if time.monotonic() >= deadline:
                return stop("TIMEOUT", step)

            # Tool：执行
            result = registry.execute(
                call.function.name,
                call.function.arguments,
            )

            trace.append({
                "step": step,
                "tool": call.function.name,
                "action": normalized,
                "result": result,
            })

            # Observation：反馈工具结果
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

            previous_action = action

    return stop("MAX_STEPS_REACHED", max_steps)
