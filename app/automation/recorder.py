from __future__ import annotations

import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Signal


class MacroRecorder(QObject):
    recorded = Signal(object)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.mouse_listener = None
        self.keyboard_listener = None
        self.steps: list[dict[str, Any]] = []
        self.started_at = 0.0
        self.last_event = 0.0
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self.mouse_listener is not None or self.keyboard_listener is not None

    def _delay(self, now: float) -> None:
        gap = now - self.last_event
        if gap >= 0.25:
            self.steps.append(
                {
                    "enabled": True,
                    "action": "WAIT",
                    "duration": round(gap, 2),
                    "duration_max": round(gap, 2),
                }
            )

    def start(self) -> None:
        if self.active:
            return
        try:
            from pynput import keyboard, mouse

            self.steps = []
            self.started_at = self.last_event = time.monotonic()

            def on_click(x, y, button, pressed):
                if not pressed or time.monotonic() - self.started_at < 0.4:
                    return
                now = time.monotonic()
                with self._lock:
                    self._delay(now)
                    action = "RIGHT_CLICK" if str(button).endswith("right") else "CLICK"
                    self.steps.append(
                        {
                            "enabled": True,
                            "action": action,
                            "x": x,
                            "y": y,
                            "random_offset": 0,
                            "move_duration": 0.35,
                        }
                    )
                    self.last_event = now

            def on_press(key):
                if time.monotonic() - self.started_at < 0.4:
                    return
                now = time.monotonic()
                try:
                    value = key.char
                except AttributeError:
                    value = str(key).replace("Key.", "")
                with self._lock:
                    self._delay(now)
                    self.steps.append(
                        {"enabled": True, "action": "PRESS_KEY", "value": value}
                    )
                    self.last_event = now

            self.mouse_listener = mouse.Listener(on_click=on_click)
            self.keyboard_listener = keyboard.Listener(on_press=on_press)
            self.mouse_listener.start()
            self.keyboard_listener.start()
        except Exception as exc:
            self.error.emit(str(exc))
            self.stop()

    def stop(self) -> list[dict[str, Any]]:
        for listener in (self.mouse_listener, self.keyboard_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self.mouse_listener = None
        self.keyboard_listener = None
        result = list(self.steps)
        self.recorded.emit(result)
        return result
