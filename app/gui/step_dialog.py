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
from app.gui.coordinate_picker import CoordinatePickerOverlay

ACTIONS = list(SUPPORTED_ACTIONS)


class StepDialog(QDialog):
    def __init__(
        self, classes: list[str], step: dict | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro Step")
        self.setMinimumWidth(430)
        self.step = step or {}
        self.coordinate_picker: CoordinatePickerOverlay | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.enabled = QCheckBox("Run this step")
        self.enabled.setChecked(self.step.get("enabled", True))
        self.action = QComboBox()
        self.action.addItems(ACTIONS)
        self.action.setCurrentText(self.step.get("action", ACTIONS[0]))
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
        self.on_timeout.addItems(["stop", "continue"])
        self.on_timeout.setCurrentText(self.step.get("on_timeout", "stop"))
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
        self.coordinate_status = QLabel()
        self.coordinate_status.setStyleSheet("color: #8fd7ff;")
        self.x.valueChanged.connect(self.refresh_coordinate_status)
        self.y.valueChanged.connect(self.refresh_coordinate_status)
        self.refresh_coordinate_status()
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
        rows = [
            ("Enabled", self.enabled),
            ("Action", self.action),
            ("Object", self.object),
            ("Objects in priority order", self.objects),
            ("Destination step per object", self.target_steps),
            ("Key / text", self.value),
            ("Minimum confidence", self.confidence),
            ("Minimum timeout", self.timeout),
            ("Maximum timeout (both 0 = forever)", self.timeout_max),
            ("Polling interval", self.poll),
            ("If timeout", self.on_timeout),
            ("Click X inside box", self.target_x),
            ("Click Y inside box", self.target_y),
            ("Random pixel offset", self.random_offset),
            ("Minimum wait", self.duration),
            ("Maximum wait", self.duration_max),
            ("Mouse travel time", self.move_duration),
            ("Screen X", self.x),
            ("Screen Y", self.y),
            ("Coordinate tools", coordinate_tools),
            ("Selected coordinate", self.coordinate_status),
            ("Repeat count", self.count),
            ("Destination step", self.target_step),
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
        self.update_visibility()

    def update_visibility(self) -> None:
        action = self.action.currentText()
        visible = {"Enabled", "Action"}
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
                "If timeout",
            }
        if action in ("WAIT_FOR_ANY_OBJECT", "CLICK_FIRST_AVAILABLE"):
            visible |= {
                "Objects in priority order",
                "Minimum confidence",
                "Minimum timeout",
                "Maximum timeout (both 0 = forever)",
                "Polling interval",
                "If timeout",
            }
        if action == "WAIT_FOR_ANY_OBJECT":
            visible.add("Destination step per object")
        if action in ("CLICK_OBJECT", "RIGHT_CLICK_OBJECT", "CLICK_FIRST_AVAILABLE"):
            visible |= {
                "Click X inside box",
                "Click Y inside box",
                "Random pixel offset",
                "Mouse travel time",
            }
        if action in ("PRESS_KEY", "TYPE_TEXT"):
            visible.add("Key / text")
        if action == "WAIT":
            visible |= {"Minimum wait", "Maximum wait"}
        if action in ("MOVE_MOUSE", "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            visible |= {
                "Screen X",
                "Screen Y",
                "Coordinate tools",
                "Selected coordinate",
                "Mouse travel time",
            }
        if action in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            visible.add("Random pixel offset")
        if action in ("REPEAT", "GOTO_STEP"):
            visible.add("Destination step")
        if action == "REPEAT":
            visible |= {"Repeat count", "Destination step"}
        form = self.layout().itemAt(0).layout()
        for label, widget in self.widgets.items():
            widget.setVisible(label in visible)
            label_widget = form.labelForField(widget)
            if label_widget:
                label_widget.setVisible(label in visible)

    def result_step(self) -> dict:
        action = self.action.currentText()
        result = {"enabled": self.enabled.isChecked(), "action": action}
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
                    "on_timeout": self.on_timeout.currentText(),
                }
            )
        if action == "WAIT_FOR_ANY_OBJECT":
            result["target_steps"] = destination_steps(self.target_steps.text())
        if action in ("CLICK_OBJECT", "RIGHT_CLICK_OBJECT", "CLICK_FIRST_AVAILABLE"):
            result.update(
                {
                    "target_x": self.target_x.value() / 100,
                    "target_y": self.target_y.value() / 100,
                    "random_offset": self.random_offset.value(),
                    "move_duration": self.move_duration.value(),
                }
            )
        elif action in ("PRESS_KEY", "TYPE_TEXT"):
            result["value"] = self.value.text()
        elif action == "WAIT":
            result["duration"] = self.duration.value()
            result["duration_max"] = self.duration_max.value()
        elif action == "MOVE_MOUSE":
            result.update(
                {
                    "x": self.x.value(),
                    "y": self.y.value(),
                    "move_duration": self.move_duration.value(),
                }
            )
        elif action in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            result.update(
                {
                    "x": self.x.value(),
                    "y": self.y.value(),
                    "random_offset": self.random_offset.value(),
                    "move_duration": self.move_duration.value(),
                }
            )
        elif action == "REPEAT":
            result.update(
                {"count": self.count.value(), "target_step": self.target_step.value()}
            )
        elif action == "GOTO_STEP":
            result["target_step"] = self.target_step.value()
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

    def refresh_coordinate_status(self, _value=None, *, picked: bool = False) -> None:
        prefix = "Picked" if picked else "Current"
        self.coordinate_status.setText(
            f"{prefix}: X {self.x.value()}, Y {self.y.value()}"
        )

    def accept(self) -> None:
        action = self.action.currentText()
        detection_actions = {
            "WAIT_FOR_OBJECT",
            "WAIT_FOR_ANY_OBJECT",
            "WAIT_UNTIL_DISAPPEARS",
            "CLICK_OBJECT",
            "RIGHT_CLICK_OBJECT",
            "CLICK_FIRST_AVAILABLE",
        }
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
