from __future__ import annotations

from dataclasses import dataclass

import mss
from PIL import Image


@dataclass(frozen=True)
class ScreenGrab:
    image: Image.Image
    left: int
    top: int
    monitor_index: int


def list_monitors() -> list[dict[str, int]]:
    with mss.mss() as capture:
        return [dict(item) for item in capture.monitors]


def grab_screen(monitor_index: int = 0) -> ScreenGrab:
    """Capture the virtual desktop (0) or one physical monitor (1+)."""
    with mss.mss() as capture:
        if monitor_index < 0 or monitor_index >= len(capture.monitors):
            monitor_index = 0
        monitor = capture.monitors[monitor_index]
        raw = capture.grab(monitor)
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return ScreenGrab(
            image, int(monitor["left"]), int(monitor["top"]), monitor_index
        )
