
import json
from dataclasses import dataclass
from typing import Callable, Any

from shopmate_agent.calculator import safe_calculate


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    function: Callable[..., Any]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool: {spec.name}")

        self._tools[spec.name] = spec

    def get_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def execute(self, name: str, arguments_json: str) -> dict:
        if name not in self._tools:
            return self._error("UNKNOWN_TOOL", "Unknown tool")

        try:
            args = json.loads(arguments_json)
        except (json.JSONDecodeError, TypeError):
            return self._error("INVALID_JSON", "Invalid JSON arguments")

        if not isinstance(args, dict):
            return self._error(
                "INVALID_ARGUMENTS",
                "Arguments must be a JSON object",
            )

        spec = self._tools[name]
        parameters = spec.parameters

        properties = parameters.get("properties", {})
        required = parameters.get("required", [])

        if any(key not in args for key in required):
            return self._error(
                "INVALID_ARGUMENTS",
                "Missing required arguments",
            )

        if any(key not in properties for key in args):
            return self._error(
                "INVALID_ARGUMENTS",
                "Unexpected arguments",
            )

        for key, value in args.items():
            expected_type = properties[key].get("type")

            if expected_type == "string" and not isinstance(value, str):
                return self._error(
                    "INVALID_ARGUMENTS",
                    f"{key} must be a string",
                )

        try:
            result = spec.function(**args)
        except ValueError as exc:
            return self._error(
                "TOOL_EXECUTION_ERROR",
                str(exc),
            )
        except Exception:
            # 不向模型泄露内部异常细节
            return self._error(
                "INTERNAL_TOOL_ERROR",
                "Tool execution failed",
            )

        return {
            "ok": True,
            "data": result,
            "error": None,
        }

    @staticmethod
    def _error(code: str, message: str) -> dict:
        return {
            "ok": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
            },
        }


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="calculate",
            description="安全计算加减乘除数学表达式",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "例如 123 * 456",
                    }
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
            function=safe_calculate,
        )
    )

    return registry
