from __future__ import annotations

import ctypes
import math
import os
from ctypes import wintypes
from typing import Any, Callable


COORDINATE_MODES = ("absolute", "watch_relative", "window_relative")
COORDINATE_MODE_LABELS = {
    "absolute": "Absolute screen position",
    "watch_relative": "Watch source (scales with resolution)",
    "window_relative": "Application window (moves and scales)",
}


class CoordinateReferenceError(RuntimeError):
    pass


def coordinate_mode(value: Any) -> str:
    mode = str(value or "absolute")
    return mode if mode in COORDINATE_MODES else "absolute"


def coordinate_mode_label(value: Any) -> str:
    return COORDINATE_MODE_LABELS[coordinate_mode(value)]


def checked_bounds(bounds: dict[str, Any]) -> dict[str, int]:
    try:
        result = {
            "left": int(bounds.get("left", 0)),
            "top": int(bounds.get("top", 0)),
            "width": int(bounds["width"]),
            "height": int(bounds["height"]),
        }
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise CoordinateReferenceError("The saved screen bounds are invalid.") from exc
    if result["width"] <= 0 or result["height"] <= 0:
        raise CoordinateReferenceError("Screen bounds must have a positive size.")
    return result


def relative_point(
    x: int | float, y: int | float, bounds: dict[str, Any]
) -> tuple[float, float]:
    area = checked_bounds(bounds)
    relative_x = (float(x) - area["left"]) / area["width"]
    relative_y = (float(y) - area["top"]) / area["height"]
    return (
        min(1.0, max(0.0, relative_x)),
        min(1.0, max(0.0, relative_y)),
    )


def point_from_relative(
    relative_x: int | float,
    relative_y: int | float,
    bounds: dict[str, Any],
) -> tuple[int, int]:
    area = checked_bounds(bounds)
    x = min(1.0, max(0.0, float(relative_x)))
    y = min(1.0, max(0.0, float(relative_y)))
    return (
        min(
            area["left"] + area["width"] - 1,
            round(area["left"] + area["width"] * x),
        ),
        min(
            area["top"] + area["height"] - 1,
            round(area["top"] + area["height"] * y),
        ),
    )


def normalized_region_from_absolute(
    region: dict[str, Any], bounds: dict[str, Any]
) -> dict[str, float]:
    area = checked_bounds(bounds)
    try:
        left = float(region["left"])
        top = float(region["top"])
        width = float(region["width"])
        height = float(region["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CoordinateReferenceError("The selected detection region is invalid.") from exc
    if width <= 0 or height <= 0:
        raise CoordinateReferenceError("The detection region must have a positive size.")
    right = min(area["left"] + area["width"], max(area["left"], left + width))
    bottom = min(area["top"] + area["height"], max(area["top"], top + height))
    left = min(area["left"] + area["width"], max(area["left"], left))
    top = min(area["top"] + area["height"], max(area["top"], top))
    if right <= left or bottom <= top:
        raise CoordinateReferenceError(
            "The selected detection region is outside the Watch source."
        )
    return {
        "x": (left - area["left"]) / area["width"],
        "y": (top - area["top"]) / area["height"],
        "width": (right - left) / area["width"],
        "height": (bottom - top) / area["height"],
    }


def checked_normalized_region(region: dict[str, Any]) -> dict[str, float]:
    try:
        result = {
            "x": float(region["x"]),
            "y": float(region["y"]),
            "width": float(region["width"]),
            "height": float(region["height"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise CoordinateReferenceError("The saved detection region is invalid.") from exc
    if not all(math.isfinite(value) for value in result.values()):
        raise CoordinateReferenceError("The saved detection region is invalid.")
    if (
        result["x"] < 0
        or result["y"] < 0
        or result["width"] <= 0
        or result["height"] <= 0
        or result["x"] + result["width"] > 1.000001
        or result["y"] + result["height"] > 1.000001
    ):
        raise CoordinateReferenceError(
            "The detection region must fit inside the selected Watch source."
        )
    return result


def absolute_region_from_normalized(
    region: dict[str, Any], bounds: dict[str, Any]
) -> dict[str, int]:
    normalized = checked_normalized_region(region)
    area = checked_bounds(bounds)
    left = round(area["left"] + area["width"] * normalized["x"])
    top = round(area["top"] + area["height"] * normalized["y"])
    right = round(
        area["left"]
        + area["width"] * (normalized["x"] + normalized["width"])
    )
    bottom = round(
        area["top"]
        + area["height"] * (normalized["y"] + normalized["height"])
    )
    source_right = area["left"] + area["width"]
    source_bottom = area["top"] + area["height"]
    left = min(source_right - 1, max(area["left"], left))
    top = min(source_bottom - 1, max(area["top"], top))
    right = min(source_right, max(left + 1, right))
    bottom = min(source_bottom, max(top + 1, bottom))
    return {
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top,
    }


def detection_region_label(region: dict[str, Any] | None) -> str:
    if not region:
        return "Full Watch source"
    normalized = checked_normalized_region(region)
    return (
        f"{normalized['width']:.0%} × {normalized['height']:.0%} area at "
        f"{normalized['x']:.0%}, {normalized['y']:.0%}"
    )


def _window_records() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    user32 = ctypes.windll.user32
    records: list[dict[str, Any]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    def collect(handle, _parameter):
        if not user32.IsWindowVisible(handle) or user32.IsIconic(handle):
            return True
        length = user32.GetWindowTextLengthW(handle)
        if length <= 0:
            return True
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(handle, title_buffer, length + 1)
        title = title_buffer.value.strip()
        if not title:
            return True
        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(handle, class_buffer, len(class_buffer))
        rectangle = wintypes.RECT()
        if not user32.GetWindowRect(handle, ctypes.byref(rectangle)):
            return True
        width = int(rectangle.right - rectangle.left)
        height = int(rectangle.bottom - rectangle.top)
        if width <= 0 or height <= 0:
            return True
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        records.append(
            {
                "handle": int(handle),
                "title": title,
                "class_name": class_buffer.value.strip(),
                "process_id": int(process_id.value),
                "left": int(rectangle.left),
                "top": int(rectangle.top),
                "width": width,
                "height": height,
            }
        )
        return True

    callback = callback_type(collect)
    if not user32.EnumWindows(callback, 0):
        return []
    return records


def window_at_point(
    x: int, y: int, excluded_process_id: int | None = None
) -> dict[str, Any] | None:
    excluded = os.getpid() if excluded_process_id is None else excluded_process_id
    for window in _window_records():
        if int(window["process_id"]) == excluded:
            continue
        if (
            int(window["left"]) <= x < int(window["left"]) + int(window["width"])
            and int(window["top"]) <= y < int(window["top"]) + int(window["height"])
        ):
            return window
    return None


def find_window_by_title(
    title: str, class_name: str = ""
) -> dict[str, Any] | None:
    target = str(title).strip().casefold()
    target_class = str(class_name).strip().casefold()
    if not target and not target_class:
        return None
    current_process_id = os.getpid()
    windows = [
        window
        for window in _window_records()
        if int(window.get("process_id", 0)) != current_process_id
    ]
    if target:
        exact = next(
            (
                window
                for window in windows
                if str(window["title"]).casefold() == target
            ),
            None,
        )
        if exact is not None:
            return exact
    if target:
        title_match = next(
            (
                window
                for window in windows
                if target in str(window["title"]).casefold()
                or str(window["title"]).casefold() in target
            ),
            None,
        )
        if title_match is not None:
            return title_match
    if target_class:
        return next(
            (
                window
                for window in windows
                if str(window.get("class_name", "")).casefold() == target_class
            ),
            None,
        )
    return None


def resolve_step_coordinate(
    step: dict[str, Any],
    watch_bounds: dict[str, Any],
    window_finder: Callable[[str], dict[str, Any] | None] | None = None,
) -> tuple[int, int, str]:
    mode = coordinate_mode(step.get("coordinate_mode", "absolute"))
    if mode == "absolute":
        try:
            return int(step["x"]), int(step["y"]), "absolute screen position"
        except (KeyError, TypeError, ValueError) as exc:
            raise CoordinateReferenceError(
                "This step does not have a valid absolute screen coordinate."
            ) from exc

    try:
        relative_x = float(step["relative_x"])
        relative_y = float(step["relative_y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CoordinateReferenceError(
            "This portable coordinate is missing its relative position."
        ) from exc
    if (
        not math.isfinite(relative_x)
        or not math.isfinite(relative_y)
        or not 0 <= relative_x <= 1
        or not 0 <= relative_y <= 1
    ):
        raise CoordinateReferenceError(
            "Portable coordinate percentages must be between 0% and 100%."
        )

    if mode == "watch_relative":
        x, y = point_from_relative(relative_x, relative_y, watch_bounds)
        return x, y, "Watch-relative scaled position"

    title = str(step.get("window_title", "")).strip()
    if not title:
        raise CoordinateReferenceError(
            "This window-relative step does not have a saved application-window title."
        )
    window = (
        window_finder(title)
        if window_finder is not None
        else find_window_by_title(title, str(step.get("window_class", "")))
    )
    if window is None:
        raise CoordinateReferenceError(
            f"The saved application window could not be found: {title}."
        )
    x, y = point_from_relative(relative_x, relative_y, window)
    return x, y, f"window-relative position in {window.get('title', title)}"
