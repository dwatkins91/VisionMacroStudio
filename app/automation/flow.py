from __future__ import annotations

import math
import re
from typing import Any


COMPARISON_OPERATORS = ("==", "!=", ">", ">=", "<", "<=")
VARIABLE_ACTIONS = {"SET_VARIABLE", "ADD_VARIABLE", "IF_VARIABLE"}
VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def valid_variable_name(value: Any) -> bool:
    return bool(VARIABLE_NAME_PATTERN.fullmatch(str(value).strip()))


def parse_value(value: Any) -> Any:
    """Turn editor text into a predictable bool/number/string value."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    lowered = text.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        integer = int(text)
        if str(integer) == text or text in {f"+{integer}", f"-{abs(integer)}"}:
            return integer
    except ValueError:
        pass
    try:
        number = float(text)
        if math.isfinite(number):
            return number
    except ValueError:
        pass
    return text


def number_value(value: Any) -> float:
    parsed = parse_value(value)
    if isinstance(parsed, bool) or not isinstance(parsed, (int, float)):
        raise ValueError(f"{value!r} is not a number.")
    number = float(parsed)
    if not math.isfinite(number):
        raise ValueError(f"{value!r} is not a finite number.")
    return number


def compare_values(left: Any, operator: str, right: Any) -> bool:
    if operator not in COMPARISON_OPERATORS:
        raise ValueError(f"Unsupported comparison operator: {operator!r}.")
    left_value = parse_value(left)
    right_value = parse_value(right)
    numeric = False
    try:
        left_number = number_value(left_value)
        right_number = number_value(right_value)
        numeric = True
    except ValueError:
        left_number = right_number = 0.0
    if numeric:
        first, second = left_number, right_number
    else:
        first, second = str(left_value), str(right_value)
    return {
        "==": first == second,
        "!=": first != second,
        ">": first > second,
        ">=": first >= second,
        "<": first < second,
        "<=": first <= second,
    }[operator]


def step_destinations(step: dict[str, Any]) -> list[int]:
    """Return every explicit local step destination used by a flow action."""
    action = step.get("action")
    values: list[Any] = []
    if action == "WAIT_FOR_ANY_OBJECT":
        raw = step.get("target_steps", [])
        values.extend(raw.split(",") if isinstance(raw, str) else raw)
    elif action in {"GOTO_STEP", "REPEAT"}:
        values.append(step.get("target_step", 0))
    elif action == "IF_VARIABLE":
        values.extend((step.get("true_step", 0), step.get("false_step", 0)))
    if action in {
        "WAIT_FOR_OBJECT",
        "WAIT_FOR_ANY_OBJECT",
        "WAIT_UNTIL_DISAPPEARS",
        "CLICK_OBJECT",
        "RIGHT_CLICK_OBJECT",
        "CLICK_FIRST_AVAILABLE",
    } and step.get("on_timeout") == "go_to_step":
        values.append(step.get("failure_step", 0))
    destinations: list[int] = []
    for value in values:
        try:
            target = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if target != 0:
            destinations.append(target)
    return destinations

