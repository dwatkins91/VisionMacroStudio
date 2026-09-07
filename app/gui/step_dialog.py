from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.automation.control import SUPPORTED_ACTIONS, destination_steps, object_names
from app.automation.flow import COMPARISON_OPERATORS, valid_variable_name
from app.automation.coordinates import (
    COORDINATE_MODE_LABELS,
    checked_bounds,
    coordinate_mode,
    point_from_relative,
    relative_point,
)
from app.gui.coordinate_picker import CoordinatePickerOverlay

ACTIONS = list(SUPPORTED_ACTIONS)


class StepDialog(QDialog):
    def __init__(
        self,
        classes: list[str],
        step: dict | None = None,
        parent=None,
        watch_bounds: dict[str, int] | None = None,
        macro_choices: list[dict] | None = None,
        current_macro_id: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro Step")
        self.setMinimumWidth(430)
        self.step = step or {}
        self.window_class = str(self.step.get("window_class", ""))
        self.watch_bounds = checked_bounds(
            watch_bounds or {"left": 0, "top": 0, "width": 1920, "height": 1080}
        )
        saved_window_bounds = self.step.get("window_reference_bounds")
        try:
            self.window_reference_bounds = (
                checked_bounds(saved_window_bounds) if saved_window_bounds else None
            )
        except Exception:
            self.window_reference_bounds = None
        self._updating_coordinate = False
        self.coordinate_picker: CoordinatePickerOverlay | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.enabled = QCheckBox("Run this step")
        self.enabled.setChecked(self.step.get("enabled", True))
        self.action = QComboBox()
        self.action.addItems(ACTIONS)
        self.action.setCurrentText(self.step.get("action", ACTIONS[0]))
        self.step_name = QLineEdit(str(self.step.get("name", "")))
        self.step_name.setMaxLength(120)
        self.step_name.setPlaceholderText(
            "Example: Wait for completion message"
        )
        self.step_name.setToolTip(
            "An optional readable name for this step. A Section action requires a title."
        )
        self.comment = QLineEdit(str(self.step.get("comment", "")))
        self.comment.setMaxLength(500)
        self.comment.setPlaceholderText("Optional note about what this step does")
        self.object = QComboBox()
        self.object.setEditable(True)
        self.object.addItems(classes)
        self.object.setCurrentText(
            self.step.get("object", classes[0] if classes else "Object_A")
        )
        default_objects = object_names(self.step.get("objects", classes[:2]))
        if not default_objects:
            default_objects = ["Object_A", "Object_B"]
        self.objects = QLineEdit(", ".join(default_objects))
        self.objects.setPlaceholderText("Primary_Object, Fallback_Object")
        saved_destinations = destination_steps(self.step.get("target_steps", []))
        if not saved_destinations:
            saved_destinations = [0] * len(default_objects)
        self.target_steps = QLineEdit(
            ", ".join(str(value) for value in saved_destinations)
        )
        self.target_steps.setPlaceholderText("Example: 3, 1 (0 = next step)")
        self.value = QLineEdit(str(self.step.get("value", "space")))
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.1, 0.99)
        self.confidence.setSingleStep(0.05)
        self.confidence.setValue(float(self.step.get("confidence", 0.70)))
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(0, 3600)
        self.timeout.setSuffix(" sec")
        self.timeout.setValue(float(self.step.get("timeout", 30)))
        self.timeout_max = QDoubleSpinBox()
        self.timeout_max.setRange(0, 3600)
        self.timeout_max.setSuffix(" sec")
        self.timeout_max.setValue(
            float(self.step.get("timeout_max", self.step.get("timeout", 30)))
        )
        self.poll = QDoubleSpinBox()
        self.poll.setRange(0.05, 10)
        self.poll.setSingleStep(0.05)
        self.poll.setValue(float(self.step.get("poll_interval", 0.25)))
        self.on_timeout = QComboBox()
        self.on_timeout.addItems(["stop", "continue", "go_to_step"])
        self.on_timeout.setCurrentText(self.step.get("on_timeout", "stop"))
        self.failure_step = QSpinBox()
        self.failure_step.setRange(1, 10000)
        self.failure_step.setValue(int(self.step.get("failure_step", 1)))
        self.failure_step.setToolTip(
            "Destination used only when this detection step reaches its timeout or maximum check count."
        )
        self.required_detections = QSpinBox()
        self.required_detections.setRange(1, 20)
        self.required_detections.setValue(
            int(self.step.get("required_consecutive_detections", 1))
        )
        self.required_detections.setToolTip(
            "Require the same condition in this many consecutive screen checks before the step passes."
        )
        self.max_detection_attempts = QSpinBox()
        self.max_detection_attempts.setRange(0, 100000)
        self.max_detection_attempts.setSpecialValueText("No limit")
        self.max_detection_attempts.setValue(
            int(self.step.get("max_detection_attempts", 0))
        )
        self.max_detection_attempts.setToolTip(
            "Stop or continue according to If timeout after this many checks. Zero leaves only the step's time-based timeout."
        )
        self.target_x = QSpinBox()
        self.target_x.setRange(0, 100)
        self.target_x.setSuffix("%")
        self.target_x.setValue(round(float(self.step.get("target_x", 0.5)) * 100))
        self.target_y = QSpinBox()
        self.target_y.setRange(0, 100)
        self.target_y.setSuffix("%")
        self.target_y.setValue(round(float(self.step.get("target_y", 0.5)) * 100))
        self.random_offset = QSpinBox()
        self.random_offset.setRange(0, 100)
        self.random_offset.setSuffix(" px")
        self.random_offset.setValue(int(self.step.get("random_offset", 0)))
        self.click_cooldown = QDoubleSpinBox()
        self.click_cooldown.setRange(0, 3600)
        self.click_cooldown.setSingleStep(0.5)
        self.click_cooldown.setSuffix(" sec")
        self.click_cooldown.setSpecialValueText("No cooldown")
        self.click_cooldown.setValue(
            float(self.step.get("click_cooldown_seconds", 0))
        )
        self.click_cooldown.setToolTip(
            "Temporarily ignore the same detected class near the same screen position after clicking it."
        )
        self.wait_after_click = QCheckBox("Wait until the clicked object disappears")
        self.wait_after_click.setChecked(
            bool(self.step.get("wait_after_click_until_disappears", False))
        )
        self.post_click_timeout = QDoubleSpinBox()
        self.post_click_timeout.setRange(0, 3600)
        self.post_click_timeout.setSuffix(" sec")
        self.post_click_timeout.setSpecialValueText("Forever")
        self.post_click_timeout.setValue(
            float(self.step.get("post_click_disappear_timeout", 10))
        )
        self.post_click_timeout.setToolTip(
            "How long to wait for the clicked object to disappear. If timeout controls what happens next."
        )
        self.post_click_timeout.setEnabled(self.wait_after_click.isChecked())
        self.wait_after_click.toggled.connect(self.post_click_timeout.setEnabled)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0, 3600)
        self.duration.setSuffix(" sec")
        self.duration.setValue(float(self.step.get("duration", 1)))
        self.duration_max = QDoubleSpinBox()
        self.duration_max.setRange(0, 3600)
        self.duration_max.setSuffix(" sec")
        self.duration_max.setValue(
            float(self.step.get("duration_max", self.step.get("duration", 1)))
        )
        self.move_duration = QDoubleSpinBox()
        self.move_duration.setRange(0.05, 10)
        self.move_duration.setSingleStep(0.05)
        self.move_duration.setSuffix(" sec")
        self.move_duration.setValue(float(self.step.get("move_duration", 0.35)))
        self.x = QSpinBox()
        self.x.setRange(-100000, 100000)
        self.x.setValue(int(self.step.get("x", 0)))
        self.y = QSpinBox()
        self.y.setRange(-100000, 100000)
        self.y.setValue(int(self.step.get("y", 0)))
        self.coordinate_basis = QComboBox()
        for mode, label in COORDINATE_MODE_LABELS.items():
            self.coordinate_basis.addItem(label, mode)
        self.coordinate_basis.setToolTip(
            "Absolute keeps one screen pixel. Watch-relative scales with the selected monitor. "
            "Application-window-relative follows a visible window when it moves or resizes."
        )
        saved_mode = coordinate_mode(self.step.get("coordinate_mode", "absolute"))
        self.coordinate_basis.setCurrentIndex(
            max(0, self.coordinate_basis.findData(saved_mode))
        )
        if "relative_x" in self.step and "relative_y" in self.step:
            initial_relative_x = float(self.step["relative_x"])
            initial_relative_y = float(self.step["relative_y"])
        elif saved_mode == "watch_relative":
            initial_relative_x, initial_relative_y = relative_point(
                self.x.value(), self.y.value(), self.watch_bounds
            )
        elif saved_mode == "window_relative" and self.window_reference_bounds:
            initial_relative_x, initial_relative_y = relative_point(
                self.x.value(), self.y.value(), self.window_reference_bounds
            )
        else:
            initial_relative_x, initial_relative_y = 0.5, 0.5
        self.relative_x = QDoubleSpinBox()
        self.relative_x.setRange(0, 100)
        self.relative_x.setDecimals(2)
        self.relative_x.setSingleStep(1)
        self.relative_x.setSuffix("%")
        self.relative_x.setValue(initial_relative_x * 100)
        self.relative_y = QDoubleSpinBox()
        self.relative_y.setRange(0, 100)
        self.relative_y.setDecimals(2)
        self.relative_y.setSingleStep(1)
        self.relative_y.setSuffix("%")
        self.relative_y.setValue(initial_relative_y * 100)
        self.window_title = QLineEdit(str(self.step.get("window_title", "")))
        self.window_title.setPlaceholderText("Captured automatically by the picker")
        self.window_title.setReadOnly(True)
        self.window_title.setToolTip(
            "Use a coordinate picker to identify the target application window."
        )
        self.coordinate_status = QLabel()
        self.coordinate_status.setStyleSheet("color: #8fd7ff;")
        coordinate_tools = QWidget()
        coordinate_layout = QHBoxLayout(coordinate_tools)
        coordinate_layout.setContentsMargins(0, 0, 0, 0)
        pick_click = QPushButton("Pick by Click")
        pick_click.setToolTip(
            "Open a full-screen overlay and click once to capture that screen position."
        )
        pick_click.clicked.connect(lambda: self.pick_coordinate("click"))
        pick_hover = QPushButton("Pick by Hover (3s)")
        pick_hover.setToolTip(
            "Open a full-screen overlay and capture the cursor position after three seconds."
        )
        pick_hover.clicked.connect(lambda: self.pick_coordinate("hover"))
        coordinate_layout.addWidget(pick_click)
        coordinate_layout.addWidget(pick_hover)
        self.count = QSpinBox()
        self.count.setRange(1, 100000)
        self.count.setValue(int(self.step.get("count", 1)))
        self.target_step = QSpinBox()
        self.target_step.setRange(1, 10000)
        self.target_step.setValue(int(self.step.get("target_step", 1)))
        self.variable = QLineEdit(str(self.step.get("variable", "counter")))
        self.variable.setMaxLength(64)
        self.variable.setPlaceholderText("Example: completed_runs")
        self.variable.setToolTip(
            "Variable names begin with a letter or underscore and use no spaces. Variables reset at the start of each run."
        )
        self.variable_value = QLineEdit(
            str(self.step.get("variable_value", "0"))
        )
        self.variable_value.setPlaceholderText("Number, true/false, or text")
        self.amount = QDoubleSpinBox()
        self.amount.setRange(-1_000_000_000, 1_000_000_000)
        self.amount.setDecimals(3)
        self.amount.setValue(float(self.step.get("amount", 1)))
        self.comparison = QComboBox()
        self.comparison.addItems(list(COMPARISON_OPERATORS))
        self.comparison.setCurrentText(str(self.step.get("comparison", "==")))
        self.compare_value = QLineEdit(str(self.step.get("compare_value", "0")))
        self.true_step = QSpinBox()
        self.true_step.setRange(0, 10000)
        self.true_step.setSpecialValueText("Next step")
        self.true_step.setValue(int(self.step.get("true_step", 0)))
        self.false_step = QSpinBox()
        self.false_step.setRange(0, 10000)
        self.false_step.setSpecialValueText("Next step")
        self.false_step.setValue(int(self.step.get("false_step", 0)))
        self.called_macro = QComboBox()
        available_macros = [
            macro
            for macro in (macro_choices or [])
            if str(macro.get("id", "")) != str(current_macro_id)
        ]
        for macro in available_macros:
            self.called_macro.addItem(
                str(macro.get("name", "Untitled")), str(macro.get("id", ""))
            )
        saved_macro_id = str(self.step.get("macro_id", ""))
        saved_macro_name = str(self.step.get("macro_name", ""))
        selected_macro = self.called_macro.findData(saved_macro_id)
        if selected_macro < 0 and saved_macro_name:
            selected_macro = self.called_macro.findText(saved_macro_name)
        if selected_macro < 0 and (saved_macro_id or saved_macro_name):
            self.called_macro.addItem(
                f"[Missing] {saved_macro_name or saved_macro_id}", saved_macro_id
            )
            selected_macro = self.called_macro.count() - 1
        if selected_macro >= 0:
            self.called_macro.setCurrentIndex(selected_macro)
        if self.called_macro.count() == 0:
            self.called_macro.addItem("No other macro is available", "")
            self.called_macro.setEnabled(False)
        rows = [
            ("Enabled", self.enabled),
            ("Action", self.action),
            ("Step name / section title", self.step_name),
            ("Comment", self.comment),
            ("Object", self.object),
            ("Objects in priority order", self.objects),
            ("Destination step per object", self.target_steps),
            ("Key / text", self.value),
            ("Minimum confidence", self.confidence),
            ("Minimum timeout", self.timeout),
            ("Maximum timeout (both 0 = forever)", self.timeout_max),
            ("Polling interval", self.poll),
            ("Consecutive confirmations", self.required_detections),
            ("Maximum detection checks", self.max_detection_attempts),
            ("If timeout", self.on_timeout),
            ("Failure destination", self.failure_step),
            ("Click X inside box", self.target_x),
            ("Click Y inside box", self.target_y),
            ("Random pixel offset", self.random_offset),
            ("Clicked-object cooldown", self.click_cooldown),
            ("After clicking", self.wait_after_click),
            ("Disappear wait timeout", self.post_click_timeout),
            ("Minimum wait", self.duration),
            ("Maximum wait", self.duration_max),
            ("Mouse travel time", self.move_duration),
            ("Coordinate basis", self.coordinate_basis),
            ("Screen X", self.x),
            ("Screen Y", self.y),
            ("Horizontal position", self.relative_x),
            ("Vertical position", self.relative_y),
            ("Application window", self.window_title),
            ("Coordinate tools", coordinate_tools),
            ("Selected coordinate", self.coordinate_status),
            ("Repeat count", self.count),
            ("Destination step", self.target_step),
            ("Variable name", self.variable),
            ("Variable value", self.variable_value),
            ("Amount to add", self.amount),
            ("Comparison", self.comparison),
            ("Compare with", self.compare_value),
            ("If true", self.true_step),
            ("If false", self.false_step),
            ("Reusable macro", self.called_macro),
        ]
        self.widgets = {label: widget for label, widget in rows}
        for label, widget in rows:
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.action.currentTextChanged.connect(self.update_visibility)
        self.on_timeout.currentTextChanged.connect(self.update_visibility)
        self.coordinate_basis.currentIndexChanged.connect(
            self.coordinate_basis_changed
        )
        self.x.valueChanged.connect(self.absolute_coordinate_changed)
        self.y.valueChanged.connect(self.absolute_coordinate_changed)
        self.relative_x.valueChanged.connect(self.relative_coordinate_changed)
        self.relative_y.valueChanged.connect(self.relative_coordinate_changed)
        if saved_mode in {"watch_relative", "window_relative"}:
            self.relative_coordinate_changed()
        self.update_visibility()
        self.refresh_coordinate_status()

    def update_visibility(self) -> None:
        action = self.action.currentText()
        visible = {
            "Enabled",
            "Action",
            "Step name / section title",
            "Comment",
        }
        if action in (
            "WAIT_FOR_OBJECT",
            "WAIT_UNTIL_DISAPPEARS",
            "CLICK_OBJECT",
            "RIGHT_CLICK_OBJECT",
        ):
            visible |= {
                "Object",
                "Minimum confidence",
                "Minimum timeout",
                "Maximum timeout (both 0 = forever)",
                "Polling interval",
                "Consecutive confirmations",
                "Maximum detection checks",
                "If timeout",
            }
        if action in ("WAIT_FOR_ANY_OBJECT", "CLICK_FIRST_AVAILABLE"):
            visible |= {
                "Objects in priority order",
                "Minimum confidence",
                "Minimum timeout",
                "Maximum timeout (both 0 = forever)",
                "Polling interval",
                "Consecutive confirmations",
                "Maximum detection checks",
                "If timeout",
            }
        if action in {
            "WAIT_FOR_OBJECT",
            "WAIT_FOR_ANY_OBJECT",
            "WAIT_UNTIL_DISAPPEARS",
            "CLICK_OBJECT",
            "RIGHT_CLICK_OBJECT",
            "CLICK_FIRST_AVAILABLE",
        } and self.on_timeout.currentText() == "go_to_step":
            visible.add("Failure destination")
        if action == "WAIT_FOR_ANY_OBJECT":
            visible.add("Destination step per object")
        if action in ("CLICK_OBJECT", "RIGHT_CLICK_OBJECT", "CLICK_FIRST_AVAILABLE"):
            visible |= {
                "Click X inside box",
                "Click Y inside box",
                "Random pixel offset",
                "Mouse travel time",
                "Clicked-object cooldown",
                "After clicking",
                "Disappear wait timeout",
            }
        if action in ("PRESS_KEY", "TYPE_TEXT"):
            visible.add("Key / text")
        if action == "WAIT":
            visible |= {"Minimum wait", "Maximum wait"}
        if action in ("MOVE_MOUSE", "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            visible |= {
                "Coordinate basis",
                "Coordinate tools",
                "Selected coordinate",
                "Mouse travel time",
            }
            mode = self.coordinate_basis.currentData() or "absolute"
            if mode == "absolute":
                visible |= {"Screen X", "Screen Y"}
            else:
                visible |= {"Horizontal position", "Vertical position"}
            if mode == "window_relative":
                visible.add("Application window")
        if action in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            visible.add("Random pixel offset")
        if action in ("REPEAT", "GOTO_STEP"):
            visible.add("Destination step")
        if action == "REPEAT":
            visible |= {"Repeat count", "Destination step"}
        if action == "SET_VARIABLE":
            visible |= {"Variable name", "Variable value"}
        if action == "ADD_VARIABLE":
            visible |= {"Variable name", "Amount to add"}
        if action == "IF_VARIABLE":
            visible |= {
                "Variable name",
                "Comparison",
                "Compare with",
                "If true",
                "If false",
            }
        if action == "CALL_MACRO":
            visible.add("Reusable macro")
        form = self.layout().itemAt(0).layout()
        for label, widget in self.widgets.items():
            widget.setVisible(label in visible)
            label_widget = form.labelForField(widget)
            if label_widget:
                label_widget.setVisible(label in visible)

    def result_step(self) -> dict:
        action = self.action.currentText()
        result = {"enabled": self.enabled.isChecked(), "action": action}
        if self.step_name.text().strip():
            result["name"] = self.step_name.text().strip()
        if self.comment.text().strip():
            result["comment"] = self.comment.text().strip()
        if action in (
            "WAIT_FOR_OBJECT",
            "WAIT_UNTIL_DISAPPEARS",
            "CLICK_OBJECT",
            "RIGHT_CLICK_OBJECT",
        ):
            result.update(
                {
                    "object": self.object.currentText().strip(),
                    "confidence": self.confidence.value(),
                    "timeout": self.timeout.value(),
                    "timeout_max": self.timeout_max.value(),
                    "poll_interval": self.poll.value(),
                    "required_consecutive_detections": self.required_detections.value(),
                    "max_detection_attempts": self.max_detection_attempts.value(),
                    "on_timeout": self.on_timeout.currentText(),
                }
            )
        if action in ("WAIT_FOR_ANY_OBJECT", "CLICK_FIRST_AVAILABLE"):
            result.update(
                {
                    "objects": object_names(self.objects.text()),
                    "confidence": self.confidence.value(),
                    "timeout": self.timeout.value(),
                    "timeout_max": self.timeout_max.value(),
                    "poll_interval": self.poll.value(),
                    "required_consecutive_detections": self.required_detections.value(),
                    "max_detection_attempts": self.max_detection_attempts.value(),
                    "on_timeout": self.on_timeout.currentText(),
                }
            )
        if action in {
            "WAIT_FOR_OBJECT",
            "WAIT_FOR_ANY_OBJECT",
            "WAIT_UNTIL_DISAPPEARS",
            "CLICK_OBJECT",
            "RIGHT_CLICK_OBJECT",
            "CLICK_FIRST_AVAILABLE",
        } and self.on_timeout.currentText() == "go_to_step":
            result["failure_step"] = self.failure_step.value()
        if action == "WAIT_FOR_ANY_OBJECT":
            result["target_steps"] = destination_steps(self.target_steps.text())
        if action in ("CLICK_OBJECT", "RIGHT_CLICK_OBJECT", "CLICK_FIRST_AVAILABLE"):
            result.update(
                {
                    "target_x": self.target_x.value() / 100,
                    "target_y": self.target_y.value() / 100,
                    "random_offset": self.random_offset.value(),
                    "move_duration": self.move_duration.value(),
                    "click_cooldown_seconds": self.click_cooldown.value(),
                    "wait_after_click_until_disappears": self.wait_after_click.isChecked(),
                    "post_click_disappear_timeout": self.post_click_timeout.value(),
                }
            )
        elif action in ("PRESS_KEY", "TYPE_TEXT"):
            result["value"] = self.value.text()
        elif action == "WAIT":
            result["duration"] = self.duration.value()
            result["duration_max"] = self.duration_max.value()
        elif action == "MOVE_MOUSE":
            result.update(self.coordinate_result())
            result["move_duration"] = self.move_duration.value()
        elif action in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            result.update(self.coordinate_result())
            result["random_offset"] = self.random_offset.value()
            result["move_duration"] = self.move_duration.value()
        elif action == "REPEAT":
            result.update(
                {"count": self.count.value(), "target_step": self.target_step.value()}
            )
        elif action == "GOTO_STEP":
            result["target_step"] = self.target_step.value()
        elif action == "SET_VARIABLE":
            result.update(
                {
                    "variable": self.variable.text().strip(),
                    "variable_value": self.variable_value.text(),
                }
            )
        elif action == "ADD_VARIABLE":
            result.update(
                {
                    "variable": self.variable.text().strip(),
                    "amount": self.amount.value(),
                }
            )
        elif action == "IF_VARIABLE":
            result.update(
                {
                    "variable": self.variable.text().strip(),
                    "comparison": self.comparison.currentText(),
                    "compare_value": self.compare_value.text(),
                    "true_step": self.true_step.value(),
                    "false_step": self.false_step.value(),
                }
            )
        elif action == "CALL_MACRO":
            result.update(
                {
                    "macro_id": str(self.called_macro.currentData() or ""),
                    "macro_name": self.called_macro.currentText(),
                }
            )
        return result

    def coordinate_result(self) -> dict:
        mode = str(self.coordinate_basis.currentData() or "absolute")
        result = {
            "x": self.x.value(),
            "y": self.y.value(),
            "coordinate_mode": mode,
        }
        if mode in {"watch_relative", "window_relative"}:
            result.update(
                {
                    "relative_x": self.relative_x.value() / 100,
                    "relative_y": self.relative_y.value() / 100,
                    "reference_bounds": dict(self.watch_bounds),
                }
            )
        if mode == "window_relative":
            result["window_title"] = self.window_title.text().strip()
            if self.window_class:
                result["window_class"] = self.window_class
            if self.window_reference_bounds:
                result["window_reference_bounds"] = dict(
                    self.window_reference_bounds
                )
        return result

    def pick_coordinate(self, mode: str) -> None:
        if self.coordinate_picker is not None:
            return
        previous_opacity = self.windowOpacity()
        try:
            picker = CoordinatePickerOverlay(
                mode=mode,
                countdown_seconds=3,
                parent=self,
            )
            self.coordinate_picker = picker
            # Keep this dialog visible so its outer exec() loop remains active.
            # Hiding an executing QDialog can finish that loop before the user
            # presses Save, leaving correctly picked values with no caller to
            # persist them. Near-zero opacity reveals the target screen while
            # the child picker safely owns all interaction.
            self.setWindowOpacity(0.01)
            result = picker.exec()
            if (
                result == QDialog.Accepted
                and picker.selected_coordinate is not None
            ):
                x, y = picker.selected_coordinate
                mode_name = str(self.coordinate_basis.currentData() or "absolute")
                if mode_name == "window_relative":
                    if picker.selected_window is None:
                        QMessageBox.warning(
                            self,
                            "Application window not found",
                            "The picker could not identify an application window under that point. "
                            "Try again and select a point inside the target application's window.",
                        )
                        return
                    self.window_reference_bounds = checked_bounds(
                        picker.selected_window
                    )
                    self.window_title.setText(
                        str(picker.selected_window.get("title", ""))
                    )
                    self.window_class = str(
                        picker.selected_window.get("class_name", "")
                    )
                    relative_x, relative_y = relative_point(
                        x, y, self.window_reference_bounds
                    )
                    self.set_relative_values(relative_x, relative_y)
                elif mode_name == "watch_relative":
                    relative_x, relative_y = relative_point(
                        x, y, self.watch_bounds
                    )
                    self.set_relative_values(relative_x, relative_y)
                self.x.setValue(x)
                self.y.setValue(y)
                self.refresh_coordinate_status(picked=True)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Coordinate picker unavailable",
                f"The coordinate picker could not start: {exc}",
            )
        finally:
            self.coordinate_picker = None
            self.setWindowOpacity(previous_opacity)
            self.raise_()
            self.activateWindow()

    def set_relative_values(self, relative_x: float, relative_y: float) -> None:
        self._updating_coordinate = True
        try:
            self.relative_x.setValue(relative_x * 100)
            self.relative_y.setValue(relative_y * 100)
        finally:
            self._updating_coordinate = False

    def coordinate_basis_changed(self, _value=None) -> None:
        mode = str(self.coordinate_basis.currentData() or "absolute")
        if mode == "watch_relative":
            relative_x, relative_y = relative_point(
                self.x.value(), self.y.value(), self.watch_bounds
            )
            self.set_relative_values(relative_x, relative_y)
        elif mode == "window_relative" and self.window_reference_bounds:
            relative_x, relative_y = relative_point(
                self.x.value(), self.y.value(), self.window_reference_bounds
            )
            self.set_relative_values(relative_x, relative_y)
        self.update_visibility()
        self.refresh_coordinate_status()

    def absolute_coordinate_changed(self, _value=None) -> None:
        if self._updating_coordinate:
            return
        mode = str(self.coordinate_basis.currentData() or "absolute")
        if mode == "watch_relative":
            relative_x, relative_y = relative_point(
                self.x.value(), self.y.value(), self.watch_bounds
            )
            self.set_relative_values(relative_x, relative_y)
        elif mode == "window_relative" and self.window_reference_bounds:
            relative_x, relative_y = relative_point(
                self.x.value(), self.y.value(), self.window_reference_bounds
            )
            self.set_relative_values(relative_x, relative_y)
        self.refresh_coordinate_status()

    def relative_coordinate_changed(self, _value=None) -> None:
        if self._updating_coordinate:
            return
        mode = str(self.coordinate_basis.currentData() or "absolute")
        bounds = (
            self.watch_bounds
            if mode == "watch_relative"
            else self.window_reference_bounds
        )
        if bounds:
            x, y = point_from_relative(
                self.relative_x.value() / 100,
                self.relative_y.value() / 100,
                bounds,
            )
            self._updating_coordinate = True
            try:
                self.x.setValue(x)
                self.y.setValue(y)
            finally:
                self._updating_coordinate = False
        self.refresh_coordinate_status()

    def refresh_coordinate_status(self, _value=None, *, picked: bool = False) -> None:
        prefix = "Picked" if picked else "Current"
        mode = str(self.coordinate_basis.currentData() or "absolute")
        if mode == "absolute":
            detail = f"screen X {self.x.value()}, Y {self.y.value()}"
        elif mode == "watch_relative":
            detail = (
                f"Watch {self.relative_x.value():g}%, {self.relative_y.value():g}% "
                f"→ X {self.x.value()}, Y {self.y.value()} at the current resolution"
            )
        else:
            title = self.window_title.text().strip() or "choose a window with the picker"
            detail = (
                f"{title} · {self.relative_x.value():g}%, "
                f"{self.relative_y.value():g}%"
            )
        self.coordinate_status.setText(f"{prefix}: {detail}")

    def accept(self) -> None:
        action = self.action.currentText()
        if action == "SECTION" and not self.step_name.text().strip():
            QMessageBox.warning(
                self,
                "Name this section",
                "Enter a section title so the divider is recognizable in the Macro Builder.",
            )
            return
        detection_actions = {
            "WAIT_FOR_OBJECT",
            "WAIT_FOR_ANY_OBJECT",
            "WAIT_UNTIL_DISAPPEARS",
            "CLICK_OBJECT",
            "RIGHT_CLICK_OBJECT",
            "CLICK_FIRST_AVAILABLE",
        }
        if action in {"SET_VARIABLE", "ADD_VARIABLE", "IF_VARIABLE"} and not valid_variable_name(
            self.variable.text()
        ):
            QMessageBox.warning(
                self,
                "Invalid variable name",
                "Use a name that begins with a letter or underscore and contains only letters, numbers, and underscores.",
            )
            return
        if action == "CALL_MACRO" and not str(self.called_macro.currentData() or ""):
            QMessageBox.warning(
                self,
                "Choose a reusable macro",
                "Create another macro first, then select it here.",
            )
            return
        if (
            action in detection_actions
            and self.timeout_max.value() < self.timeout.value()
        ):
            QMessageBox.warning(
                self,
                "Invalid timeout range",
                "Maximum timeout must be equal to or greater than minimum timeout.",
            )
            return
        if action == "WAIT" and self.duration_max.value() < self.duration.value():
            QMessageBox.warning(
                self,
                "Invalid wait range",
                "Maximum wait must be equal to or greater than minimum wait.",
            )
            return
        if (
            action in ("MOVE_MOUSE", "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK")
            and self.coordinate_basis.currentData() == "window_relative"
            and not self.window_title.text().strip()
        ):
            QMessageBox.warning(
                self,
                "Choose an application window",
                "Use Pick by Click or Pick by Hover while Application window is selected. "
                "The picker records both the window and the relative position.",
            )
            return
        if action in ("WAIT_FOR_ANY_OBJECT", "CLICK_FIRST_AVAILABLE"):
            names = object_names(self.objects.text())
            if not names:
                QMessageBox.warning(
                    self, "Choose objects", "Enter at least one object name."
                )
                return
            lowered = [name.casefold() for name in names]
            if len(set(lowered)) != len(lowered):
                QMessageBox.warning(
                    self,
                    "Duplicate objects",
                    "Each object should appear only once in the priority list.",
                )
                return
            if action == "WAIT_FOR_ANY_OBJECT":
                try:
                    targets = destination_steps(self.target_steps.text())
                except ValueError as exc:
                    QMessageBox.warning(self, "Invalid destinations", str(exc))
                    return
                if len(targets) != len(names):
                    QMessageBox.warning(
                        self,
                        "Match destinations",
                        "Enter one destination step for each object. Use 0 to continue to the next step.",
                    )
                    return
        super().accept()
