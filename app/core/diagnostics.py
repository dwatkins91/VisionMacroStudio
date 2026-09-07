"""Create intentionally small, scrubbed diagnostic archives for bug reports."""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import __license__, __repository_url__, __version__
from app.core.config import application_data_dir
from app.core.system_check import CheckResult, checks_summary


SAFE_SETTING_KEYS = (
    "capture_hotkey",
    "start_recording_hotkey",
    "stop_recording_hotkey",
    "run_macro_hotkey",
    "emergency_stop_hotkey",
    "train_split",
    "confidence",
    "detection_fps",
    "preferred_monitor",
    "device",
    "macro_overlay_enabled",
)


def redact_text(text: str, extra_paths: list[str | Path] | None = None) -> str:
    """Remove common personal identifiers and local paths from diagnostic text."""

    redacted = str(text)
    replacements: list[tuple[str, str]] = []
    for value, label in (
        (Path.home(), "<HOME>"),
        (application_data_dir(), "<APP_DATA>"),
    ):
        replacements.append((str(value), label))
    for value in extra_paths or []:
        if str(value).strip():
            replacements.append((str(value), "<PROJECT_DIR>"))
    for value, label in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        redacted = redacted.replace(value, label)
        redacted = redacted.replace(value.replace("\\", "/"), label)
    username = os.getenv("USERNAME") or os.getenv("USER")
    if username:
        redacted = re.sub(re.escape(username), "<USER>", redacted, flags=re.IGNORECASE)
    redacted = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "<EMAIL>",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(?i)\b[A-Z]:\\Users\\[^\\\s]+",
        r"C:\\Users\\<USER>",
        redacted,
    )
    return redacted


def _safe_macro(macro: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(macro)
    for step in result.get("steps", []):
        if str(step.get("action", "")).upper() == "TYPE_TEXT" and step.get("text"):
            step["text"] = "<REDACTED TYPED TEXT>"
        if step.get("window_title"):
            step["window_title"] = "<REDACTED WINDOW TITLE>"
        if step.get("window_class"):
            step["window_class"] = "<REDACTED WINDOW CLASS>"
    return result


def _project_summary(project: Any) -> dict[str, Any] | None:
    if project is None or not getattr(project, "data", None):
        return None
    data = project.data
    accepted = next(
        (model for model in data.get("models", []) if model.get("accepted")), None
    )
    model_summary = None
    if accepted:
        model_summary = {
            "name": accepted.get("name"),
            "classes": accepted.get("classes", []),
            "metrics": accepted.get("metrics", {}),
            "training": accepted.get("training", {}),
        }
        if isinstance(model_summary["training"], dict):
            model_summary["training"].pop("run_dir", None)
    return {
        "name": "<PROJECT>",
        "format_version": data.get("format_version"),
        "counts": {
            "classes": len(data.get("classes", [])),
            "screenshots": len(data.get("screenshots", [])),
            "models": len(data.get("models", [])),
            "macros": len(data.get("macros", [])),
        },
        "classes": list(data.get("classes", [])),
        "accepted_model": model_summary,
    }


def diagnostic_payload(
    config: dict[str, Any],
    project: Any = None,
    checks: list[CheckResult] | None = None,
) -> dict[str, Any]:
    return {
        "application": {
            "name": "Vision Macro Studio",
            "version": __version__,
            "license": __license__,
            "source": f"{__repository_url__}/tree/v{__version__}",
            "packaged": bool(getattr(sys, "frozen", False)),
        },
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime": {
            "operating_system": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "settings": {key: config.get(key) for key in SAFE_SETTING_KEYS},
        "project": _project_summary(project),
        "system_check": checks_summary(checks or []),
    }


def create_diagnostic_package(
    destination: Path,
    *,
    config: dict[str, Any],
    project: Any = None,
    log_text: str = "",
    checks: list[CheckResult] | None = None,
) -> Path:
    """Write a ZIP with no captures, model files, project paths, or typed text."""

    destination = Path(destination)
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    project_paths = [project.root] if project is not None and getattr(project, "root", None) else []
    lines = redact_text(log_text, project_paths).splitlines()[-100:]
    macros = []
    if project is not None and getattr(project, "data", None):
        macros = [_safe_macro(item) for item in project.data.get("macros", [])]
    readme = (
        "VISION MACRO STUDIO DIAGNOSTIC PACKAGE\n\n"
        "Review every file before attaching this ZIP to a public issue. This package "
        "contains a scrubbed environment report, macro logic, and the last 100 visible "
        "log lines. Typed-text contents and window titles are redacted. It deliberately "
        "does not include screenshots, labels, trained models, project paths, or settings "
        "paths.\n"
    )
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("READ_ME_FIRST.txt", readme)
        archive.writestr(
            "diagnostics.json",
            redact_text(
                json.dumps(diagnostic_payload(config, project, checks), indent=2),
                project_paths,
            ),
        )
        archive.writestr(
            "macros.redacted.json",
            redact_text(json.dumps({"macros": macros}, indent=2), project_paths),
        )
        archive.writestr("last_100_log_lines.txt", "\n".join(lines))
    return destination
