from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.automation.control import (
    SUPPORTED_ACTIONS,
    destination_steps,
    object_names,
)
from app.automation.coordinates import (
    COORDINATE_MODES,
    CoordinateReferenceError,
    checked_normalized_region,
    coordinate_mode,
)
from app.automation.flow import (
    COMPARISON_OPERATORS,
    VARIABLE_ACTIONS,
    valid_variable_name,
)


MACRO_FILE_FORMAT = "vision-macro-studio/macro"
MACRO_FILE_VERSION = 3
SUPPORTED_MACRO_FILE_VERSIONS = {1, 2, 3}
MAX_MACRO_FILE_BYTES = 5 * 1024 * 1024
COORDINATE_ACTIONS = {"MOVE_MOUSE", "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"}
DETECTION_ACTIONS = {
    "WAIT_FOR_OBJECT",
    "WAIT_FOR_ANY_OBJECT",
    "WAIT_UNTIL_DISAPPEARS",
    "CLICK_OBJECT",
    "RIGHT_CLICK_OBJECT",
    "CLICK_FIRST_AVAILABLE",
}
DETECTION_CLICK_ACTIONS = {
    "CLICK_OBJECT",
    "RIGHT_CLICK_OBJECT",
    "CLICK_FIRST_AVAILABLE",
}


class MacroFormatError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_macro(macro: Any) -> dict[str, Any]:
    if not isinstance(macro, dict):
        raise MacroFormatError("The macro must be a JSON object.")
    name = macro.get("name")
    if not isinstance(name, str) or not name.strip():
        raise MacroFormatError("The macro does not have a valid name.")
    steps = macro.get("steps")
    if not isinstance(steps, list):
        raise MacroFormatError("The macro does not contain a valid step list.")
    if len(steps) > 10_000:
        raise MacroFormatError("The macro contains too many steps.")
    if macro.get("detection_region") is not None:
        try:
            checked_normalized_region(macro["detection_region"])
        except CoordinateReferenceError as exc:
            raise MacroFormatError(f"Invalid detection region: {exc}") from exc
    step_count = len(steps)
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise MacroFormatError(f"Step {index} is not a JSON object.")
        for field, limit in (("name", 120), ("comment", 500)):
            value = step.get(field, "")
            if not isinstance(value, str):
                raise MacroFormatError(
                    f"Step {index} has an invalid {field}."
                )
            if len(value) > limit:
                raise MacroFormatError(
                    f"Step {index} {field} is longer than {limit} characters."
                )
        action = step.get("action")
        if action not in SUPPORTED_ACTIONS:
            raise MacroFormatError(
                f"Step {index} uses an unsupported action: {action!r}."
            )
        if action == "SECTION" and not str(step.get("name", "")).strip():
            raise MacroFormatError(f"Step {index} needs a section title.")
        if action == "WAIT_FOR_ANY_OBJECT":
            names = object_names(step.get("objects", []))
            try:
                targets = destination_steps(step.get("target_steps", []))
            except ValueError as exc:
                raise MacroFormatError(f"Step {index}: {exc}") from exc
            if not names or len(names) != len(targets):
                raise MacroFormatError(
                    f"Step {index} needs one destination for every object."
                )
            for target in targets:
                if target != 0 and not 1 <= target <= step_count:
                    raise MacroFormatError(
                        f"Step {index} points to missing step {target}."
                    )
        if action == "CLICK_FIRST_AVAILABLE" and not object_names(
            step.get("objects", [])
        ):
            raise MacroFormatError(f"Step {index} does not contain object names.")
        if action in {
            "WAIT_FOR_OBJECT",
            "WAIT_UNTIL_DISAPPEARS",
            "CLICK_OBJECT",
            "RIGHT_CLICK_OBJECT",
        } and not object_names([step.get("object", "")]):
            raise MacroFormatError(f"Step {index} does not contain an object name.")
        if action in {"GOTO_STEP", "REPEAT"}:
            try:
                target = int(step.get("target_step", 0))
            except (TypeError, ValueError) as exc:
                raise MacroFormatError(
                    f"Step {index} has an invalid destination."
                ) from exc
            if not 1 <= target <= step_count:
                raise MacroFormatError(
                    f"Step {index} points to missing step {target}."
                )
        if action in VARIABLE_ACTIONS:
            variable_name = str(step.get("variable", "")).strip()
            if not valid_variable_name(variable_name):
                raise MacroFormatError(
                    f"Step {index} needs a variable name that begins with a letter "
                    "or underscore and contains only letters, numbers, and underscores."
                )
        if action == "ADD_VARIABLE":
            try:
                float(step.get("amount", 1))
            except (TypeError, ValueError) as exc:
                raise MacroFormatError(
                    f"Step {index} has an invalid counter amount."
                ) from exc
        if action == "IF_VARIABLE":
            operator = str(step.get("comparison", "=="))
            if operator not in COMPARISON_OPERATORS:
                raise MacroFormatError(
                    f"Step {index} uses an unsupported variable comparison."
                )
            for field in ("true_step", "false_step"):
                try:
                    target = int(step.get(field, 0))
                except (TypeError, ValueError) as exc:
                    raise MacroFormatError(
                        f"Step {index} has an invalid variable-branch destination."
                    ) from exc
                if target != 0 and not 1 <= target <= step_count:
                    raise MacroFormatError(
                        f"Step {index} points to missing step {target}."
                    )
        if action == "CALL_MACRO" and not (
            str(step.get("macro_id", "")).strip()
            or str(step.get("macro_name", "")).strip()
        ):
            raise MacroFormatError(
                f"Step {index} does not identify a reusable macro."
            )
        if action in COORDINATE_ACTIONS:
            raw_mode = step.get("coordinate_mode", "absolute")
            if str(raw_mode) not in COORDINATE_MODES:
                raise MacroFormatError(
                    f"Step {index} uses an unsupported coordinate basis: {raw_mode!r}."
                )
            mode = coordinate_mode(raw_mode)
            if mode == "absolute":
                required_values = ("x", "y")
            else:
                required_values = ("relative_x", "relative_y")
            for axis in required_values:
                try:
                    value = float(step[axis])
                except (KeyError, TypeError, ValueError) as exc:
                    raise MacroFormatError(
                        f"Step {index} does not have a valid {axis.replace('_', ' ')} value."
                    ) from exc
                if axis.startswith("relative_") and not 0 <= value <= 1:
                    raise MacroFormatError(
                        f"Step {index} relative coordinates must be between 0 and 1."
                    )
            if mode == "window_relative" and not str(
                step.get("window_title", "")
            ).strip():
                raise MacroFormatError(
                    f"Step {index} does not identify an application window."
                )
        if action in DETECTION_ACTIONS:
            try:
                required = int(step.get("required_consecutive_detections", 1))
                maximum = int(step.get("max_detection_attempts", 0))
            except (TypeError, ValueError) as exc:
                raise MacroFormatError(
                    f"Step {index} has invalid detection-stability limits."
                ) from exc
            if not 1 <= required <= 20:
                raise MacroFormatError(
                    f"Step {index} consecutive confirmations must be from 1 to 20."
                )
            if not 0 <= maximum <= 100_000:
                raise MacroFormatError(
                    f"Step {index} maximum detection checks must be from 0 to 100000."
                )
            timeout_behavior = str(step.get("on_timeout", "stop"))
            if timeout_behavior not in {"stop", "continue", "go_to_step"}:
                raise MacroFormatError(
                    f"Step {index} has an unsupported timeout behavior."
                )
            if timeout_behavior == "go_to_step":
                try:
                    failure_step = int(step.get("failure_step", 0))
                except (TypeError, ValueError) as exc:
                    raise MacroFormatError(
                        f"Step {index} has an invalid failure destination."
                    ) from exc
                if not 1 <= failure_step <= step_count:
                    raise MacroFormatError(
                        f"Step {index} points to missing step {failure_step}."
                    )
        if action in DETECTION_CLICK_ACTIONS:
            try:
                cooldown = float(step.get("click_cooldown_seconds", 0))
                disappear_timeout = float(
                    step.get("post_click_disappear_timeout", 10)
                )
            except (TypeError, ValueError) as exc:
                raise MacroFormatError(
                    f"Step {index} has invalid clicked-object stability values."
                ) from exc
            if not 0 <= cooldown <= 3600:
                raise MacroFormatError(
                    f"Step {index} clicked-object cooldown must be from 0 to 3600 seconds."
                )
            if not 0 <= disappear_timeout <= 3600:
                raise MacroFormatError(
                    f"Step {index} disappear wait timeout must be from 0 to 3600 seconds."
                )
            wait_after_click = step.get(
                "wait_after_click_until_disappears", False
            )
            if not isinstance(wait_after_click, bool):
                raise MacroFormatError(
                    f"Step {index} wait-after-click setting must be true or false."
                )
    result = deepcopy(macro)
    result["name"] = name.strip()
    return result


def export_macro_file(
    path: Path,
    macro: dict[str, Any],
    app_version: str,
    screen_layout: list[dict[str, int]] | None = None,
    macro_library: list[dict[str, Any]] | None = None,
) -> Path:
    checked = validate_macro(macro)
    dependencies = bundled_macro_dependencies(checked, macro_library or [])
    payload = {
        "format": MACRO_FILE_FORMAT,
        "format_version": MACRO_FILE_VERSION,
        "app_version": app_version,
        "exported_at": _now(),
        "screen_layout": screen_layout or [],
        "macro": checked,
        "dependencies": dependencies,
    }
    path = Path(path)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path


def import_macro_file(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(path)
    try:
        if path.stat().st_size > MAX_MACRO_FILE_BYTES:
            raise MacroFormatError("That macro file is unexpectedly large.")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except MacroFormatError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MacroFormatError(f"The macro file could not be read: {exc}") from exc
    if not isinstance(payload, dict):
        raise MacroFormatError("The macro file must contain a JSON object.")
    if payload.get("format") == MACRO_FILE_FORMAT:
        version = payload.get("format_version")
        if version not in SUPPORTED_MACRO_FILE_VERSIONS:
            raise MacroFormatError(
                f"Macro format version {version!r} is not supported by this app."
            )
        macro = validate_macro(payload.get("macro"))
        metadata = {
            "format_version": version,
            "app_version": payload.get("app_version"),
            "exported_at": payload.get("exported_at"),
            "screen_layout": payload.get("screen_layout", []),
            "dependencies": [],
        }
        if version >= 3:
            dependencies = payload.get("dependencies", [])
            if not isinstance(dependencies, list):
                raise MacroFormatError("The reusable-macro bundle is invalid.")
            metadata["dependencies"] = [
                validate_macro(dependency) for dependency in dependencies
            ]
        return macro, metadata
    if "name" in payload and "steps" in payload:
        return validate_macro(payload), {}
    raise MacroFormatError("This is not a Vision Macro Studio macro file.")


def unique_macro_name(name: str, existing_names: list[str]) -> str:
    existing = {value.casefold() for value in existing_names}
    if name.casefold() not in existing:
        return name
    candidate = f"{name} (Imported)"
    number = 2
    while candidate.casefold() in existing:
        candidate = f"{name} (Imported {number})"
        number += 1
    return candidate


def macro_reference(step: dict[str, Any]) -> tuple[str, str]:
    return (
        str(step.get("macro_id", "")).strip(),
        str(step.get("macro_name", "")).strip(),
    )


def find_macro_reference(
    step: dict[str, Any], macro_library: list[dict[str, Any]]
) -> dict[str, Any] | None:
    macro_id, macro_name = macro_reference(step)
    if macro_id:
        match = next(
            (item for item in macro_library if str(item.get("id", "")) == macro_id),
            None,
        )
        if match is not None:
            return match
    if macro_name:
        key = macro_name.casefold()
        return next(
            (item for item in macro_library if str(item.get("name", "")).casefold() == key),
            None,
        )
    return None


def bundled_macro_dependencies(
    macro: dict[str, Any], macro_library: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Collect called macros recursively for a self-contained format-v3 export."""
    collected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    root_identity = (
        str(macro.get("id", "")),
        str(macro.get("name", "")).casefold(),
    )

    def collect(source: dict[str, Any]) -> None:
        for step in source.get("steps", []):
            if step.get("action") != "CALL_MACRO":
                continue
            target = find_macro_reference(step, macro_library)
            if target is None:
                continue
            identity = (
                str(target.get("id", "")),
                str(target.get("name", "")).casefold(),
            )
            if identity in seen or identity == root_identity:
                continue
            seen.add(identity)
            checked = validate_macro(target)
            collected.append(checked)
            collect(target)

    collect(macro)
    return collected


def referenced_objects(macro: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for step in macro.get("steps", []):
        if step.get("object"):
            names.extend(object_names([step["object"]]))
        names.extend(object_names(step.get("objects", [])))
    return list(dict.fromkeys(names))


def has_coordinate_steps(macro: dict[str, Any]) -> bool:
    return any(
        step.get("action") in COORDINATE_ACTIONS
        for step in macro.get("steps", [])
    )


def has_absolute_coordinate_steps(macro: dict[str, Any]) -> bool:
    return any(
        step.get("action") in COORDINATE_ACTIONS
        and coordinate_mode(step.get("coordinate_mode", "absolute")) == "absolute"
        for step in macro.get("steps", [])
    )


def _remap_step_destinations(
    step: dict[str, Any],
    old_to_new: dict[int, int],
    missing_target: int | None = None,
    removed_step: int | None = None,
) -> dict[str, Any]:
    """Remap numbered branches after an editor changes the row order."""
    result = deepcopy(step)

    def mapped(value: Any) -> int:
        target = int(value)
        if target == 0:
            return 0
        if removed_step is not None and target == removed_step:
            return missing_target if missing_target is not None else target
        return old_to_new.get(target, target)

    action = result.get("action")
    if action == "WAIT_FOR_ANY_OBJECT":
        try:
            result["target_steps"] = [
                mapped(target)
                for target in destination_steps(result.get("target_steps", []))
            ]
        except (TypeError, ValueError):
            pass
    elif action in {"GOTO_STEP", "REPEAT"} and "target_step" in result:
        try:
            result["target_step"] = mapped(result["target_step"])
        except (TypeError, ValueError):
            pass
    elif action == "IF_VARIABLE":
        for field in ("true_step", "false_step"):
            if field in result:
                try:
                    result[field] = mapped(result[field])
                except (TypeError, ValueError):
                    pass
    if action in DETECTION_ACTIONS and result.get("on_timeout") == "go_to_step":
        try:
            result["failure_step"] = mapped(result.get("failure_step", 0))
        except (TypeError, ValueError):
            pass
    return result


def reorder_steps_preserving_destinations(
    steps: list[dict[str, Any]], source_index: int, target_index: int
) -> list[dict[str, Any]]:
    """Move one step and keep every branch attached to its original target."""
    if not 0 <= source_index < len(steps):
        raise IndexError("The source step does not exist.")
    if not 0 <= target_index < len(steps):
        raise IndexError("The destination row does not exist.")
    entries = list(enumerate(deepcopy(steps)))
    moved = entries.pop(source_index)
    entries.insert(target_index, moved)
    old_to_new = {
        old_index + 1: new_index + 1
        for new_index, (old_index, _step) in enumerate(entries)
    }
    return [
        _remap_step_destinations(step, old_to_new)
        for _old_index, step in entries
    ]


def insert_step_preserving_destinations(
    steps: list[dict[str, Any]], target_index: int, new_step: dict[str, Any]
) -> list[dict[str, Any]]:
    """Insert a step and shift existing branch destinations safely."""
    if not 0 <= target_index <= len(steps):
        raise IndexError("The insertion row does not exist.")
    entries: list[tuple[int | None, dict[str, Any]]] = list(
        enumerate(deepcopy(steps))
    )
    entries.insert(target_index, (None, deepcopy(new_step)))
    old_to_new = {
        old_index + 1: new_index + 1
        for new_index, (old_index, _step) in enumerate(entries)
        if old_index is not None
    }
    return [
        _remap_step_destinations(step, old_to_new)
        for _old_index, step in entries
    ]


def duplicate_step_preserving_destinations(
    steps: list[dict[str, Any]], source_index: int
) -> list[dict[str, Any]]:
    """Duplicate a step immediately below it without breaking numbered routes."""
    if not 0 <= source_index < len(steps):
        raise IndexError("The step to duplicate does not exist.")
    entries: list[tuple[int | None, dict[str, Any]]] = list(
        enumerate(deepcopy(steps))
    )
    entries.insert(source_index + 1, (None, deepcopy(steps[source_index])))
    old_to_new = {
        old_index + 1: new_index + 1
        for new_index, (old_index, _step) in enumerate(entries)
        if old_index is not None
    }
    return [
        _remap_step_destinations(step, old_to_new)
        for _old_index, step in entries
    ]


def delete_step_preserving_destinations(
    steps: list[dict[str, Any]], source_index: int
) -> list[dict[str, Any]]:
    """Delete a step, preserve other targets, and expose routes to the removed row."""
    if not 0 <= source_index < len(steps):
        raise IndexError("The step to delete does not exist.")
    removed_step = source_index + 1
    entries = [
        (old_index, deepcopy(step))
        for old_index, step in enumerate(steps)
        if old_index != source_index
    ]
    old_to_new = {
        old_index + 1: new_index + 1
        for new_index, (old_index, _step) in enumerate(entries)
    }
    missing_target = len(entries) + 1
    return [
        _remap_step_destinations(
            step,
            old_to_new,
            missing_target=missing_target,
            removed_step=removed_step,
        )
        for _old_index, step in entries
    ]
