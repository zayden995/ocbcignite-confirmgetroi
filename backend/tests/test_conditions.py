import pytest

from app.conditions import evaluate_condition, evaluate_conditions
from app.models import Condition


def c(field, op, value):
    return Condition(field=field, op=op, value=value)


@pytest.mark.parametrize(
    "op,value,actual,expected",
    [
        (">=", 10000, 10000, "pass"),
        (">=", 10000, 9999, "fail"),
        (">", 10000, 10000, "fail"),
        ("<=", 10, 10, "pass"),
        ("<", 10, 10, "fail"),
        ("==", 12, 12, "pass"),
        ("!=", 12, 12, "fail"),
        ("in", ["GIRO"], "GIRO", "pass"),
        ("in", ["GIRO"], "FAST", "fail"),
        ("in", ["GIRO"], "giro", "pass"),  # categorical compare is case-insensitive
        ("not_in", ["FAST"], "GIRO", "pass"),
        ("in", [12], 12, "pass"),
        (">=", 10000, "20000", "pass"),  # numeric strings from a form are coerced
    ],
)
def test_operators(op, value, actual, expected):
    assert evaluate_condition(c("x", op, value), {"x": actual}) == expected


@pytest.mark.parametrize("params", [{}, {"x": None}, {"x": ""}])
def test_missing_parameter_is_missing_not_fail(params):
    assert evaluate_condition(c("x", ">=", 1), params) == "missing"


def test_non_numeric_value_for_numeric_op_raises():
    with pytest.raises(ValueError):
        evaluate_condition(c("x", ">=", 1), {"x": "lots"})


def test_evaluate_conditions_returns_detail():
    results = evaluate_conditions(
        [c("deposit_amount", ">=", 10000), c("channel", "in", ["GIRO"])],
        {"deposit_amount": 5000},
    )
    assert [(r.field, r.result, r.actual) for r in results] == [
        ("deposit_amount", "fail", 5000),
        ("channel", "missing", None),
    ]
