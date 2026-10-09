
import pytest

from shopmate_agent.calculator import safe_calculate


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("123 * 456", 56088),
        ("(10 + 5) / 3", 5),
        ("-8 + 3", -5),
        ("100 / 4", 25),
    ],
)
def test_valid_expression(expression, expected):
    assert safe_calculate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "1 / 0",
        "2 ** 100000",
        "__import__('os').system('whoami')",
        "open('secret.txt')",
        "x + 1",
        "[1, 2, 3]",
        "1000000 * 1000000",
        "1e309",
        "",
    ],
)
def test_invalid_expression(expression):
    with pytest.raises(ValueError):
        safe_calculate(expression)
