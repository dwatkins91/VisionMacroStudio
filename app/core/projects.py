from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_FILE = "project.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_name(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " _-." else "_" for c in value).strip(
        " ."
    )
    return cleaned or "Untitled Project"


class ProjectError(RuntimeError):
    pass


class ProjectManager:
    def __init__(self) -> None:
        self.root: Path | None = None
        self.data: dict[str, Any] | None = None

    @property
    def is_open(self) -> bool:
        return self.root is not None and self.data is not None

    @property
    def project_file(self) -> Path:
        if self.root is None:
            raise ProjectError("No project is open.")
        return self.root / PROJECT_FILE

    def create(self, parent: Path, name: str) -> Path:
        project_name = safe_name(name)
        root = parent / project_name
        suffix = 2
        while root.exists():
            root = parent / f"{project_name} {suffix}"
            suffix += 1
        root.mkdir(parents=True)
        for folder in ("screenshots", "crops", "exports", "models", "logs"):
            (root / folder).mkdir()
        self.root = root
        self.data = {
            "format_version": 1,
            "id": str(uuid.uuid4()),
            "name": project_name,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "classes": [],
            "screenshots": [],
            "models": [],
            "macros": [],
            "settings": {},
        }
        self.save()
        return root

    def open(self, root: Path) -> None:
        project_file = root / PROJECT_FILE if root.is_dir() else root
        try:
            data = json.loads(project_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectError(f"Could not open project: {exc}") from exc
        if not isinstance(data, dict) or "screenshots" not in data:
            raise ProjectError(
                "This folder does not contain a valid Vision Macro Studio project."
            )
        self.root = project_file.parent
        self.data = data
        for key, default in (
            ("classes", []),
            ("models", []),
            ("macros", []),
            ("settings", {}),
        ):
            self.data.setdefault(key, default)
        self.ensure_macro_ids()

    def save(self) -> None:
        if not self.is_open:
            raise ProjectError("No project is open.")
        assert self.data is not None
        self.ensure_macro_ids()
        self.data["updated_at"] = utc_now()
        temp = self.project_file.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        temp.replace(self.project_file)

    def ensure_macro_ids(self) -> bool:
        """Give legacy macros stable identities for reusable-macro references."""
        if not self.data:
            return False
        changed = False
        seen: set[str] = set()
        for macro in self.data.get("macros", []):
            current = str(macro.get("id", "")).strip()
            if not current or current in seen:
                current = str(uuid.uuid4())
                macro["id"] = current
                changed = True
            seen.add(current)
        return changed

    def path(self, relative: str) -> Path:
        if self.root is None:
            raise ProjectError("No project is open.")
        return self.root / relative

    def add_class(self, name: str) -> str:
        if self.data is None:
            raise ProjectError("Open a project first.")
        name = safe_name(name).replace(" ", "_")
        if name not in self.data["classes"]:
            self.data["classes"].append(name)
            self.save()
        return name

    def rename_class(self, old: str, new: str) -> None:
        if self.data is None:
            raise ProjectError("Open a project first.")
        new = safe_name(new).replace(" ", "_")
        if new != old and new in self.data["classes"]:
            raise ProjectError(f"A class named {new!r} already exists.")
        self.data["classes"] = [
            new if item == old else item for item in self.data["classes"]
        ]
        for shot in self.data["screenshots"]:
            for annotation in shot.get("annotations", []):
                if annotation.get("class_name") == old:
                    annotation["class_name"] = new
        self.save()

    def remove_class(self, name: str) -> None:
        if self.data is None:
            raise ProjectError("Open a project first.")
        in_use = any(
            ann.get("class_name") == name
            for shot in self.data["screenshots"]
            for ann in shot.get("annotations", [])
        )
        if in_use:
            raise ProjectError("This class is still used by saved annotations.")
        self.data["classes"] = [item for item in self.data["classes"] if item != name]
        self.save()

    def add_screenshot(
        self, image, annotations: list[dict[str, Any]], origin: tuple[int, int]
    ) -> dict[str, Any]:
        if self.data is None or self.root is None:
            raise ProjectError("Open a project first.")
        shot_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        relative = f"screenshots/{shot_id}.png"
        image.save(self.root / relative)
        crop_files: list[str] = []
        for index, ann in enumerate(annotations):
            x, y, w, h = ann["bbox"]
            crop_rel = f"crops/{shot_id}_{index}_{safe_name(ann['class_name'])}.png"
            image.crop((x, y, x + w, y + h)).save(self.root / crop_rel)
            crop_files.append(crop_rel)
        record = {
            "id": shot_id,
            "image": relative,
            "width": image.width,
            "height": image.height,
            "origin": list(origin),
            "split": "train",
            "annotations": annotations,
            "crops": crop_files,
            "created_at": utc_now(),
        }
        self.data["screenshots"].append(record)
        for ann in annotations:
            self.add_class(ann["class_name"])
        self.save()
        return record

    def remove_screenshot(self, shot_id: str) -> None:
        if self.data is None:
            return
        target = next(
            (s for s in self.data["screenshots"] if s.get("id") == shot_id), None
        )
        if target:
            for relative in [target.get("image"), *target.get("crops", [])]:
                if relative:
                    try:
                        self.path(relative).unlink(missing_ok=True)
                    except OSError:
                        pass
            self.data["screenshots"].remove(target)
            self.save()

    def add_annotations(
        self, shot_id: str, annotations: list[dict[str, Any]]
    ) -> int:
        """Add approved model suggestions to an existing capture and create crops."""
        if not self.data or self.root is None:
            raise ProjectError("Open a project first.")
        shot = next(
            (item for item in self.data["screenshots"] if item.get("id") == shot_id),
            None,
        )
        if shot is None:
            raise ProjectError("That screenshot is no longer available.")
        image_path = self.path(shot["image"])
        from PIL import Image

        added = 0
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            for annotation in annotations:
                class_name = self.add_class(str(annotation.get("class_name", "")))
                bbox = [int(value) for value in annotation.get("bbox", [])]
                if len(bbox) != 4:
                    continue
                x, y, width, height = bbox
                x = max(0, min(x, image.width - 1))
                y = max(0, min(y, image.height - 1))
                width = max(1, min(width, image.width - x))
                height = max(1, min(height, image.height - y))
                saved = {"class_name": class_name, "bbox": [x, y, width, height]}
                shot.setdefault("annotations", []).append(saved)
                crop_index = len(shot.setdefault("crops", []))
                crop_rel = (
                    f"crops/{shot_id}_{crop_index}_{safe_name(class_name)}.png"
                )
                image.crop((x, y, x + width, y + height)).save(
                    self.path(crop_rel)
                )
                shot["crops"].append(crop_rel)
                added += 1
        self.save()
        return added

    def rename(self, name: str) -> None:
        if not self.is_open or self.data is None:
            raise ProjectError("No project is open.")
        self.data["name"] = safe_name(name)
        self.save()

    def export_zip(self, destination: Path) -> Path:
        if self.root is None:
            raise ProjectError("No project is open.")
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in self.root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(self.root.parent))
        return destination

    def import_zip(self, archive_path: Path, parent: Path) -> Path:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.namelist()
            if not members or any(
                Path(m).is_absolute() or ".." in Path(m).parts for m in members
            ):
                raise ProjectError("The project archive is invalid or unsafe.")
            top = Path(members[0]).parts[0]
            archive.extractall(parent)
        root = parent / top
        self.open(root)
        return root

    def delete_project(self) -> Path:
        if self.root is None:
            raise ProjectError("No project is open.")
        root = self.root
        self.root = None
        self.data = None
        shutil.rmtree(root)
        return root
