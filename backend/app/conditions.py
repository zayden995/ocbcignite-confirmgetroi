"""Evaluate structured mandatory conditions against the employee's case parameters."""
from __future__ import annotations

from typing import Any

from .models import Condition, ConditionResult

_NUMERIC_OPS = {">=", ">", "<=", "<"}


def _is_missing(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _num(v: Any, field: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError) as e:
        raise ValueError(f"parameter '{field}' must be numeric for a numeric condition, got {v!r}") from e


def _equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    return str(actual).strip().casefold() == str(expected).strip().casefold()


def evaluate_condition(cond: Condition, params: dict[str, Any]) -> str:
    """Return 'pass', 'fail' or 'missing' (parameter not provided)."""
    actual = params.get(cond.field)
    if _is_missing(actual):
        return "missing"
    if cond.op in _NUMERIC_OPS:
        a, b = _num(actual, cond.field), float(cond.value)
        ok = {">=": a >= b, ">": a > b, "<=": a <= b, "<": a < b}[cond.op]
    elif cond.op == "==":
        ok = _equal(actual, cond.value)
    elif cond.op == "!=":
        ok = not _equal(actual, cond.value)
    elif cond.op == "in":
        ok = any(_equal(actual, v) for v in cond.value)
    elif cond.op == "not_in":
        ok = not any(_equal(actual, v) for v in cond.value)
    else:  # pragma: no cover - guarded by the Literal on Condition.op
        raise ValueError(f"unsupported operator {cond.op!r}")
    return "pass" if ok else "fail"


def evaluate_conditions(
    conditions: list[Condition], params: dict[str, Any], passage_id: str | None = None
) -> list[ConditionResult]:
    out = []
    for c in conditions:
        actual = params.get(c.field)
        out.append(
            ConditionResult(
                field=c.field,
                op=c.op,
                expected=c.value,
                actual=None if _is_missing(actual) else actual,
                result=evaluate_condition(c, params),
                passage_id=passage_id,
            )
        )
    return out
