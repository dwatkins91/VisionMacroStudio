"""Built-in, model-free examples for exploring macro logic safely."""

from __future__ import annotations

import uuid
from typing import Any


def sample_macros() -> list[dict[str, Any]]:
    return [
        {
            "id": str(uuid.uuid4()),
            "name": "01 - Safe Counter Tutorial",
            "time_limit_minutes": 1,
            "steps": [
                {"enabled": True, "action": "SECTION", "name": "Count five loops"},
                {
                    "enabled": True,
                    "action": "SET_VARIABLE",
                    "name": "Start counter",
                    "variable": "runs",
                    "variable_value": "0",
                },
                {
                    "enabled": True,
                    "action": "ADD_VARIABLE",
                    "name": "Add one",
                    "variable": "runs",
                    "amount": 1,
                },
                {
                    "enabled": True,
                    "action": "IF_VARIABLE",
                    "name": "Have we reached five?",
                    "variable": "runs",
                    "comparison": ">=",
                    "compare_value": "5",
                    "true_step": 6,
                    "false_step": 5,
                },
                {
                    "enabled": True,
                    "action": "GOTO_STEP",
                    "name": "Loop",
                    "target_step": 3,
                },
                {"enabled": True, "action": "STOP", "name": "Finished"},
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "02 - Priority Detection Template",
            "monitor_index": 0,
            "time_limit_minutes": 2,
            "steps": [
                {"enabled": True, "action": "SECTION", "name": "Find a target"},
                {
                    "enabled": True,
                    "action": "WAIT_FOR_ANY_OBJECT",
                    "name": "Prefer Start Button",
                    "comment": "Replace these sample classes with your own.",
                    "objects": ["Start_Button", "Done_Message"],
                    "target_steps": [4, 5],
                    "confidence": 0.7,
                    "timeout": 10,
                    "on_timeout": "go_to_step",
                    "failure_step": 5,
                    "required_consecutive_detections": 2,
                },
                {
                    "enabled": False,
                    "action": "CLICK_OBJECT",
                    "name": "Example click (disabled)",
                    "object": "Start_Button",
                    "confidence": 0.7,
                    "timeout": 5,
                },
                {"enabled": True, "action": "GOTO_STEP", "name": "Wait again", "target_step": 2},
                {"enabled": True, "action": "STOP", "name": "Finished or timed out"},
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "03 - Portable Coordinates Template",
            "monitor_index": 0,
            "time_limit_minutes": 1,
            "steps": [
                {"enabled": True, "action": "SECTION", "name": "Portable position"},
                {
                    "enabled": False,
                    "action": "MOVE_MOUSE",
                    "name": "Center of Watch source (disabled)",
                    "comment": "Safe-preview and enable only after selecting your own point.",
                    "coordinate_mode": "watch_relative",
                    "relative_x": 0.5,
                    "relative_y": 0.5,
                    "x": 0,
                    "y": 0,
                    "move_duration": 0.35,
                },
                {"enabled": True, "action": "STOP", "name": "Finished"},
            ],
        },
    ]


def populate_sample_project(project: Any) -> None:
    if not project.data:
        raise RuntimeError("Create the sample project before populating it.")
    project.data["classes"] = ["Start_Button", "Done_Message"]
    project.data["macros"] = sample_macros()
    project.save()
