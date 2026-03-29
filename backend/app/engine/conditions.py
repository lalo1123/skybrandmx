"""Condition evaluator for automation rules."""
import json
from typing import Any


def get_nested_value(data: dict, field_path: str) -> Any:
    """Get a value from nested dict using dot notation. e.g. 'customer.state'"""
    keys = field_path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def evaluate_condition(condition: dict, data: dict) -> bool:
    """Evaluate a single condition against event data."""
    field = condition.get("field", "")
    op = condition.get("op", "eq")
    expected = condition.get("value")
    actual = get_nested_value(data, field)

    if actual is None:
        return op == "eq" and expected is None

    try:
        if op == "eq":
            return str(actual) == str(expected)
        elif op == "neq":
            return str(actual) != str(expected)
        elif op == "gt":
            return float(actual) > float(expected)
        elif op == "gte":
            return float(actual) >= float(expected)
        elif op == "lt":
            return float(actual) < float(expected)
        elif op == "lte":
            return float(actual) <= float(expected)
        elif op == "contains":
            return str(expected).lower() in str(actual).lower()
        elif op == "not_contains":
            return str(expected).lower() not in str(actual).lower()
    except (ValueError, TypeError):
        return False

    return False


def evaluate_conditions(conditions_json: str | None, data: dict) -> bool:
    """Evaluate all conditions (AND logic). Returns True if no conditions."""
    if not conditions_json:
        return True

    try:
        conditions = json.loads(conditions_json)
    except (json.JSONDecodeError, TypeError):
        return True

    if not conditions:
        return True

    return all(evaluate_condition(c, data) for c in conditions)
