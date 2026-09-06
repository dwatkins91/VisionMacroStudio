from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def class_name_key(value: str) -> str:
    """Normalize harmless case and separator differences in class names."""
    return re.sub(r"[^0-9a-z]+", "_", str(value).casefold()).strip("_")


def to_ultralytics_source(image: Image.Image | np.ndarray) -> np.ndarray:
    """Convert the app's RGB screenshots to OpenCV/Ultralytics BGR arrays."""
    if isinstance(image, Image.Image):
        rgb = np.asarray(image.convert("RGB"))
    else:
        rgb = np.asarray(image)
    if rgb.ndim == 3 and rgb.shape[2] >= 3:
        return np.ascontiguousarray(rgb[:, :, :3][:, :, ::-1])
    return np.ascontiguousarray(rgb)


class Detector:
    def __init__(self, model_path: str | Path) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics is not installed. Run install.bat first."
            ) from exc
        path = Path(model_path)
        if not path.exists():
            raise RuntimeError(f"Model file is missing: {path}")
        self.path = path
        self.model = YOLO(str(path))

    def predict(
        self, image: Image.Image | np.ndarray, confidence: float = 0.70
    ) -> list[dict[str, Any]]:
        source = to_ultralytics_source(image)
        results = self.model.predict(source=source, conf=confidence, verbose=False)
        detections: list[dict[str, Any]] = []
        if not results:
            return detections
        result = results[0]
        names = result.names
        if result.boxes is None:
            return detections
        for box in result.boxes:
            xyxy = box.xyxy[0].cpu().tolist()
            class_id = int(box.cls[0].cpu().item())
            score = float(box.conf[0].cpu().item())
            x1, y1, x2, y2 = xyxy
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": names[class_id],
                    "confidence": score,
                    "bbox": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
                }
            )
        return detections

    @staticmethod
    def best(
        detections: list[dict[str, Any]],
        class_name: str,
        minimum_confidence: float = 0.0,
    ) -> dict[str, Any] | None:
        target_key = class_name_key(class_name)
        matches = [
            detection
            for detection in detections
            if class_name_key(str(detection.get("class_name", ""))) == target_key
            and float(detection.get("confidence", 0.0)) >= minimum_confidence
        ]
        return max(matches, key=lambda d: d["confidence"], default=None)


def draw_detections(image: np.ndarray, detections: list[dict[str, Any]]) -> np.ndarray:
    import cv2

    output = image.copy()
    for det in detections:
        x, y, w, h = det["bbox"]
        color = (40, 215, 161)
        cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)
        label = f"{det['class_name']} {det['confidence']:.0%}"
        cv2.rectangle(
            output, (x, max(0, y - 24)), (x + max(100, len(label) * 8), y), color, -1
        )
        cv2.putText(
            output,
            label,
            (x + 4, max(16, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (8, 17, 31),
            1,
        )
    return output
