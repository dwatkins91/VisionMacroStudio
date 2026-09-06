from __future__ import annotations

import math
import random
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.automation.control import (
    destination_steps,
    object_names,
    randomized_point,
    randomized_seconds,
)
from app.capture.grabber import grab_screen
from app.vision.detector import Detector


DETECTION_ACTIONS = {
    "WAIT_FOR_OBJECT",
    "WAIT_FOR_ANY_OBJECT",
    "WAIT_UNTIL_DISAPPEARS",
    "CLICK_OBJECT",
    "RIGHT_CLICK_OBJECT",
    "CLICK_FIRST_AVAILABLE",
}


def _keyboard_key(name: str):
    from pynput import keyboard

    normalized = name.lower().strip().replace(" ", "_")
    aliases = {"ctrl": "ctrl", "control": "ctrl", "escape": "esc", "return": "enter"}
    normalized = aliases.get(normalized, normalized)
    return getattr(keyboard.Key, normalized, name)


class MacroWorker(QObject):
    log = Signal(str)
    current_step = Signal(int, object)
    detection_state = Signal(str, bool, float)
    observation_state = Signal(str, float, str, float, bool)
    completed = Signal()
    failed = Signal(str)
    stopped = Signal()
    time_limit_reached = Signal(float)

    def __init__(
        self,
        macro: dict[str, Any],
        model_path: str | None,
        single_step: int | None = None,
        time_limit_seconds: float = 0.0,
        monitor_index: int = 0,
    ) -> None:
        super().__init__()
        self.macro = macro
        self.model_path = model_path
        self.single_step = single_step
        self.time_limit_seconds = max(0.0, float(time_limit_seconds))
        self.monitor_index = max(0, int(monitor_index))
        self.stop_event = threading.Event()
        self._deadline: float | None = None
        self._ended_by_time_limit = False
        self._held_keys: set[Any] = set()
        self._mouse = None
        self._keyboard = None

    def request_stop(self) -> None:
        self.stop_event.set()
        self._release_inputs()

    def _check_time_limit(self) -> bool:
        if self.stop_event.is_set():
            return True
        if self._deadline is not None and time.monotonic() >= self._deadline:
            self._ended_by_time_limit = True
            self.stop_event.set()
            self.log.emit(
                f"Macro time limit reached after {self.time_limit_seconds / 60:g} minute(s)."
            )
            self.time_limit_reached.emit(self.time_limit_seconds)
            self._release_inputs()
            return True
        return False

    def _release_inputs(self) -> None:
        try:
            for key in list(self._held_keys):
                self._keyboard.release(key)
            self._held_keys.clear()
            if self._mouse is not None:
                from pynput.mouse import Button

                for button in (Button.left, Button.middle, Button.right):
                    try:
                        self._mouse.release(button)
                    except Exception:
                        pass
        except Exception:
            pass

    def _interruptible_sleep(self, seconds: float) -> bool:
        wait_seconds = max(0.0, seconds)
        if self._check_time_limit():
            return True
        if self._deadline is not None:
            wait_seconds = min(
                wait_seconds, max(0.0, self._deadline - time.monotonic())
            )
        self.stop_event.wait(wait_seconds)
        self._check_time_limit()
        return self.stop_event.is_set()

    def _detect(
        self, detector: Detector, object_name: str, confidence: float
    ) -> tuple[dict | None, tuple[int, int]]:
        grab = grab_screen(self.monitor_index)
        detections = detector.predict(grab.image, min(confidence, 0.05))
        if self._check_time_limit():
            return None, (grab.left, grab.top)
        candidate = detector.best(detections, object_name)
        found = detector.best(detections, object_name, confidence)
        score = found["confidence"] if found else 0.0
        if found is not None:
            self.detection_state.emit(object_name, True, score)
        elif candidate is not None:
            self.observation_state.emit(
                str(candidate["class_name"]),
                float(candidate["confidence"]),
                object_name,
                confidence,
                True,
            )
        elif detections:
            observed = max(detections, key=lambda item: item["confidence"])
            self.observation_state.emit(
                str(observed["class_name"]),
                float(observed["confidence"]),
                object_name,
                confidence,
                False,
            )
        else:
            self.detection_state.emit(object_name, False, 0.0)
        return found, (grab.left, grab.top)

    def _detect_any(
        self, detector: Detector, names: list[str], confidence: float
    ) -> tuple[str | None, dict | None, tuple[int, int]]:
        grab = grab_screen(self.monitor_index)
        detections = detector.predict(grab.image, min(confidence, 0.05))
        if self._check_time_limit():
            return None, None, (grab.left, grab.top)
        for name in names:
            found = detector.best(detections, name, confidence)
            if found is not None:
                self.detection_state.emit(name, True, found["confidence"])
                return name, found, (grab.left, grab.top)
        target_candidates = [
            (name, candidate)
            for name in names
            if (candidate := detector.best(detections, name)) is not None
        ]
        targets = " / ".join(names)
        if target_candidates:
            _name, observed = max(
                target_candidates, key=lambda item: item[1]["confidence"]
            )
            self.observation_state.emit(
                str(observed["class_name"]),
                float(observed["confidence"]),
                targets,
                confidence,
                True,
            )
        elif detections:
            observed = max(detections, key=lambda item: item["confidence"])
            self.observation_state.emit(
                str(observed["class_name"]),
                float(observed["confidence"]),
                targets,
                confidence,
                False,
            )
        else:
            self.detection_state.emit(targets, False, 0.0)
        return None, None, (grab.left, grab.top)

    @staticmethod
    def _detection_description(object_name: str, found: dict) -> str:
        x, y, width, height = found["bbox"]
        return (
            f"Detected {object_name} at {found['confidence']:.0%} confidence "
            f"in box ({round(x)}, {round(y)}, {round(width)}, {round(height)})."
        )

    def _wait_for(
        self, detector: Detector, step: dict, desired: bool
    ) -> tuple[dict | None, tuple[int, int]]:
        object_name = step.get("object", "")
        confidence = float(step.get("confidence", 0.70))
        timeout_min = float(step.get("timeout", 30.0))
        timeout_max = float(step.get("timeout_max", timeout_min))
        timeout = randomized_seconds(timeout_min, timeout_max)
        if timeout > 0 and timeout_max != timeout_min:
            self.log.emit(f"Random timeout selected: {timeout:.2f} seconds.")
        poll = max(0.05, float(step.get("poll_interval", 0.25)))
        started = time.monotonic()
        while not self._check_time_limit():
            found, origin = self._detect(detector, object_name, confidence)
            if self.stop_event.is_set():
                return None, origin
            if (found is not None) == desired:
                if found is not None:
                    self.log.emit(self._detection_description(object_name, found))
                else:
                    self.log.emit(f"{object_name} is no longer visible.")
                return found, origin
            if timeout > 0 and time.monotonic() - started >= timeout:
                behavior = step.get("on_timeout", "stop")
                message = f"Timed out waiting for {object_name}."
                if behavior == "continue":
                    self.log.emit(message + " Continuing.")
                    return None, origin
                raise TimeoutError(message)
            self._interruptible_sleep(poll)
        return None, (0, 0)

    def _wait_for_any(
        self, detector: Detector, step: dict
    ) -> tuple[str | None, dict | None, tuple[int, int]]:
        names = object_names(step.get("objects", []))
        if not names:
            raise RuntimeError("This step does not contain any object names.")
        confidence = float(step.get("confidence", 0.70))
        timeout_min = float(step.get("timeout", 30.0))
        timeout_max = float(step.get("timeout_max", timeout_min))
        timeout = randomized_seconds(timeout_min, timeout_max)
        if timeout > 0 and timeout_max != timeout_min:
            self.log.emit(f"Random timeout selected: {timeout:.2f} seconds.")
        poll = max(0.05, float(step.get("poll_interval", 0.25)))
        started = time.monotonic()
        origin = (0, 0)
        while not self._check_time_limit():
            matched, found, origin = self._detect_any(detector, names, confidence)
            if self.stop_event.is_set():
                return None, None, origin
            if found is not None:
                return matched, found, origin
            if timeout > 0 and time.monotonic() - started >= timeout:
                behavior = step.get("on_timeout", "stop")
                message = f"Timed out waiting for any of: {', '.join(names)}."
                if behavior == "continue":
                    self.log.emit(message + " Continuing.")
                    return None, None, origin
                raise TimeoutError(message)
            self._interruptible_sleep(poll)
        return None, None, origin

    def _smooth_move(
        self, target_x: int, target_y: int, duration: float = 0.35
    ) -> None:
        start_x, start_y = self._mouse.position
        duration = max(0.05, duration * random.uniform(0.80, 1.25))
        distance = math.hypot(target_x - start_x, target_y - start_y)
        steps = max(8, min(75, int(distance / 12)))
        arc = random.uniform(-0.09, 0.09) * distance
        normal_x = -(target_y - start_y) / max(distance, 1)
        normal_y = (target_x - start_x) / max(distance, 1)
        for index in range(1, steps + 1):
            if self._check_time_limit():
                return
            t = index / steps
            eased = t * t * (3 - 2 * t)
            bend = math.sin(math.pi * t) * arc
            x = start_x + (target_x - start_x) * eased + normal_x * bend
            y = start_y + (target_y - start_y) * eased + normal_y * bend
            self._mouse.position = (round(x), round(y))
            if self._interruptible_sleep(duration / steps):
                return

    def _click_detection(
        self,
        found: dict,
        origin: tuple[int, int],
        step: dict[str, Any],
        object_name: str,
        right_click: bool = False,
    ) -> None:
        from pynput.mouse import Button

        x, y, width, height = found["bbox"]
        relative_x = float(step.get("target_x", 0.5))
        relative_y = float(step.get("target_y", 0.5))
        random_offset = int(step.get("random_offset", 0))
        target_x, target_y = randomized_point(
            round(origin[0] + x + width * relative_x),
            round(origin[1] + y + height * relative_y),
            random_offset,
        )
        self._smooth_move(target_x, target_y, float(step.get("move_duration", 0.35)))
        if self._check_time_limit():
            return
        button = Button.right if right_click else Button.left
        self._mouse.click(button, 2 if step.get("double_click") else 1)
        verb = "Right-clicked" if right_click else "Clicked"
        self.log.emit(
            f"{verb} {object_name} at ({round(target_x)}, {round(target_y)})."
        )

    def _execute_step(self, detector: Detector | None, step: dict[str, Any]) -> None:
        from pynput.mouse import Button

        action = step.get("action")
        if action == "WAIT_FOR_OBJECT":
            self._wait_for(detector, step, True)
        elif action == "WAIT_UNTIL_DISAPPEARS":
            self._wait_for(detector, step, False)
        elif action in ("CLICK_OBJECT", "RIGHT_CLICK_OBJECT"):
            found, origin = self._wait_for(detector, step, True)
            if found is None:
                return
            self._click_detection(
                found,
                origin,
                step,
                str(step.get("object", "")),
                right_click=action == "RIGHT_CLICK_OBJECT",
            )
        elif action == "CLICK_FIRST_AVAILABLE":
            names = object_names(step.get("objects", []))
            matched, found, origin = self._wait_for_any(detector, step)
            if matched is None or found is None:
                return
            selected_index = names.index(matched)
            if selected_index == 0:
                self.log.emit(
                    f"Selected primary object {matched} at {found['confidence']:.0%} confidence."
                )
            else:
                unavailable = ", ".join(names[:selected_index])
                self.log.emit(
                    f"{unavailable} unavailable; selected fallback {matched} "
                    f"at {found['confidence']:.0%} confidence."
                )
            self._click_detection(found, origin, step, matched)
        elif action == "PRESS_KEY":
            key = _keyboard_key(str(step.get("value", "space")))
            self._keyboard.press(key)
            self._held_keys.add(key)
            self._keyboard.release(key)
            self._held_keys.discard(key)
        elif action == "TYPE_TEXT":
            self._keyboard.type(str(step.get("value", "")))
        elif action == "WAIT":
            wait_min = float(step.get("duration", 1.0))
            wait_max = float(step.get("duration_max", wait_min))
            wait_seconds = randomized_seconds(wait_min, wait_max)
            self.log.emit(f"Waiting {wait_seconds:.2f} seconds.")
            self._interruptible_sleep(wait_seconds)
        elif action == "MOVE_MOUSE":
            self._smooth_move(
                int(step.get("x", 0)),
                int(step.get("y", 0)),
                float(step.get("move_duration", 0.35)),
            )
        elif action in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            target_x, target_y = self._mouse.position
            if "x" in step and "y" in step:
                target_x, target_y = randomized_point(
                    int(step["x"]),
                    int(step["y"]),
                    int(step.get("random_offset", 0)),
                )
                self._smooth_move(
                    target_x,
                    target_y,
                    float(step.get("move_duration", 0.35)),
                )
            if self._check_time_limit():
                return
            button = Button.right if action == "RIGHT_CLICK" else Button.left
            self._mouse.click(button, 2 if action == "DOUBLE_CLICK" else 1)
            click_name = {
                "CLICK": "Clicked",
                "DOUBLE_CLICK": "Double-clicked",
                "RIGHT_CLICK": "Right-clicked",
            }[action]
            self.log.emit(f"{click_name} screen location ({target_x}, {target_y}).")
        elif action == "STOP":
            self.stop_event.set()

    @staticmethod
    def _jump_index(target_step: int, step_count: int, source_step: int) -> int:
        if target_step < 1 or target_step > step_count:
            raise RuntimeError(
                f"Step {source_step + 1} points to step {target_step}, "
                f"but this macro has {step_count} steps."
            )
        return target_step - 1

    @Slot()
    def run(self) -> None:
        try:
            from pynput import keyboard, mouse

            self._mouse = mouse.Controller()
            self._keyboard = keyboard.Controller()
            if self.time_limit_seconds > 0:
                self._deadline = time.monotonic() + self.time_limit_seconds
            source_steps = self.macro.get("steps", [])
            steps = source_steps
            if self.single_step is not None:
                if self.single_step < 0 or self.single_step >= len(source_steps):
                    raise RuntimeError("Select a step to run.")
                steps = [source_steps[self.single_step]]
            active_steps = (
                steps
                if self.single_step is not None
                else [step for step in steps if step.get("enabled", True)]
            )
            needs_detection = any(
                step.get("action") in DETECTION_ACTIONS for step in active_steps
            )
            if needs_detection and not self.model_path:
                raise RuntimeError(
                    "This macro uses object detection, but no model is available."
                )
            self.log.emit(f"Macro started: {self.macro.get('name', 'Untitled')}")
            source = (
                "the entire desktop"
                if self.monitor_index == 0
                else f"monitor {self.monitor_index}"
            )
            self.log.emit(f"Detection source: {source}.")
            if self.time_limit_seconds > 0:
                self.log.emit(
                    f"Automatic stop is set for {self.time_limit_seconds / 60:g} minute(s)."
                )
            detector = Detector(self.model_path) if needs_detection else None
            repeat_counts: dict[int, int] = {}
            index = 0
            while index < len(steps) and not self._check_time_limit():
                step = steps[index]
                if self.single_step is None and not step.get("enabled", True):
                    index += 1
                    continue
                self.current_step.emit(index, step)
                action = step.get("action", "")
                self.log.emit(f"Step {index + 1}: {action.replace('_', ' ').title()}")
                if action == "WAIT_FOR_ANY_OBJECT":
                    names = object_names(step.get("objects", []))
                    targets = destination_steps(step.get("target_steps", []))
                    if len(names) != len(targets):
                        raise RuntimeError(
                            "Wait For Any Object needs one destination step per object."
                        )
                    matched, found, _origin = self._wait_for_any(detector, step)
                    if matched is not None and found is not None:
                        route = targets[names.index(matched)]
                        detail = self._detection_description(matched, found)
                        if route == 0:
                            self.log.emit(detail + " Continuing to the next step.")
                        elif self.single_step is not None:
                            self.log.emit(
                                detail
                                + f" Branch destination is step {route}; single-step testing will not jump."
                            )
                        else:
                            self.log.emit(detail + f" Branching to step {route}.")
                            index = self._jump_index(route, len(steps), index)
                            continue
                elif action == "GOTO_STEP":
                    target = int(step.get("target_step", 1))
                    if self.single_step is not None:
                        self.log.emit(
                            f"Go To Step would jump to step {target}; single-step testing will not jump."
                        )
                    else:
                        self.log.emit(f"Going to step {target}.")
                        self._interruptible_sleep(0.01)
                        index = self._jump_index(target, len(steps), index)
                        continue
                elif action == "REPEAT":
                    count = max(1, int(step.get("count", 1)))
                    done = repeat_counts.get(index, 0)
                    if self.single_step is not None:
                        self.log.emit(
                            "Repeat branching is skipped during single-step testing."
                        )
                    elif done < count:
                        repeat_counts[index] = done + 1
                        target = int(step.get("target_step", 1))
                        self.log.emit(
                            f"Repeat {done + 1} of {count}: returning to step {target}."
                        )
                        index = self._jump_index(target, len(steps), index)
                        continue
                    else:
                        repeat_counts.pop(index, None)
                        self.log.emit("Repeat count completed; continuing.")
                else:
                    self._execute_step(detector, step)
                index += 1
            if self.stop_event.is_set():
                if self._ended_by_time_limit:
                    self.log.emit("Macro stopped automatically at its time limit.")
                else:
                    self.log.emit("Macro stopped.")
                self.stopped.emit()
            else:
                self.log.emit("Macro completed.")
                self.completed.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self._release_inputs()
