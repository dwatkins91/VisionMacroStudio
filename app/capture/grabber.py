from __future__ import annotations

from dataclasses import dataclass

import mss
from PIL import Image

from app.automation.coordinates import absolute_region_from_normalized


@dataclass(frozen=True)
class ScreenGrab:
    image: Image.Image
    left: int
    top: int
    monitor_index: int
    source_left: int
    source_top: int
    source_width: int
    source_height: int

    @property
    def source_bounds(self) -> dict[str, int]:
        return {
            "left": self.source_left,
            "top": self.source_top,
            "width": self.source_width,
            "height": self.source_height,
        }


def list_monitors() -> list[dict[str, int]]:
    with mss.mss() as capture:
        return [dict(item) for item in capture.monitors]


def monitor_bounds(monitor_index: int = 0) -> dict[str, int]:
    with mss.mss() as capture:
        if monitor_index < 0 or monitor_index >= len(capture.monitors):
            monitor_index = 0
        monitor = capture.monitors[monitor_index]
        return {
            "left": int(monitor["left"]),
            "top": int(monitor["top"]),
            "width": int(monitor["width"]),
            "height": int(monitor["height"]),
        }


def grab_screen(
    monitor_index: int = 0,
    detection_region: dict[str, float] | None = None,
) -> ScreenGrab:
    """Capture a Watch source, optionally cropped to a normalized region."""
    with mss.mss() as capture:
        if monitor_index < 0 or monitor_index >= len(capture.monitors):
            monitor_index = 0
        selected = capture.monitors[monitor_index]
        source = {
            "left": int(selected["left"]),
            "top": int(selected["top"]),
            "width": int(selected["width"]),
            "height": int(selected["height"]),
        }
        capture_bounds = (
            absolute_region_from_normalized(detection_region, source)
            if detection_region
            else source
        )
        raw = capture.grab(capture_bounds)
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return ScreenGrab(
            image,
            int(capture_bounds["left"]),
            int(capture_bounds["top"]),
            monitor_index,
            source["left"],
            source["top"],
            source["width"],
            source["height"],
        )
