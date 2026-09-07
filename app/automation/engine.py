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
from app.automation.coordinates import (
    detection_region_label,
    resolve_step_coordinate,
)
from app.capture.grabber import grab_screen, monitor_bounds
from app.vision.detector import Detector, class_name_key


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
    decision_state = Signal(str)
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
        one_loop: bool = False,
        detection_region: dict[str, float] | None = None,
    ) -> None:
        super().__init__()
        self.macro = macro
        self.model_path = model_path
        self.single_step = single_step
        self.time_limit_seconds = max(0.0, float(time_limit_seconds))
        self.monitor_index = max(0, int(monitor_index))
        self.one_loop = bool(one_loop)
        self.detection_region = dict(detection_region) if detection_region else None
        self.stop_event = threading.Event()
        self._deadline: float | None = None
        self._ended_by_time_limit = False
        self._held_keys: set[Any] = set()
        self._mouse = None
        self._keyboard = None
        self._recent_detection_clicks: list[dict[str, Any]] = []

    def _decision(self, message: str) -> None:
        self.log.emit(message)
        self.decision_state.emit(message)

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

    def _filter_recent_detection_clicks(
        self,
        detections: list[dict[str, Any]],
        origin: tuple[int, int],
        respect_click_cooldown: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        now = time.monotonic()
        self._recent_detection_clicks = [
            record
            for record in self._recent_detection_clicks
            if float(record["expires_at"]) > now
        ]
        if not respect_click_cooldown:
            return detections, 0
        allowed: list[dict[str, Any]] = []
        ignored = 0
        for detection in detections:
            x, y, width, height = detection["bbox"]
            center_x = origin[0] + x + width / 2
            center_y = origin[1] + y + height / 2
            radius = max(32.0, math.hypot(width, height) * 0.55)
            key = class_name_key(str(detection.get("class_name", "")))
            is_recent = any(
                record["class_key"] == key
                and math.hypot(
                    center_x - float(record["center_x"]),
                    center_y - float(record["center_y"]),
                )
                <= max(radius, float(record["radius"]))
                for record in self._recent_detection_clicks
            )
            if is_recent:
                ignored += 1
            else:
                allowed.append(detection)
        return allowed, ignored

    def _remember_detection_click(
        self,
        found: dict[str, Any],
        origin: tuple[int, int],
        object_name: str,
        cooldown_seconds: float,
    ) -> None:
        cooldown = max(0.0, float(cooldown_seconds))
        if cooldown == 0:
            return
        x, y, width, height = found["bbox"]
        self._recent_detection_clicks.append(
            {
                "class_key": class_name_key(object_name),
                "center_x": origin[0] + x + width / 2,
                "center_y": origin[1] + y + height / 2,
                "radius": max(32.0, math.hypot(width, height) * 0.55),
                "expires_at": time.monotonic() + cooldown,
            }
        )
        self._decision(
            f"STABILITY — {object_name} at this position will be ignored for "
            f"{cooldown:g} second(s)."
        )

    def _wait_limit_reached(self, step: dict, message: str) -> bool:
        behavior = step.get("on_timeout", "stop")
        if behavior == "continue":
            self._decision(message + " Timeout behavior is Continue.")
            return True
        raise TimeoutError(message)

    def _detect(
        self,
        detector: Detector,
        object_name: str,
        confidence: float,
        respect_click_cooldown: bool = True,
    ) -> tuple[dict | None, tuple[int, int], int]:
        grab = grab_screen(self.monitor_index, self.detection_region)
        detections = detector.predict(grab.image, min(confidence, 0.05))
        if self._check_time_limit():
            return None, (grab.left, grab.top), 0
        origin = (grab.left, grab.top)
        detections, ignored = self._filter_recent_detection_clicks(
            detections, origin, respect_click_cooldown
        )
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
        return found, origin, ignored

    def _detect_any(
        self,
        detector: Detector,
        names: list[str],
        confidence: float,
        respect_click_cooldown: bool = True,
    ) -> tuple[str | None, dict | None, tuple[int, int], int]:
        grab = grab_screen(self.monitor_index, self.detection_region)
        detections = detector.predict(grab.image, min(confidence, 0.05))
        if self._check_time_limit():
            return None, None, (grab.left, grab.top), 0
        origin = (grab.left, grab.top)
        detections, ignored = self._filter_recent_detection_clicks(
            detections, origin, respect_click_cooldown
        )
        for name in names:
            found = detector.best(detections, name, confidence)
            if found is not None:
                self.detection_state.emit(name, True, found["confidence"])
                return name, found, origin, ignored
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
        return None, None, origin, ignored

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
        required = max(1, int(step.get("required_consecutive_detections", 1)))
        max_attempts = max(0, int(step.get("max_detection_attempts", 0)))
        started = time.monotonic()
        attempts = 0
        streak = 0
        cooldown_reported = False
        while not self._check_time_limit():
            found, origin, ignored = self._detect(
                detector,
                object_name,
                confidence,
                respect_click_cooldown=desired,
            )
            attempts += 1
            if self.stop_event.is_set():
                return None, origin
            if (found is not None) == desired:
                streak += 1
                if required > 1 and streak < required:
                    state = "visible" if desired else "absent"
                    self.decision_state.emit(
                        f"STABILITY — {object_name} is {state}: confirmation "
                        f"{streak} of {required}."
                    )
                if streak >= required:
                    if found is not None:
                        detail = self._detection_description(object_name, found)
                    else:
                        detail = f"{object_name} is no longer visible."
                    if required > 1:
                        detail += f" Confirmed across {required} consecutive checks."
                    self._decision(detail + " Step condition passed.")
                    return found, origin
            else:
                streak = 0
            if ignored and not cooldown_reported:
                cooldown_reported = True
                self._decision(
                    f"STABILITY — Ignored {ignored} recent {object_name} detection(s) "
                    "because the clicked-object cooldown is active."
                )
            if max_attempts and attempts >= max_attempts:
                message = (
                    f"Reached the maximum of {max_attempts} detection checks while "
                    f"waiting for {object_name}."
                )
                if self._wait_limit_reached(step, message):
                    return None, origin
            if timeout > 0 and time.monotonic() - started >= timeout:
                message = f"Timed out waiting for {object_name}."
                if self._wait_limit_reached(step, message):
                    return None, origin
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
        required = max(1, int(step.get("required_consecutive_detections", 1)))
        max_attempts = max(0, int(step.get("max_detection_attempts", 0)))
        started = time.monotonic()
        origin = (0, 0)
        attempts = 0
        streak = 0
        streak_name: str | None = None
        cooldown_reported = False
        while not self._check_time_limit():
            matched, found, origin, ignored = self._detect_any(
                detector, names, confidence, respect_click_cooldown=True
            )
            attempts += 1
            if self.stop_event.is_set():
                return None, None, origin
            if found is not None and matched is not None:
                if matched == streak_name:
                    streak += 1
                else:
                    streak_name = matched
                    streak = 1
                if required > 1 and streak < required:
                    self.decision_state.emit(
                        f"STABILITY — {matched} confirmation {streak} of {required}."
                    )
                if streak >= required:
                    if required > 1:
                        self._decision(
                            f"STABILITY — {matched} confirmed across "
                            f"{required} consecutive checks."
                        )
                    return matched, found, origin
            else:
                streak = 0
                streak_name = None
            if ignored and not cooldown_reported:
                cooldown_reported = True
                self._decision(
                    f"STABILITY — Ignored {ignored} recently clicked detection(s) "
                    "because the clicked-object cooldown is active."
                )
            if max_attempts and attempts >= max_attempts:
                message = (
                    f"Reached the maximum of {max_attempts} detection checks while "
                    f"waiting for any of: {', '.join(names)}."
                )
                if self._wait_limit_reached(step, message):
                    return None, None, origin
            if timeout > 0 and time.monotonic() - started >= timeout:
                message = f"Timed out waiting for any of: {', '.join(names)}."
                if self._wait_limit_reached(step, message):
                    return None, None, origin
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
        self._decision(
            f"ACTION — {verb} {object_name} at ({round(target_x)}, {round(target_y)})."
        )
        self._remember_detection_click(
            found,
            origin,
            object_name,
            float(step.get("click_cooldown_seconds", 0)),
        )

    def _wait_after_detection_click(
        self, detector: Detector, step: dict[str, Any], object_name: str
    ) -> None:
        if not step.get("wait_after_click_until_disappears", False):
            return
        timeout = max(0.0, float(step.get("post_click_disappear_timeout", 10)))
        wait_step = dict(step)
        wait_step.update(
            {
                "object": object_name,
                "timeout": timeout,
                "timeout_max": timeout,
                "max_detection_attempts": 0,
                "click_cooldown_seconds": 0,
            }
        )
        timeout_text = "forever" if timeout == 0 else f"up to {timeout:g} second(s)"
        self._decision(
            f"STABILITY — Waiting {timeout_text} for {object_name} to disappear "
            "before the macro continues."
        )
        self._wait_for(detector, wait_step, False)

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
            self._wait_after_detection_click(
                detector, step, str(step.get("object", ""))
            )
        elif action == "CLICK_FIRST_AVAILABLE":
            names = object_names(step.get("objects", []))
            matched, found, origin = self._wait_for_any(detector, step)
            if matched is None or found is None:
                return
            selected_index = names.index(matched)
            if selected_index == 0:
                self._decision(
                    f"DECISION — Selected primary object {matched} at "
                    f"{found['confidence']:.0%} confidence."
                )
            else:
                unavailable = ", ".join(names[:selected_index])
                self._decision(
                    f"DECISION — {unavailable} unavailable; selected fallback {matched} "
                    f"at {found['confidence']:.0%} confidence."
                )
            self._click_detection(found, origin, step, matched)
            self._wait_after_detection_click(detector, step, matched)
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
            target_x, target_y, basis = resolve_step_coordinate(
                step, monitor_bounds(self.monitor_index)
            )
            self._decision(
                f"COORDINATE — Resolved {basis} to ({target_x}, {target_y})."
            )
            self._smooth_move(
                target_x,
                target_y,
                float(step.get("move_duration", 0.35)),
            )
        elif action in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            resolved_x, resolved_y, basis = resolve_step_coordinate(
                step, monitor_bounds(self.monitor_index)
            )
            target_x, target_y = randomized_point(
                resolved_x,
                resolved_y,
                int(step.get("random_offset", 0)),
            )
            self._decision(
                f"COORDINATE — Resolved {basis} to ({resolved_x}, {resolved_y})."
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
            self._decision(
                f"ACTION — {click_name} screen location ({target_x}, {target_y})."
            )
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
            active_steps = (
                [source_steps[self.single_step]]
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
            if self.single_step is not None:
                mode = f"selected step {self.single_step + 1}"
            elif self.one_loop:
                mode = "one loop"
            else:
                mode = "full macro"
            self.log.emit(
                f"Macro started: {self.macro.get('name', 'Untitled')} ({mode})"
            )
            source = (
                "the entire desktop"
                if self.monitor_index == 0
                else f"monitor {self.monitor_index}"
            )
            self.log.emit(f"Detection source: {source}.")
            if self.detection_region:
                self.log.emit(
                    "Detection region: "
                    + detection_region_label(self.detection_region)
                    + "."
                )
            else:
                self.log.emit("Detection region: full Watch source.")
            if self.time_limit_seconds > 0:
                self.log.emit(
                    f"Automatic stop is set for {self.time_limit_seconds / 60:g} minute(s)."
                )
            detector = Detector(self.model_path) if needs_detection else None
            repeat_counts: dict[int, int] = {}
            index = self.single_step if self.single_step is not None else 0
            one_loop_finished = False
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
                            self._decision(
                                detail + " DECISION — Continuing to the next step."
                            )
                        elif self.single_step is not None:
                            self._decision(
                                detail
                                + f" DECISION — Would branch to step {route}; "
                                "selected-step live testing will not jump."
                            )
                        elif self.one_loop and route == 1:
                            self._decision(
                                detail
                                + " DECISION — Would branch to step 1; one-loop run is complete."
                            )
                            one_loop_finished = True
                            break
                        else:
                            self._decision(
                                detail + f" DECISION — Branching to step {route}."
                            )
                            index = self._jump_index(route, len(steps), index)
                            continue
                elif action == "GOTO_STEP":
                    target = int(step.get("target_step", 1))
                    if self.single_step is not None:
                        self._decision(
                            f"DECISION — Go To Step would jump to step {target}; "
                            "selected-step live testing will not jump."
                        )
                    elif self.one_loop and target == 1:
                        self._decision(
                            "DECISION — Go To Step would return to step 1; "
                            "one-loop run is complete."
                        )
                        one_loop_finished = True
                        break
                    else:
                        self._decision(f"DECISION — Going to step {target}.")
                        self._interruptible_sleep(0.01)
                        index = self._jump_index(target, len(steps), index)
                        continue
                elif action == "REPEAT":
                    count = max(1, int(step.get("count", 1)))
                    done = repeat_counts.get(index, 0)
                    if self.single_step is not None:
                        self._decision(
                            "DECISION — Repeat branching is skipped during selected-step live testing."
                        )
                    elif self.one_loop and int(step.get("target_step", 1)) == 1:
                        self._decision(
                            "DECISION — Repeat would return to step 1; "
                            "one-loop run is complete."
                        )
                        one_loop_finished = True
                        break
                    elif done < count:
                        repeat_counts[index] = done + 1
                        target = int(step.get("target_step", 1))
                        self._decision(
                            f"DECISION — Repeat {done + 1} of {count}: returning to step {target}."
                        )
                        index = self._jump_index(target, len(steps), index)
                        continue
                    else:
                        repeat_counts.pop(index, None)
                        self._decision(
                            "DECISION — Repeat count completed; continuing."
                        )
                else:
                    self._execute_step(detector, step)
                index += 1
                if self.single_step is not None:
                    break
            if self.stop_event.is_set():
                if self._ended_by_time_limit:
                    self.log.emit("Macro stopped automatically at its time limit.")
                else:
                    self.log.emit("Macro stopped.")
                self.stopped.emit()
            else:
                if one_loop_finished:
                    self.log.emit("One-loop run completed before returning to step 1.")
                elif self.single_step is not None:
                    self.log.emit(
                        f"Selected-step live run completed for step {self.single_step + 1}."
                    )
                else:
                    self.log.emit("Macro completed.")
                self.completed.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self._release_inputs()
