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


MACRO_FILE_FORMAT = "vision-macro-studio/macro"
MACRO_FILE_VERSION = 1
MAX_MACRO_FILE_BYTES = 5 * 1024 * 1024
COORDINATE_ACTIONS = {"MOVE_MOUSE", "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"}


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
    step_count = len(steps)
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise MacroFormatError(f"Step {index} is not a JSON object.")
        action = step.get("action")
        if action not in SUPPORTED_ACTIONS:
            raise MacroFormatError(
                f"Step {index} uses an unsupported action: {action!r}."
            )
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
        if action in COORDINATE_ACTIONS:
            for axis in ("x", "y"):
                try:
                    int(step[axis])
                except (KeyError, TypeError, ValueError) as exc:
                    raise MacroFormatError(
                        f"Step {index} does not have a valid screen {axis.upper()} coordinate."
                    ) from exc
    result = deepcopy(macro)
    result["name"] = name.strip()
    return result


def export_macro_file(
    path: Path,
    macro: dict[str, Any],
    app_version: str,
    screen_layout: list[dict[str, int]] | None = None,
) -> Path:
    checked = validate_macro(macro)
    payload = {
        "format": MACRO_FILE_FORMAT,
        "format_version": MACRO_FILE_VERSION,
        "app_version": app_version,
        "exported_at": _now(),
        "screen_layout": screen_layout or [],
        "macro": checked,
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
        if version != MACRO_FILE_VERSION:
            raise MacroFormatError(
                f"Macro format version {version!r} is not supported by this app."
            )
        macro = validate_macro(payload.get("macro"))
        metadata = {
            "app_version": payload.get("app_version"),
            "exported_at": payload.get("exported_at"),
            "screen_layout": payload.get("screen_layout", []),
        }
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
