from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from app.automation.control import SUPPORTED_ACTIONS, destination_steps, object_names
from app.automation.macro_io import MacroFormatError, validate_macro


DETECTION_ACTIONS = {
    "WAIT_FOR_OBJECT",
    "WAIT_FOR_ANY_OBJECT",
    "WAIT_UNTIL_DISAPPEARS",
    "CLICK_OBJECT",
    "RIGHT_CLICK_OBJECT",
    "CLICK_FIRST_AVAILABLE",
}
SINGLE_OBJECT_ACTIONS = {
    "WAIT_FOR_OBJECT",
    "WAIT_UNTIL_DISAPPEARS",
    "CLICK_OBJECT",
    "RIGHT_CLICK_OBJECT",
}


@dataclass(frozen=True)
class MacroIssue:
    severity: str
    message: str
    step_number: int | None = None
    code: str = ""


def _class_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z]+", "_", str(value).casefold()).strip("_")


def _step_title(step: dict[str, Any], step_number: int) -> str:
    name = str(step.get("name", "")).strip()
    return f"Step {step_number} ({name})" if name else f"Step {step_number}"


def _explicit_destinations(step: dict[str, Any]) -> list[int]:
    action = step.get("action")
    try:
        if action == "WAIT_FOR_ANY_OBJECT":
            return [
                target
                for target in destination_steps(step.get("target_steps", []))
                if target != 0
            ]
        if action in {"GOTO_STEP", "REPEAT"}:
            return [int(step.get("target_step", 0))]
    except (TypeError, ValueError):
        pass
    return []


def _finite_detection_limit(step: dict[str, Any]) -> bool:
    try:
        minimum = float(step.get("timeout", 30))
        maximum = float(step.get("timeout_max", minimum))
        attempts = int(step.get("max_detection_attempts", 0))
    except (TypeError, ValueError):
        return False
    return maximum > 0 or minimum > 0 or attempts > 0


def _next_enabled(steps: list[dict[str, Any]], start: int) -> int | None:
    for index in range(max(0, start), len(steps)):
        if bool(steps[index].get("enabled", True)):
            return index
    return None


def _flow_graph(
    steps: list[dict[str, Any]],
) -> tuple[dict[int, set[int]], dict[int, bool]]:
    edges: dict[int, set[int]] = {}
    can_terminate: dict[int, bool] = {}
    count = len(steps)
    for index, step in enumerate(steps):
        if not bool(step.get("enabled", True)):
            continue
        action = step.get("action")
        next_step = _next_enabled(steps, index + 1)
        outgoing: set[int] = set()
        terminates = False

        def add_destination(target: int) -> None:
            nonlocal terminates
            if target == 0:
                resolved = next_step
            elif 1 <= target <= count:
                resolved = _next_enabled(steps, target - 1)
            else:
                return
            if resolved is None:
                terminates = True
            else:
                outgoing.add(resolved)

        if action == "STOP":
            terminates = True
        elif action == "GOTO_STEP":
            for target in _explicit_destinations(step):
                add_destination(target)
        elif action == "REPEAT":
            for target in _explicit_destinations(step):
                add_destination(target)
            add_destination(0)
        elif action == "WAIT_FOR_ANY_OBJECT":
            try:
                targets = destination_steps(step.get("target_steps", []))
            except ValueError:
                targets = []
            for target in targets:
                add_destination(target)
            if (
                _finite_detection_limit(step)
                and step.get("on_timeout", "stop") == "stop"
            ):
                terminates = True
            elif step.get("on_timeout", "stop") == "continue":
                add_destination(0)
        else:
            add_destination(0)
            if (
                action in DETECTION_ACTIONS
                and _finite_detection_limit(step)
                and step.get("on_timeout", "stop") == "stop"
            ):
                terminates = True
        edges[index] = outgoing
        can_terminate[index] = terminates
    return edges, can_terminate


def _reachable(start: int | None, edges: dict[int, set[int]]) -> set[int]:
    if start is None:
        return set()
    seen: set[int] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(edges.get(node, set()) - seen)
    return seen


def _strongly_connected_components(
    nodes: Iterable[int], edges: dict[int, set[int]]
) -> list[set[int]]:
    allowed = set(nodes)
    index = 0
    indices: dict[int, int] = {}
    low_links: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    components: list[set[int]] = []

    def visit(node: int) -> None:
        nonlocal index
        indices[node] = index
        low_links[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for destination in edges.get(node, set()):
            if destination not in allowed:
                continue
            if destination not in indices:
                visit(destination)
                low_links[node] = min(low_links[node], low_links[destination])
            elif destination in on_stack:
                low_links[node] = min(low_links[node], indices[destination])
        if low_links[node] != indices[node]:
            return
        component: set[int] = set()
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == node:
                break
        components.append(component)

    for node in sorted(allowed):
        if node not in indices:
            visit(node)
    return components


def analyze_macro(
    macro: Any, project_classes: Iterable[str] | None = None
) -> list[MacroIssue]:
    """Return actionable builder errors and warnings without changing the macro."""
    issues: list[MacroIssue] = []
    if not isinstance(macro, dict):
        return [
            MacroIssue("error", "The macro is not a valid object.", code="format")
        ]
    steps_value = macro.get("steps")
    if not isinstance(steps_value, list):
        return [
            MacroIssue(
                "error",
                "The macro does not contain a valid step list.",
                code="format",
            )
        ]
    steps = [step if isinstance(step, dict) else {} for step in steps_value]
    if not steps:
        return [
            MacroIssue("error", "The macro does not contain any steps.", code="empty")
        ]

    try:
        validate_macro(macro)
    except MacroFormatError as exc:
        message = str(exc)
        match = re.match(r"Step (\d+)\b", message)
        issues.append(
            MacroIssue(
                "error",
                message,
                int(match.group(1)) if match else None,
                "format",
            )
        )

    known_classes = {
        _class_key(name) for name in (project_classes or ()) if str(name).strip()
    }
    count = len(steps)
    enabled_executable = 0
    for index, step in enumerate(steps):
        number = index + 1
        title = _step_title(step, number)
        action = step.get("action")
        enabled = bool(step.get("enabled", True))
        if action not in SUPPORTED_ACTIONS:
            continue
        if enabled and action != "SECTION":
            enabled_executable += 1

        names = (
            object_names([step.get("object", "")])
            if action in SINGLE_OBJECT_ACTIONS
            else object_names(step.get("objects", []))
            if action in {"WAIT_FOR_ANY_OBJECT", "CLICK_FIRST_AVAILABLE"}
            else []
        )
        for name in names:
            if project_classes is not None and _class_key(name) not in known_classes:
                severity = "error" if enabled else "warning"
                issues.append(
                    MacroIssue(
                        severity,
                        f"{title} references missing project class {name!r}.",
                        number,
                        "missing_class",
                    )
                )

        for target in _explicit_destinations(step):
            if not 1 <= target <= count:
                issues.append(
                    MacroIssue(
                        "error",
                        f"{title} points to missing step {target}.",
                        number,
                        "missing_destination",
                    )
                )
            elif not bool(steps[target - 1].get("enabled", True)):
                issues.append(
                    MacroIssue(
                        "warning",
                        f"{title} can branch to disabled step {target}; "
                        "a live run will skip it.",
                        number,
                        "disabled_destination",
                    )
                )

        if (
            action in DETECTION_ACTIONS
            and enabled
            and not _finite_detection_limit(step)
        ):
            issues.append(
                MacroIssue(
                    "warning",
                    f"{title} can wait forever because it has no timeout or "
                    "maximum detection-check limit.",
                    number,
                    "unbounded_wait",
                )
            )

    if enabled_executable == 0:
        issues.append(
            MacroIssue(
                "error",
                "The macro has no enabled executable steps.",
                code="no_enabled_steps",
            )
        )

    edges, can_terminate = _flow_graph(steps)
    reachable = _reachable(_next_enabled(steps, 0), edges)
    for index, step in enumerate(steps):
        if bool(step.get("enabled", True)) and index not in reachable:
            issues.append(
                MacroIssue(
                    "warning",
                    f"{_step_title(step, index + 1)} cannot be reached from "
                    "the beginning of the macro.",
                    index + 1,
                    "unreachable",
                )
            )

    try:
        time_limit = float(macro.get("time_limit_minutes", 0))
    except (TypeError, ValueError):
        time_limit = 0
    if time_limit <= 0:
        for component in _strongly_connected_components(reachable, edges):
            has_cycle = len(component) > 1 or any(
                node in edges.get(node, set()) for node in component
            )
            has_exit = any(
                destination not in component
                for node in component
                for destination in edges.get(node, set())
            )
            if (
                has_cycle
                and not has_exit
                and not any(can_terminate.get(node, False) for node in component)
            ):
                numbers = sorted(node + 1 for node in component)
                singular = len(numbers) == 1
                label = (
                    f"Step {numbers[0]}"
                    if singular
                    else "Steps " + ", ".join(str(number) for number in numbers)
                )
                issues.append(
                    MacroIssue(
                        "warning",
                        f"{label} {'forms' if singular else 'form'} a closed loop "
                        "with no exit or macro time limit.",
                        numbers[0],
                        "closed_loop",
                    )
                )

    deduplicated: dict[tuple[str, str], MacroIssue] = {}
    for issue in issues:
        key = (issue.severity, issue.message)
        current = deduplicated.get(key)
        if current is None or (
            current.step_number is None and issue.step_number is not None
        ) or (
            current.code == "format" and issue.code != "format"
        ):
            deduplicated[key] = issue
    severity_order = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        deduplicated.values(),
        key=lambda issue: (
            severity_order.get(issue.severity, 9),
            issue.step_number or 0,
            issue.code,
        ),
    )


def issue_counts(issues: Iterable[MacroIssue]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return counts
