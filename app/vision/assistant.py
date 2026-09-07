from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from statistics import pstdev
from typing import Any

from PIL import Image

from app.core.projects import ProjectManager
from app.vision.detector import class_name_key


def bbox_iou(first: list[int], second: list[int]) -> float:
    ax, ay, aw, ah = (float(value) for value in first)
    bx, by, bw, bh = (float(value) for value in second)
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def merge_label_suggestions(
    existing: list[dict[str, Any]],
    detections: list[dict[str, Any]],
    classes: list[str],
    *,
    minimum_confidence: float = 0.25,
    duplicate_iou: float = 0.55,
) -> list[dict[str, Any]]:
    """Convert detections to annotations while rejecting duplicates/unknown classes."""
    class_lookup = {class_name_key(name): name for name in classes}
    suggestions: list[dict[str, Any]] = []
    for detection in sorted(
        detections,
        key=lambda item: float(item.get("confidence", 0)),
        reverse=True,
    ):
        confidence = float(detection.get("confidence", 0))
        class_name = class_lookup.get(
            class_name_key(str(detection.get("class_name", "")))
        )
        bbox = [int(round(value)) for value in detection.get("bbox", [])]
        if class_name is None or confidence < minimum_confidence or len(bbox) != 4:
            continue
        duplicate = any(
            class_name_key(str(annotation.get("class_name", "")))
            == class_name_key(class_name)
            and bbox_iou(bbox, list(annotation.get("bbox", []))) >= duplicate_iou
            for annotation in [*existing, *suggestions]
            if len(annotation.get("bbox", [])) == 4
        )
        if duplicate:
            continue
        suggestions.append(
            {
                "class_name": class_name,
                "bbox": bbox,
                "confidence": confidence,
                "source": "model_suggestion",
            }
        )
    return suggestions


def dataset_quality_rows(project: ProjectManager) -> list[dict[str, Any]]:
    if not project.data:
        return []
    rows: list[dict[str, Any]] = []
    for class_name in project.data.get("classes", []):
        instances = 0
        train_images: set[str] = set()
        val_images: set[str] = set()
        sizes: list[float] = []
        centers_x: list[float] = []
        centers_y: list[float] = []
        for shot in project.data.get("screenshots", []):
            for annotation in shot.get("annotations", []):
                if annotation.get("class_name") != class_name:
                    continue
                instances += 1
                target = train_images if shot.get("split") == "train" else val_images
                target.add(str(shot.get("id", "")))
                x, y, width, height = annotation["bbox"]
                image_width = max(1, int(shot.get("width", 1)))
                image_height = max(1, int(shot.get("height", 1)))
                sizes.append(width * height / (image_width * image_height))
                centers_x.append((x + width / 2) / image_width)
                centers_y.append((y + height / 2) / image_height)
        position_spread = (
            (pstdev(centers_x) + pstdev(centers_y)) / 2
            if len(centers_x) >= 2
            else 0.0
        )
        if instances < 20:
            recommendation = "Add more varied examples"
        elif not val_images:
            recommendation = "Add validation images"
        elif position_spread < 0.08 and instances >= 8:
            recommendation = "Vary screen position"
        elif sizes and pstdev(sizes) < 0.002 and instances >= 8:
            recommendation = "Vary apparent size"
        else:
            recommendation = "Coverage looks reasonable"
        rows.append(
            {
                "class_name": class_name,
                "instances": instances,
                "train_images": len(train_images),
                "val_images": len(val_images),
                "average_box_percent": (sum(sizes) / len(sizes) * 100) if sizes else 0,
                "position_spread": position_spread,
                "recommendation": recommendation,
            }
        )
    return rows


def _average_hash(path: Path, size: int = 12) -> int:
    with Image.open(path) as image:
        values = list(image.convert("L").resize((size, size)).getdata())
    average = sum(values) / max(1, len(values))
    result = 0
    for value in values:
        result = (result << 1) | int(value >= average)
    return result


def near_duplicate_pairs(
    project: ProjectManager, *, max_distance: int = 5, limit: int = 500
) -> tuple[list[tuple[str, str, int]], bool]:
    """Find visually near-identical captures using a dependency-free average hash."""
    if not project.data:
        return [], False
    shots = project.data.get("screenshots", [])[:limit]
    hashes: list[tuple[str, int]] = []
    for shot in shots:
        path = project.path(str(shot.get("image", "")))
        if path.is_file():
            try:
                hashes.append((str(shot.get("id", path.stem)), _average_hash(path)))
            except OSError:
                pass
    pairs: list[tuple[str, str, int]] = []
    for index, (first_id, first_hash) in enumerate(hashes):
        for second_id, second_hash in hashes[index + 1 :]:
            distance = (first_hash ^ second_hash).bit_count()
            if distance <= max_distance:
                pairs.append((first_id, second_id, distance))
    return pairs, len(project.data.get("screenshots", [])) > limit


def extract_training_metrics(results: Any, classes: list[str]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    result_dict = getattr(results, "results_dict", {}) or {}
    try:
        metrics["mAP50"] = float(result_dict.get("metrics/mAP50(B)", 0.0))
        metrics["mAP50-95"] = float(
            result_dict.get("metrics/mAP50-95(B)", 0.0)
        )
    except (TypeError, ValueError):
        pass
    box = getattr(results, "box", None)

    def values(name: str) -> list[Any]:
        raw = getattr(box, name, None) if box is not None else None
        return list(raw) if raw is not None else []

    ap50 = values("ap50")
    maps = values("maps")
    class_indices = values("ap_class_index")
    if ap50:
        if not class_indices:
            class_indices = list(range(len(ap50)))
        per_class: dict[str, dict[str, float]] = {}
        for metric_index, class_index in enumerate(class_indices):
            class_number = int(class_index)
            if not 0 <= class_number < len(classes) or metric_index >= len(ap50):
                continue
            per_class[classes[class_number]] = {
                "mAP50": float(ap50[metric_index]),
                "mAP50-95": float(maps[metric_index]) if metric_index < len(maps) else 0.0,
            }
        if per_class:
            metrics["per_class"] = per_class
    return metrics


def preserve_training_reports(run_dir: Path, report_dir: Path) -> dict[str, str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    reports: dict[str, str] = {}
    candidates = {
        "confusion_matrix": "confusion_matrix.png",
        "confusion_matrix_normalized": "confusion_matrix_normalized.png",
        "results_plot": "results.png",
        "results_csv": "results.csv",
    }
    for key, filename in candidates.items():
        source = run_dir / filename
        if source.is_file():
            destination = report_dir / filename
            shutil.copy2(source, destination)
            reports[key] = str(destination)
    return reports


def best_model_by_map50(models: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = [
        model
        for model in models
        if isinstance(model.get("metrics", {}).get("mAP50"), (int, float))
    ]
    return max(scored, key=lambda item: item["metrics"]["mAP50"], default=None)


def confusion_candidates(model: dict[str, Any]) -> list[str]:
    reports = model.get("reports", {})
    return [
        path
        for key in ("confusion_matrix_normalized", "confusion_matrix")
        if (path := str(reports.get(key, "")))
    ]
