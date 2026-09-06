from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class HotkeyService(QObject):
    capture_requested = Signal()
    record_requested = Signal()
    stop_recording_requested = Signal()
    run_macro_requested = Signal()
    emergency_stop_requested = Signal()
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.listener = None

    def start(self, config: dict) -> None:
        self.stop()
        try:
            from pynput import keyboard

            keys = [
                config["capture_hotkey"],
                config["start_recording_hotkey"],
                config["stop_recording_hotkey"],
                config["run_macro_hotkey"],
                config["emergency_stop_hotkey"],
            ]
            if len(set(keys)) != len(keys):
                raise ValueError(
                    "Two actions use the same hotkey. Choose a unique hotkey for each action in Settings."
                )
            bindings = {
                config["capture_hotkey"]: lambda: self.capture_requested.emit(),
                config["start_recording_hotkey"]: lambda: self.record_requested.emit(),
                config["stop_recording_hotkey"]: lambda: (
                    self.stop_recording_requested.emit()
                ),
                config["run_macro_hotkey"]: lambda: self.run_macro_requested.emit(),
                config["emergency_stop_hotkey"]: lambda: (
                    self.emergency_stop_requested.emit()
                ),
            }
            self.listener = keyboard.GlobalHotKeys(bindings)
            self.listener.start()
        except Exception as exc:
            self.listener = None
            self.error.emit(f"Global hotkeys could not start: {exc}")

    def restart(self, config: dict) -> None:
        self.start(config)

    def stop(self) -> None:
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None
