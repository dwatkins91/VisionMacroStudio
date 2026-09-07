from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.projects import ProjectManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_model_name(project: ProjectManager) -> str:
    if not project.data:
        return "Model_v1"
    base = (
        "".join(c if c.isalnum() else "_" for c in project.data["name"]).strip("_")
        or "Model"
    )
    return f"{base}_Model_v{len(project.data['models']) + 1}"


def register_model(
    project: ProjectManager,
    name: str,
    relative_path: str,
    classes: list[str],
    metrics: dict[str, Any] | None = None,
    training: dict[str, Any] | None = None,
    reports: dict[str, str] | None = None,
) -> dict[str, Any]:
    if project.data is None:
        raise RuntimeError("Open a project first.")
    record = {
        "id": name,
        "name": name,
        "path": relative_path,
        "created_at": _now(),
        "classes": classes,
        "metrics": metrics or {},
        "training": training or {},
        "reports": reports or {},
        "notes": "",
        "accepted": False,
    }
    project.data["models"].append(record)
    project.save()
    return record


def training_source_label(model: dict[str, Any]) -> str:
    """Return a compact, backward-compatible description of model lineage."""
    source = model.get("training", {}).get("source", {})
    if source.get("type") == "project_model":
        return str(source.get("name") or source.get("model_id") or "Project model")
    if source.get("type") == "pretrained":
        return str(source.get("model_file") or "Pretrained base")
    return "Pretrained base"


def accept_model(project: ProjectManager, model_id: str) -> None:
    if not project.data:
        return
    for model in project.data["models"]:
        model["accepted"] = model.get("id") == model_id
    project.save()


def delete_model(project: ProjectManager, model_id: str) -> None:
    if not project.data:
        return
    model = next((m for m in project.data["models"] if m.get("id") == model_id), None)
    if not model:
        return
    path = project.path(model["path"])
    path.unlink(missing_ok=True)
    for report in model.get("reports", {}).values():
        report_path = project.path(str(report))
        report_path.unlink(missing_ok=True)
        try:
            report_path.parent.rmdir()
        except OSError:
            pass
    project.data["models"].remove(model)
    project.save()


def preferred_model(project: ProjectManager) -> dict[str, Any] | None:
    if not project.data or not project.data["models"]:
        return None
    return next(
        (m for m in project.data["models"] if m.get("accepted")),
        project.data["models"][-1],
    )


def resolve_model_path(project: ProjectManager, model: dict[str, Any]) -> Path:
    return project.path(model["path"])


def update_model_notes(
    project: ProjectManager, model_id: str, notes: str
) -> None:
    if not project.data:
        return
    model = next(
        (item for item in project.data.get("models", []) if item.get("id") == model_id),
        None,
    )
    if model is None:
        return
    model["notes"] = str(notes).strip()[:1000]
    project.save()
