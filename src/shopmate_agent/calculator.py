
import ast
import math
import operator

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

MAX_LENGTH = 100
MAX_VALUE = 1_000_000


def safe_calculate(expression: str) -> int | float:
    if not isinstance(expression, str):
        raise ValueError("Expression must be a string")

    if not expression.strip() or len(expression) > MAX_LENGTH:
        raise ValueError("Invalid expression length")

    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ValueError("Invalid expression") from exc

    def evaluate(node):
        if isinstance(node, ast.Constant):
            value = node.value

            if type(value) not in (int, float):
                raise ValueError("Only numbers allowed")

            if not math.isfinite(value) or abs(value) > MAX_VALUE:
                raise ValueError("Number out of range")

            return value

        if isinstance(node, ast.UnaryOp):
            if type(node.op) not in (ast.UAdd, ast.USub):
                raise ValueError("Operator not allowed")

            result = evaluate(node.operand)

            if isinstance(node.op, ast.USub):
                result = -result

            return result

        if isinstance(node, ast.BinOp):
            operation = OPERATORS.get(type(node.op))

            if operation is None:
                raise ValueError("Operator not allowed")

            left = evaluate(node.left)
            right = evaluate(node.right)

            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("Division by zero")

            # 运算前限制输入量级
            if abs(left) > MAX_VALUE or abs(right) > MAX_VALUE:
                raise ValueError("Number out of range")

            result = operation(left, right)

            if not math.isfinite(result) or abs(result) > MAX_VALUE:
                raise ValueError("Result out of range")

            return result

        raise ValueError("Expression not allowed")

    return evaluate(tree.body)
