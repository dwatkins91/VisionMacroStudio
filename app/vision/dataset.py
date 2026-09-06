from __future__ import annotations

import random
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import pstdev
from typing import Any

import yaml

from app.core.projects import ProjectManager


def class_counts(project: ProjectManager) -> Counter:
    counts: Counter = Counter()
    if project.data:
        for shot in project.data["screenshots"]:
            for ann in shot.get("annotations", []):
                counts[ann["class_name"]] += 1
    return counts


def automatic_split(
    project: ProjectManager, train_percent: int = 80, seed: int | None = None
) -> None:
    """Stratified-ish image split that keeps every screenshot and its boxes together."""
    if not project.data:
        return
    rng = random.Random(seed)
    shots = list(project.data["screenshots"])
    rng.shuffle(shots)
    by_primary: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for shot in shots:
        labels = [a["class_name"] for a in shot.get("annotations", [])]
        primary = (
            min(labels, key=lambda name: class_counts(project)[name])
            if labels
            else "__empty__"
        )
        by_primary[primary].append(shot)
    for group in by_primary.values():
        rng.shuffle(group)
        train_count = max(1, round(len(group) * train_percent / 100)) if group else 0
        if len(group) > 1:
            train_count = min(train_count, len(group) - 1)
        for index, shot in enumerate(group):
            shot["split"] = "train" if index < train_count else "val"
    project.save()


def quality_warnings(project: ProjectManager) -> list[str]:
    if not project.data:
        return ["Open a project and capture some objects first."]
    warnings: list[str] = []
    counts = class_counts(project)
    if not counts:
        return ["No labeled objects have been captured yet."]
    largest = max(counts.values())
    for name in project.data["classes"]:
        count = counts[name]
        if count < 20:
            warnings.append(
                f"{name} only has {count} examples. Aim for at least 20–50 varied examples to begin."
            )
        elif count < 50:
            warnings.append(
                f"{name} has {count} examples. More variety may improve reliability."
            )
        if largest >= 2 * max(1, count):
            warnings.append(
                f"{name} has far fewer samples than the largest class ({largest})."
            )
        centers_x: list[float] = []
        centers_y: list[float] = []
        relative_sizes: list[float] = []
        for shot in project.data["screenshots"]:
            for ann in shot.get("annotations", []):
                if ann["class_name"] != name:
                    continue
                x, y, w, h = ann["bbox"]
                centers_x.append((x + w / 2) / shot["width"])
                centers_y.append((y + h / 2) / shot["height"])
                relative_sizes.append((w * h) / (shot["width"] * shot["height"]))
        if (
            len(centers_x) >= 8
            and pstdev(centers_x) < 0.08
            and pstdev(centers_y) < 0.08
        ):
            warnings.append(
                f"Most {name} captures are in nearly the same screen location. Move it around when possible."
            )
        if len(relative_sizes) >= 8 and pstdev(relative_sizes) < 0.002:
            warnings.append(
                f"Most {name} captures are nearly the same size. Include closer and farther examples."
            )
    train = sum(s.get("split") == "train" for s in project.data["screenshots"])
    val = sum(s.get("split") == "val" for s in project.data["screenshots"])
    if val == 0:
        warnings.append(
            "There are no validation images. Run Automatic Split before training."
        )
    if train == 0:
        warnings.append("There are no training images.")
    if not warnings:
        warnings.append(
            "No obvious dataset problems found. Background and appearance variety still matter."
        )
    return warnings


def export_yolo(project: ProjectManager) -> Path:
    if not project.data or not project.root:
        raise RuntimeError("Open a project first.")
    if not project.data["classes"]:
        raise RuntimeError("Create at least one object class.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_root = project.path(f"exports/yolo_{stamp}")
    for split in ("train", "val"):
        (export_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (export_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    class_index = {name: i for i, name in enumerate(project.data["classes"])}
    valid_count = 0
    for shot in project.data["screenshots"]:
        split = shot.get("split", "train")
        if split not in ("train", "val"):
            split = "train"
        source = project.path(shot["image"])
        if not source.exists():
            continue
        target = export_root / "images" / split / source.name
        shutil.copy2(source, target)
        lines: list[str] = []
        width, height = shot["width"], shot["height"]
        for ann in shot.get("annotations", []):
            if ann["class_name"] not in class_index:
                continue
            x, y, w, h = ann["bbox"]
            cx = (x + w / 2) / width
            cy = (y + h / 2) / height
            lines.append(
                f"{class_index[ann['class_name']]} {cx:.8f} {cy:.8f} {w / width:.8f} {h / height:.8f}"
            )
        (export_root / "labels" / split / f"{source.stem}.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )
        valid_count += 1
    if valid_count == 0:
        raise RuntimeError("No usable screenshots were found.")
    config = {
        "path": str(export_root.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": {i: name for name, i in class_index.items()},
    }
    (export_root / "dataset.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    return export_root / "dataset.yaml"
