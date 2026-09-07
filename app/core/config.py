from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "capture_hotkey": "<f8>",
    "start_recording_hotkey": "<f6>",
    "stop_recording_hotkey": "<f7>",
    "run_macro_hotkey": "<f9>",
    "emergency_stop_hotkey": "<f12>",
    "train_split": 80,
    "confidence": 0.70,
    "detection_fps": 5,
    "preferred_monitor": 1,
    "device": "auto",
    "macro_overlay_enabled": True,
    "macro_overlay_x": 24,
    "macro_overlay_y": 24,
    "project_directory": "",
    "model_directory": "",
    "onboarding_completed": False,
}


def application_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home()))
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "VisionMacroStudio"


def default_project_dir() -> Path:
    return Path.home() / "Documents" / "Vision Macro Studio Projects"


class ConfigManager:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or application_data_dir() / "settings.json"
        self.data = deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
        if not self.data.get("project_directory"):
            self.data["project_directory"] = str(default_project_dir())
        if not self.data.get("model_directory"):
            self.data["model_directory"] = str(default_project_dir() / "Models")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def update(self, values: dict[str, Any]) -> None:
        self.data.update(values)
        self.save()
