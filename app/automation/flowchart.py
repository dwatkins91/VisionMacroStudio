from __future__ import annotations

from typing import Any

from app.automation.control import destination_steps, object_names


def _target_index(target: int, index: int, count: int) -> int | None:
    if target == 0:
        return index + 1 if index + 1 < count else None
    return target - 1 if 1 <= target <= count else None


def flow_edges(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build labeled edges for the read-only connected macro view."""
    edges: list[dict[str, Any]] = []
    count = len(steps)

    def add(source: int, target: int | None, label: str, kind: str) -> None:
        if target is not None:
            edges.append(
                {"source": source, "target": target, "label": label, "kind": kind}
            )

    for index, step in enumerate(steps):
        action = step.get("action")
        next_index = _target_index(0, index, count)
        if action == "STOP":
            continue
        if action == "GOTO_STEP":
            add(
                index,
                _target_index(int(step.get("target_step", 0)), index, count),
                "go to",
                "jump",
            )
            continue
        if action == "REPEAT":
            add(
                index,
                _target_index(int(step.get("target_step", 0)), index, count),
                f"repeat ×{step.get('count', 1)}",
                "repeat",
            )
            add(index, next_index, "done", "next")
            continue
        if action == "IF_VARIABLE":
            add(
                index,
                _target_index(int(step.get("true_step", 0)), index, count),
                "true",
                "true",
            )
            add(
                index,
                _target_index(int(step.get("false_step", 0)), index, count),
                "false",
                "false",
            )
            continue
        if action == "WAIT_FOR_ANY_OBJECT":
            try:
                targets = destination_steps(step.get("target_steps", []))
            except ValueError:
                targets = []
            for name, target in zip(object_names(step.get("objects", [])), targets):
                add(index, _target_index(target, index, count), name, "match")
            if step.get("on_timeout") == "go_to_step":
                add(
                    index,
                    _target_index(int(step.get("failure_step", 0)), index, count),
                    "timeout",
                    "failure",
                )
            continue
        success_label = "return" if action == "CALL_MACRO" else "next"
        add(index, next_index, success_label, "next")
        if (
            action
            in {
                "WAIT_FOR_OBJECT",
                "WAIT_UNTIL_DISAPPEARS",
                "CLICK_OBJECT",
                "RIGHT_CLICK_OBJECT",
                "CLICK_FIRST_AVAILABLE",
            }
            and step.get("on_timeout") == "go_to_step"
        ):
            add(
                index,
                _target_index(int(step.get("failure_step", 0)), index, count),
                "timeout",
                "failure",
            )
    return edges

