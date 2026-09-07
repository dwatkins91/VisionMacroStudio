from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any


SUPPORTED_ACTIONS = (
    "WAIT_FOR_OBJECT",
    "WAIT_FOR_ANY_OBJECT",
    "WAIT_UNTIL_DISAPPEARS",
    "CLICK_OBJECT",
    "RIGHT_CLICK_OBJECT",
    "CLICK_FIRST_AVAILABLE",
    "PRESS_KEY",
    "TYPE_TEXT",
    "WAIT",
    "MOVE_MOUSE",
    "CLICK",
    "DOUBLE_CLICK",
    "RIGHT_CLICK",
    "REPEAT",
    "GOTO_STEP",
    "STOP",
    "SECTION",
    "SET_VARIABLE",
    "ADD_VARIABLE",
    "IF_VARIABLE",
    "CALL_MACRO",
)


def object_names(value: Any) -> list[str]:
    """Normalize a saved list or comma-separated editor value."""
    if isinstance(value, str):
        items: Iterable[Any] = value.split(",")
    elif isinstance(value, Iterable):
        items = value
    else:
        items = []
    return [str(item).strip() for item in items if str(item).strip()]


def destination_steps(value: Any) -> list[int]:
    """Normalize branch destinations; zero means continue to the next step."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        items: Iterable[Any] = value.split(",")
    elif isinstance(value, Iterable):
        items = value
    else:
        items = [value]
    destinations: list[int] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        try:
            destination = int(text)
        except ValueError as exc:
            raise ValueError(
                "Destination steps must be whole numbers separated by commas."
            ) from exc
        if destination < 0:
            raise ValueError("Destination steps cannot be negative.")
        destinations.append(destination)
    return destinations


def randomized_point(x: int, y: int, max_offset: int) -> tuple[int, int]:
    """Move a point independently by up to max_offset pixels on each axis."""
    offset = max(0, int(max_offset))
    if offset == 0:
        return int(x), int(y)
    return (
        int(x) + random.randint(-offset, offset),
        int(y) + random.randint(-offset, offset),
    )


def randomized_seconds(minimum: float, maximum: float | None = None) -> float:
    """Choose a wait duration from an inclusive minimum/maximum range."""
    low = max(0.0, float(minimum))
    high = low if maximum is None else max(low, float(maximum))
    if high == low:
        return low
    return random.uniform(low, high)
