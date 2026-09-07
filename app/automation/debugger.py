from __future__ import annotations

from typing import Any

from app.automation.control import destination_steps, object_names
from app.automation.coordinates import (
    CoordinateReferenceError,
    coordinate_mode_label,
    resolve_step_coordinate,
)
from app.vision.detector import Detector


DETECTION_ACTIONS = {
    "WAIT_FOR_OBJECT",
    "WAIT_FOR_ANY_OBJECT",
    "WAIT_UNTIL_DISAPPEARS",
    "CLICK_OBJECT",
    "RIGHT_CLICK_OBJECT",
    "CLICK_FIRST_AVAILABLE",
}

SCREEN_ACTIONS = {"MOVE_MOUSE", "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"}


def step_needs_detection(step: dict[str, Any]) -> bool:
    return step.get("action") in DETECTION_ACTIONS


def step_needs_screen_preview(step: dict[str, Any]) -> bool:
    return step_needs_detection(step) or step.get("action") in SCREEN_ACTIONS


def _next_step_label(step_index: int, step_count: int) -> str:
    if step_index + 1 < step_count:
        return f"step {step_index + 2}"
    return "the end of the macro"


def _timeout_description(step: dict[str, Any]) -> str:
    minimum = float(step.get("timeout", 30.0))
    maximum = float(step.get("timeout_max", minimum))
    if minimum == 0 and maximum == 0:
        return "The live step can wait forever."
    if minimum == maximum:
        value = f"{minimum:g} second(s)"
    else:
        value = f"a random {minimum:g}–{maximum:g} seconds"
    behavior = str(step.get("on_timeout", "stop")).replace("_", " ")
    return f"The live step waits {value}, then will {behavior}."


def _visible_description(detections: list[dict[str, Any]]) -> str:
    if not detections:
        return "Visible detections at 5% or higher: none."
    ordered = sorted(
        detections, key=lambda detection: float(detection.get("confidence", 0)), reverse=True
    )
    shown = ", ".join(
        f"{detection.get('class_name', 'Unknown')} "
        f"{float(detection.get('confidence', 0)):.0%}"
        for detection in ordered[:10]
    )
    remainder = len(ordered) - 10
    suffix = f" (+{remainder} more)" if remainder > 0 else ""
    return f"Visible detections at 5% or higher: {shown}{suffix}."


def _click_point(
    step: dict[str, Any], found: dict[str, Any], origin: tuple[int, int]
) -> tuple[int, int]:
    x, y, width, height = found["bbox"]
    return (
        round(origin[0] + x + width * float(step.get("target_x", 0.5))),
        round(origin[1] + y + height * float(step.get("target_y", 0.5))),
    )


def _target_status(
    detections: list[dict[str, Any]], name: str, confidence: float
) -> tuple[dict[str, Any] | None, str | None]:
    accepted = Detector.best(detections, name, confidence)
    if accepted is not None:
        return accepted, None
    candidate = Detector.best(detections, name)
    if candidate is None:
        return None, f"{name} was not detected."
    return (
        None,
        f"{name} was seen at {float(candidate['confidence']):.0%}, "
        f"below the required {confidence:.0%}.",
    )


def analyze_step(
    step: dict[str, Any],
    step_index: int,
    step_count: int,
    detections: list[dict[str, Any]] | None = None,
    origin: tuple[int, int] = (0, 0),
    watch_bounds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe one macro step without sending mouse or keyboard input."""

    action = str(step.get("action", ""))
    action_label = action.replace("_", " ").title() or "Unknown"
    detections = list(detections or [])
    details: list[str] = []
    marker: tuple[int, int] | None = None
    next_label = _next_step_label(step_index, step_count)
    decision = "No live action was performed."

    if not step.get("enabled", True):
        details.append(
            "This step is disabled in a full macro run; the debugger evaluated it anyway."
        )

    if step_needs_detection(step):
        confidence = float(step.get("confidence", 0.70))
        required = max(1, int(step.get("required_consecutive_detections", 1)))
        max_attempts = max(0, int(step.get("max_detection_attempts", 0)))
        details.append(f"Required confidence: {confidence:.0%}.")
        if required > 1:
            details.append(
                f"The live step requires {required} consecutive matching screen checks."
            )
        if max_attempts > 0:
            details.append(
                f"The live step allows at most {max_attempts} detection checks."
            )
        cooldown = max(0.0, float(step.get("click_cooldown_seconds", 0)))
        if cooldown > 0:
            details.append(
                f"After a live click, the same object near that position is ignored for {cooldown:g} second(s)."
            )
            details.append(
                "Safe preview has no prior-click history, so it cannot apply that cooldown."
            )
        if step.get("wait_after_click_until_disappears", False):
            disappear_timeout = max(
                0.0, float(step.get("post_click_disappear_timeout", 10))
            )
            disappear_text = (
                "forever"
                if disappear_timeout == 0
                else f"up to {disappear_timeout:g} second(s)"
            )
            details.append(
                f"After a live click, the step waits {disappear_text} for the clicked object to disappear."
            )
        details.append(_visible_description(detections))
        details.append(_timeout_description(step))

        if action in {"WAIT_FOR_ANY_OBJECT", "CLICK_FIRST_AVAILABLE"}:
            names = object_names(step.get("objects", []))
            matched: str | None = None
            found: dict[str, Any] | None = None
            for name in names:
                accepted = Detector.best(detections, name, confidence)
                if accepted is not None:
                    matched, found = name, accepted
                    break
            if matched is None or found is None:
                below = [
                    (name, candidate)
                    for name in names
                    if (candidate := Detector.best(detections, name)) is not None
                ]
                if below:
                    name, candidate = max(
                        below, key=lambda item: float(item[1]["confidence"])
                    )
                    decision = (
                        f"WAIT — {name} is only {float(candidate['confidence']):.0%}; "
                        f"the step requires {confidence:.0%}."
                    )
                else:
                    decision = (
                        "WAIT — none of the requested objects are visible: "
                        + ", ".join(names)
                        + "."
                    )
            elif action == "CLICK_FIRST_AVAILABLE":
                selected_index = names.index(matched)
                choice = "primary" if selected_index == 0 else "fallback"
                marker = _click_point(step, found, origin)
                offset = int(step.get("random_offset", 0))
                decision = (
                    f"READY — would select the {choice} object {matched} at "
                    f"{float(found['confidence']):.0%} and left-click near "
                    f"({marker[0]}, {marker[1]})"
                    f"{' with a ±' + str(offset) + ' px offset' if offset else ''}."
                )
                if selected_index > 0:
                    details.append(
                        "Higher-priority objects were unavailable: "
                        + ", ".join(names[:selected_index])
                        + "."
                    )
            else:
                try:
                    targets = destination_steps(step.get("target_steps", []))
                except ValueError as exc:
                    targets = []
                    details.append(f"Invalid destination list: {exc}")
                selected_index = names.index(matched)
                if selected_index >= len(targets):
                    decision = (
                        f"INVALID — {matched} matched, but it has no destination step."
                    )
                else:
                    route = targets[selected_index]
                    if route == 0:
                        destination = next_label
                    elif 1 <= route <= step_count:
                        destination = f"step {route}"
                    else:
                        destination = f"missing step {route}"
                    decision = (
                        f"MATCH — {matched} was accepted at "
                        f"{float(found['confidence']):.0%}; would continue to {destination}."
                    )
        else:
            name = str(step.get("object", "")).strip()
            found, reason = _target_status(detections, name, confidence)
            if action == "WAIT_UNTIL_DISAPPEARS":
                if found is None:
                    decision = f"PASS — {name} is not visible; would continue to {next_label}."
                    if reason and "below" in reason:
                        details.append(reason)
                else:
                    decision = (
                        f"WAIT — {name} is still visible at "
                        f"{float(found['confidence']):.0%}."
                    )
            elif found is None:
                decision = f"WAIT — {reason}"
            elif action == "WAIT_FOR_OBJECT":
                decision = (
                    f"PASS — {name} was accepted at "
                    f"{float(found['confidence']):.0%}; would continue to {next_label}."
                )
            else:
                marker = _click_point(step, found, origin)
                click_name = "right-click" if action == "RIGHT_CLICK_OBJECT" else "left-click"
                offset = int(step.get("random_offset", 0))
                decision = (
                    f"READY — {name} was accepted at "
                    f"{float(found['confidence']):.0%}; would {click_name} near "
                    f"({marker[0]}, {marker[1]})"
                    f"{' with a ±' + str(offset) + ' px offset' if offset else ''}."
                )

        if required > 1 and decision.startswith(("PASS —", "MATCH —", "READY —")):
            decision = (
                f"FRAME MATCH 1 OF {required} — {decision.split(' — ', 1)[1]} "
                f"A live run waits for {required} consecutive confirmations."
            )
    elif action == "WAIT":
        minimum = float(step.get("duration", 1.0))
        maximum = float(step.get("duration_max", minimum))
        value = f"{minimum:g} second(s)" if minimum == maximum else f"{minimum:g}–{maximum:g} seconds"
        decision = f"PREVIEW — would wait {value}, then continue to {next_label}."
    elif action in SCREEN_ACTIONS:
        if action == "MOVE_MOUSE":
            verb = "move the mouse"
        elif action == "DOUBLE_CLICK":
            verb = "double-click"
        elif action == "RIGHT_CLICK":
            verb = "right-click"
        else:
            verb = "left-click"
        try:
            bounds = watch_bounds or step.get("reference_bounds") or {
                "left": 0,
                "top": 0,
                "width": 1920,
                "height": 1080,
            }
            x, y, basis = resolve_step_coordinate(step, bounds)
            marker = (x, y)
            offset = int(step.get("random_offset", 0))
            decision = (
                f"PREVIEW — would {verb} at ({x}, {y}) using {basis}"
                f"{' with a ±' + str(offset) + ' px offset' if offset else ''}."
            )
            details.append(
                "Coordinate basis: "
                + coordinate_mode_label(step.get("coordinate_mode", "absolute"))
                + "."
            )
        except CoordinateReferenceError as exc:
            decision = f"INVALID — {exc}"
    elif action == "PRESS_KEY":
        decision = f"PREVIEW — would press {step.get('value', 'space')!s}."
    elif action == "TYPE_TEXT":
        decision = f"PREVIEW — would type {step.get('value', '')!r}."
    elif action == "GOTO_STEP":
        target = int(step.get("target_step", 1))
        status = "valid" if 1 <= target <= step_count else "missing"
        decision = f"PREVIEW — would go to step {target} ({status})."
    elif action == "REPEAT":
        target = int(step.get("target_step", 1))
        count = max(1, int(step.get("count", 1)))
        decision = f"PREVIEW — would repeat from step {target} up to {count} time(s)."
    elif action == "STOP":
        decision = "PREVIEW — would stop the macro."
    else:
        decision = f"UNKNOWN — {action_label} is not recognized by the debugger."

    return {
        "step_number": step_index + 1,
        "action": action,
        "action_label": action_label,
        "decision": decision,
        "details": details,
        "detections": detections,
        "origin": origin,
        "marker": marker,
        "safe": True,
    }
