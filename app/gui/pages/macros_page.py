from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import time
import uuid

import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.automation.coordinates import (
    absolute_region_from_normalized,
    coordinate_mode,
    detection_region_label,
    normalized_region_from_absolute,
)
from app.automation.debugger import (
    analyze_step,
    step_needs_detection,
    step_needs_screen_preview,
)
from app.automation.engine import MacroWorker
from app.automation.control import destination_steps, object_names
from app.automation.flow import step_destinations
from app.automation.macro_io import (
    MacroFormatError,
    delete_step_preserving_destinations,
    duplicate_step_preserving_destinations,
    export_macro_file,
    has_absolute_coordinate_steps,
    has_coordinate_steps,
    import_macro_file,
    insert_step_preserving_destinations,
    find_macro_reference,
    referenced_objects,
    reorder_steps_preserving_destinations,
    unique_macro_name,
)
from app.automation.recorder import MacroRecorder
from app.automation.validator import analyze_macro, issue_counts
from app.capture.grabber import grab_screen, list_monitors, monitor_bounds
from app.core.context import AppContext
from app.gui.macro_debug_dialog import MacroDebugDialog
from app.gui.macro_flow_dialog import MacroFlowDialog
from app.gui.macro_overlay import MacroStatusOverlay
from app.gui.macro_validation_dialog import MacroValidationDialog
from app.gui.region_picker import DetectionRegionPickerOverlay
from app.gui.step_dialog import StepDialog
from app.gui.widgets import page_header
from app.vision.detector import Detector, class_name_key, draw_detections
from app.vision.model_manager import preferred_model


class MacroStepsTable(QTableWidget):
    """A single-row drag table that leaves data changes to the Macro Builder."""

    row_drop_requested = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(0, 4, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dropEvent(self, event) -> None:
        if event.source() is not self:
            event.ignore()
            return
        source = self.currentRow()
        position = event.position().toPoint()
        target = self.indexAt(position).row()
        if target < 0:
            target = self.rowCount()
        elif (
            self.dropIndicatorPosition()
            == QAbstractItemView.DropIndicatorPosition.BelowItem
        ):
            target += 1
        if target > source:
            target -= 1
        target = max(0, min(target, self.rowCount() - 1))
        if source >= 0 and source != target:
            self.row_drop_requested.emit(source, target)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class StepDebugWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        step: dict,
        step_index: int,
        step_count: int,
        model_path: str | None,
        monitor_index: int,
        detection_region: dict | None = None,
        capture_delay: float = 0.0,
    ) -> None:
        super().__init__()
        self.step = step
        self.step_index = step_index
        self.step_count = step_count
        self.model_path = model_path
        self.monitor_index = monitor_index
        self.detection_region = deepcopy(detection_region)
        self.capture_delay = max(0.0, float(capture_delay))

    @Slot()
    def run(self) -> None:
        try:
            detections = []
            grab = None
            if step_needs_screen_preview(self.step):
                if self.capture_delay:
                    time.sleep(self.capture_delay)
                grab = grab_screen(
                    self.monitor_index,
                    self.detection_region
                    if step_needs_detection(self.step)
                    else None,
                )
            if step_needs_detection(self.step):
                if not self.model_path:
                    raise RuntimeError(
                        "This step uses object detection, but no accepted model is available."
                    )
                detections = Detector(self.model_path).predict(grab.image, 0.05)
            origin = (grab.left, grab.top) if grab else (0, 0)
            report = analyze_step(
                self.step,
                self.step_index,
                self.step_count,
                detections,
                origin,
                watch_bounds=grab.source_bounds if grab else None,
            )
            if self.detection_region and step_needs_detection(self.step):
                report["details"].append(
                    "Inference was limited to the macro's saved detection region; "
                    "the preview image shows only that region."
                )
            if grab is not None:
                annotated = draw_detections(np.asarray(grab.image), detections)
                preview_image = Image.fromarray(annotated)
                marker = report.get("marker")
                if marker is not None:
                    local_x = int(marker[0]) - grab.left
                    local_y = int(marker[1]) - grab.top
                    if 0 <= local_x < preview_image.width and 0 <= local_y < preview_image.height:
                        draw = ImageDraw.Draw(preview_image)
                        radius = 15
                        draw.ellipse(
                            (
                                local_x - radius,
                                local_y - radius,
                                local_x + radius,
                                local_y + radius,
                            ),
                            outline=(255, 82, 104),
                            width=4,
                        )
                        draw.line(
                            (local_x - 22, local_y, local_x + 22, local_y),
                            fill=(255, 82, 104),
                            width=3,
                        )
                        draw.line(
                            (local_x, local_y - 22, local_x, local_y + 22),
                            fill=(255, 82, 104),
                            width=3,
                        )
                        report["details"].append(
                            "The red marker shows the configured click or movement target."
                        )
                    else:
                        report["details"].append(
                            "The configured coordinate is outside the selected Watch source."
                        )
                report["preview"] = np.asarray(preview_image)
            else:
                report["preview"] = None
            self.completed.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))


class MacrosPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.thread = None
        self.worker = None
        self.debug_thread = None
        self.debug_worker = None
        self.pending_debug_report = None
        self.last_decision = ""
        self.debug_minimized_window = False
        self.debug_window_was_maximized = False
        self.status_overlay = MacroStatusOverlay(self)
        self.status_overlay.position_changed.connect(self.save_overlay_position)
        self.recorder = MacroRecorder()
        self.recorder.error.connect(
            lambda m: QMessageBox.critical(self, "Recorder error", m)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Macro Builder",
                "Build connected visual logic with named steps, variables, failure "
                "routes, and reusable submacros; validate before running.",
            )
        )
        macro_bar = QHBoxLayout()
        self.macro_combo = QComboBox()
        self.macro_combo.currentIndexChanged.connect(self.refresh_steps)
        new_button = QPushButton("New Macro")
        new_button.clicked.connect(self.new_macro)
        rename_button = QPushButton("Rename")
        rename_button.clicked.connect(self.rename_macro)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.delete_macro)
        import_button = QPushButton("Import Macro")
        import_button.clicked.connect(self.import_macro)
        export_button = QPushButton("Export Macro")
        export_button.clicked.connect(self.export_macro)
        macro_bar.addWidget(QLabel("Macro"))
        macro_bar.addWidget(self.macro_combo, 1)
        macro_bar.addWidget(new_button)
        macro_bar.addWidget(rename_button)
        macro_bar.addWidget(delete_button)
        macro_bar.addWidget(import_button)
        macro_bar.addWidget(export_button)
        layout.addLayout(macro_bar)
        self.table = MacroStepsTable(self)
        self.table.setHorizontalHeaderLabels(["On", "#", "Step", "Details"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip(
            "Select a row to edit it, or drag a row to reorder the macro. "
            "Numbered branches are updated automatically."
        )
        self.table.doubleClicked.connect(self.edit_step)
        self.table.itemChanged.connect(self._enabled_changed)
        self.table.row_drop_requested.connect(self.drag_step)
        layout.addWidget(self.table, 1)
        edit_bar = QHBoxLayout()
        self.edit_buttons: list[QPushButton] = []
        for text, callback in (
            ("Add Step", self.add_step),
            ("Add Section", self.add_section),
            ("Edit", self.edit_step),
            ("Duplicate", self.duplicate_step),
            ("Delete Step", self.delete_step),
            ("Move Up", lambda: self.move_step(-1)),
            ("Move Down", lambda: self.move_step(1)),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            edit_bar.addWidget(button)
            self.edit_buttons.append(button)
        edit_bar.addStretch()
        self.flow_button = QPushButton("FLOW VIEW")
        self.flow_button.setToolTip(
            "Open a connected overview of normal flow, branches, loops, and failure routes."
        )
        self.flow_button.clicked.connect(self.show_flow_view)
        edit_bar.addWidget(self.flow_button)
        self.validate_button = QPushButton("VALIDATE MACRO")
        self.validate_button.setToolTip(
            "Check destinations, classes, disabled targets, unreachable steps, "
            "and unbounded loops."
        )
        self.validate_button.clicked.connect(self.validate_current_macro)
        edit_bar.addWidget(self.validate_button)
        layout.addLayout(edit_bar)
        self.debug = QLabel("Debug: idle")
        self.debug.setWordWrap(True)
        self.debug.setStyleSheet("padding:10px; background:#111c2f; border-radius:6px;")
        layout.addWidget(self.debug)
        options_bar = QHBoxLayout()
        self.overlay_check = QCheckBox("Show compact status overlay")
        self.overlay_check.setChecked(
            bool(self.context.config.get("macro_overlay_enabled", True))
        )
        self.overlay_check.toggled.connect(self.overlay_toggled)
        self.model_status = QLabel("Model: none")
        self.model_status.setObjectName("Subtitle")
        self.model_status.setMaximumWidth(230)
        self.monitor_combo = QComboBox()
        self.monitor_combo.setMinimumWidth(145)
        self.populate_monitors()
        self.monitor_combo.currentIndexChanged.connect(self.monitor_changed)
        self.time_limit = QDoubleSpinBox()
        self.time_limit.setRange(0, 1440)
        self.time_limit.setDecimals(1)
        self.time_limit.setSingleStep(1)
        self.time_limit.setSuffix(" min")
        self.time_limit.setSpecialValueText("No limit")
        self.time_limit.setToolTip(
            "Maximum time this macro may run. No limit keeps it running until it completes or you press F12."
        )
        self.time_limit.valueChanged.connect(self.time_limit_changed)
        options_bar.addWidget(self.overlay_check)
        options_bar.addWidget(self.model_status)
        options_bar.addStretch()
        options_bar.addWidget(QLabel("Watch"))
        options_bar.addWidget(self.monitor_combo)
        options_bar.addWidget(QLabel("Stop after"))
        options_bar.addWidget(self.time_limit)
        layout.addLayout(options_bar)
        region_bar = QHBoxLayout()
        region_bar.addWidget(QLabel("Detection region"))
        self.region_status = QLabel("Full Watch source")
        self.region_status.setObjectName("Subtitle")
        self.region_status.setToolTip(
            "Object detection is run only inside this portion of the selected Watch source."
        )
        self.draw_region_button = QPushButton("DRAW REGION")
        self.draw_region_button.setToolTip(
            "Draw the portion of the selected Watch source used for object detection."
        )
        self.draw_region_button.clicked.connect(self.draw_detection_region)
        self.clear_region_button = QPushButton("USE FULL SOURCE")
        self.clear_region_button.clicked.connect(self.clear_detection_region)
        region_bar.addWidget(self.region_status, 1)
        region_bar.addWidget(self.draw_region_button)
        region_bar.addWidget(self.clear_region_button)
        layout.addLayout(region_bar)
        debug_bar = QHBoxLayout()
        debug_bar.addWidget(QLabel("Macro debugger"))
        self.test_button = QPushButton("SAFE STEP PREVIEW (3s)")
        self.test_button.setToolTip(
            "Temporarily minimize Vision Macro Studio, wait three seconds, then inspect one screen frame without sending mouse or keyboard input."
        )
        self.test_button.clicked.connect(self.test_selected_step)
        debug_bar.addWidget(self.test_button)
        debug_bar.addStretch()
        layout.addLayout(debug_bar)
        run_bar = QHBoxLayout()
        self.run_button = QPushButton("RUN MACRO")
        self.run_button.setObjectName("Primary")
        self.run_button.clicked.connect(self.run_macro)
        self.loop_button = QPushButton("RUN ONE LOOP")
        self.loop_button.setToolTip(
            "Execute the macro until it finishes or would return to step 1. Live mouse and keyboard actions are enabled."
        )
        self.loop_button.clicked.connect(self.run_one_loop)
        self.single_button = QPushButton("RUN SELECTED STEP")
        self.single_button.setToolTip(
            "Execute only the selected step. Live mouse and keyboard actions are enabled."
        )
        self.single_button.clicked.connect(self.run_single_step)
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self.start_recording)
        self.stop_record_button = QPushButton("Stop Recording")
        self.stop_record_button.clicked.connect(self.stop_recording)
        self.stop_record_button.setEnabled(False)
        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.clicked.connect(self.emergency_stop)
        run_bar.addWidget(self.run_button)
        run_bar.addWidget(self.loop_button)
        run_bar.addWidget(self.single_button)
        run_bar.addWidget(self.record_button)
        run_bar.addWidget(self.stop_record_button)
        run_bar.addStretch()
        run_bar.addWidget(self.stop_button)
        layout.addLayout(run_bar)
        context.project_changed.connect(self.refresh_macros)
        context.macros_changed.connect(self.refresh_macros)
        context.models_changed.connect(self.refresh_runtime_options)
        self.refresh_macros()

    def populate_monitors(self) -> None:
        self.monitor_combo.clear()
        self.monitor_combo.addItem("Entire desktop", 0)
        try:
            for index, monitor in enumerate(list_monitors()[1:], 1):
                self.monitor_combo.addItem(
                    f"Monitor {index} ({monitor['width']}×{monitor['height']})", index
                )
        except Exception:
            pass

    def refresh_runtime_options(self) -> None:
        macro = self.current_macro()
        monitor_index = int(macro.get("monitor_index", 0)) if macro else 0
        self.monitor_combo.blockSignals(True)
        combo_index = self.monitor_combo.findData(monitor_index)
        self.monitor_combo.setCurrentIndex(max(0, combo_index))
        self.monitor_combo.setEnabled(
            macro is not None and self.worker is None and self.debug_worker is None
        )
        self.monitor_combo.blockSignals(False)
        model = preferred_model(self.context.projects)
        model_name = str(model.get("name", "none")) if model else "none"
        self.model_status.setText(f"Model: {model_name}")
        self.model_status.setToolTip(
            f"Macros use the accepted model: {model_name}"
            if model
            else "Accept a model before running detection steps."
        )
        active = macro is not None and self.worker is None and self.debug_worker is None
        for button in self.edit_buttons:
            button.setEnabled(active)
        self.table.setDragEnabled(active)
        self.validate_button.setEnabled(active)
        self.flow_button.setEnabled(active)
        self.draw_region_button.setEnabled(active)
        self.clear_region_button.setEnabled(
            active and bool(macro.get("detection_region"))
        )
        if macro is None:
            self.region_status.setText("No macro selected")
        else:
            try:
                label = detection_region_label(macro.get("detection_region"))
            except Exception:
                label = "Invalid saved region"
            self.region_status.setText(label)

    def current_macro(self) -> dict | None:
        if not self.context.projects.data:
            return None
        index = self.macro_combo.currentData()
        macros = self.context.projects.data.get("macros", [])
        if isinstance(index, int) and 0 <= index < len(macros):
            return macros[index]
        return None

    def refresh_macros(self) -> None:
        current_index = self.macro_combo.currentData()
        self.macro_combo.blockSignals(True)
        self.macro_combo.clear()
        if self.context.projects.data:
            macros = self.context.projects.data["macros"]
            for index, macro in enumerate(macros):
                # Store only a stable list index. Qt may convert a Python dict
                # to a copied QVariantMap, which made edits disappear on Save.
                self.macro_combo.addItem(macro["name"], index)
            if macros:
                if not isinstance(current_index, int):
                    current_index = 0
                self.macro_combo.setCurrentIndex(
                    max(0, min(current_index, len(macros) - 1))
                )
        self.macro_combo.blockSignals(False)
        self.refresh_steps()

    def refresh_steps(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        macro = self.current_macro()
        self.time_limit.blockSignals(True)
        self.time_limit.setEnabled(macro is not None and self.worker is None)
        self.time_limit.setValue(
            float(macro.get("time_limit_minutes", 0)) if macro else 0
        )
        self.time_limit.blockSignals(False)
        self.refresh_runtime_options()
        if not macro:
            self.table.blockSignals(False)
            return
        try:
            for index, step in enumerate(macro.get("steps", [])):
                row = self.table.rowCount()
                self.table.insertRow(row)
                is_section = step.get("action") == "SECTION"
                enabled = QTableWidgetItem()
                enabled.setData(Qt.UserRole, index)
                if is_section:
                    enabled.setText("—")
                    enabled.setFlags(enabled.flags() & ~Qt.ItemIsUserCheckable)
                else:
                    enabled.setFlags(enabled.flags() | Qt.ItemIsUserCheckable)
                    enabled.setCheckState(
                        Qt.Checked if step.get("enabled", True) else Qt.Unchecked
                    )
                number_item = QTableWidgetItem(str(index + 1))
                action = str(step.get("action", ""))
                action_label = action.replace("_", " ").title()
                name = str(step.get("name", "")).strip()
                comment = str(step.get("comment", "")).strip()
                if is_section:
                    step_text = f"◆  {name or 'Untitled section'}"
                    details = comment or "Visual divider · no input action"
                else:
                    step_text = name or action_label
                    action_details = self.describe_step(step)
                    details = action_label
                    if action_details:
                        details += " · " + action_details
                    if comment:
                        details += " — " + comment
                step_item = QTableWidgetItem(step_text)
                detail_item = QTableWidgetItem(details)
                items = (enabled, number_item, step_item, detail_item)
                for column, item in enumerate(items):
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if comment:
                        item.setToolTip(comment)
                    self.table.setItem(row, column, item)
                if is_section:
                    background = QBrush(QColor("#174a50"))
                    foreground = QBrush(QColor("#d8fff4"))
                    for item in items:
                        item.setBackground(background)
                        item.setForeground(foreground)
                        font = QFont(item.font())
                        font.setBold(True)
                        item.setFont(font)
                    self.table.setRowHeight(row, 36)
        finally:
            self.table.blockSignals(False)

    @staticmethod
    def describe_step(step: dict) -> str:
        def seconds_range(minimum_key: str, maximum_key: str, default: float) -> str:
            minimum = float(step.get(minimum_key, default))
            maximum = float(step.get(maximum_key, minimum))
            if minimum == 0 and maximum == 0:
                return "forever"
            if minimum == maximum:
                return f"{minimum:g}s"
            return f"{minimum:g}–{maximum:g}s"

        def stability_suffix() -> str:
            settings: list[str] = []
            required = max(
                1, int(step.get("required_consecutive_detections", 1))
            )
            maximum = max(0, int(step.get("max_detection_attempts", 0)))
            cooldown = max(0.0, float(step.get("click_cooldown_seconds", 0)))
            if required > 1:
                settings.append(f"confirm ×{required}")
            if maximum > 0:
                settings.append(f"max {maximum} checks")
            if cooldown > 0:
                settings.append(f"cooldown {cooldown:g}s")
            if step.get("wait_after_click_until_disappears", False):
                timeout = max(
                    0.0, float(step.get("post_click_disappear_timeout", 10))
                )
                timeout_text = "forever" if timeout == 0 else f"{timeout:g}s"
                settings.append(f"wait clear {timeout_text}")
            return "" if not settings else " · " + " · ".join(settings)

        action = step.get("action")
        if action == "CLICK_FIRST_AVAILABLE":
            names = object_names(step.get("objects", []))
            result = (
                f"{' → '.join(names)} · ≥{float(step.get('confidence', 0.7)):.0%}"
                f" · timeout {seconds_range('timeout', 'timeout_max', 30)}"
                f"{stability_suffix()}"
            )
            if step.get("on_timeout") == "go_to_step":
                result += f" · timeout→{step.get('failure_step', 1)}"
            return result
        if action == "WAIT_FOR_ANY_OBJECT":
            names = object_names(step.get("objects", []))
            targets = destination_steps(step.get("target_steps", []))
            routes = [
                f"{name}→{'next' if target == 0 else target}"
                for name, target in zip(names, targets)
            ]
            result = (
                f"{', '.join(routes)} · ≥{float(step.get('confidence', 0.7)):.0%}"
                f" · timeout {seconds_range('timeout', 'timeout_max', 30)}"
                f"{stability_suffix()}"
            )
            if step.get("on_timeout") == "go_to_step":
                result += f" · timeout→{step.get('failure_step', 1)}"
            return result
        if "OBJECT" in str(action) or "DISAPPEARS" in str(action):
            result = (
                f"{step.get('object')} · ≥{float(step.get('confidence', 0.7)):.0%}"
                f" · timeout {seconds_range('timeout', 'timeout_max', 30)}"
                f"{stability_suffix()}"
            )
            if step.get("on_timeout") == "go_to_step":
                result += f" · timeout→{step.get('failure_step', 1)}"
            return result
        if action in ("PRESS_KEY", "TYPE_TEXT"):
            return str(step.get("value", ""))
        if action == "WAIT":
            return seconds_range("duration", "duration_max", 1)
        if action in ("MOVE_MOUSE", "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            mode = coordinate_mode(step.get("coordinate_mode", "absolute"))
            offset = (
                f" · ±{step.get('random_offset', 0)} px"
                if action != "MOVE_MOUSE"
                else ""
            )
            if mode == "watch_relative":
                position = (
                    f"Watch {float(step.get('relative_x', 0)):.1%}, "
                    f"{float(step.get('relative_y', 0)):.1%} · scales"
                )
            elif mode == "window_relative":
                title = str(step.get("window_title", "Window"))
                if len(title) > 36:
                    title = title[:33] + "…"
                position = (
                    f"{title} · {float(step.get('relative_x', 0)):.1%}, "
                    f"{float(step.get('relative_y', 0)):.1%} · follows/scales"
                )
            else:
                position = f"Screen ({step.get('x')}, {step.get('y')})"
            return position + offset
        if action == "REPEAT":
            return f"repeat {step.get('count', 1)} time(s), return to step {step.get('target_step', 1)}"
        if action == "GOTO_STEP":
            return f"go to step {step.get('target_step', 1)}"
        if action == "SET_VARIABLE":
            return f"{step.get('variable', 'counter')} = {step.get('variable_value', '0')}"
        if action == "ADD_VARIABLE":
            return f"{step.get('variable', 'counter')} += {float(step.get('amount', 1)):g}"
        if action == "IF_VARIABLE":
            true_step = step.get("true_step", 0) or "next"
            false_step = step.get("false_step", 0) or "next"
            return (
                f"{step.get('variable', 'counter')} {step.get('comparison', '==')} "
                f"{step.get('compare_value', '0')} · true→{true_step} · false→{false_step}"
            )
        if action == "CALL_MACRO":
            return f"run {step.get('macro_name') or step.get('macro_id')} and return"
        return ""

    def _enabled_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        macro = self.current_macro()
        if macro:
            index = item.data(Qt.UserRole)
            macro["steps"][index]["enabled"] = item.checkState() == Qt.Checked
            self.save()

    def new_macro(self) -> None:
        if not self.context.projects.data:
            QMessageBox.information(self, "Open a project", "Open a project first.")
            return
        name, ok = QInputDialog.getText(self, "New Macro", "Macro name:")
        if ok and name.strip():
            macro = {
                "id": str(uuid.uuid4()),
                "name": name.strip(),
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "time_limit_minutes": 0,
                "monitor_index": int(
                    self.context.config.get("preferred_monitor", 1)
                ),
                "steps": [],
            }
            self.context.projects.data["macros"].append(macro)
            self.save()
            self.context.macros_changed.emit()
            self.macro_combo.setCurrentIndex(self.macro_combo.count() - 1)

    def rename_macro(self) -> None:
        macro = self.current_macro()
        if not macro:
            return
        name, ok = QInputDialog.getText(
            self, "Rename Macro", "Name:", text=macro["name"]
        )
        if ok and name.strip():
            macro_id = str(macro.get("id", ""))
            macro["name"] = name.strip()
            for candidate in self.context.projects.data.get("macros", []):
                for step in candidate.get("steps", []):
                    if (
                        step.get("action") == "CALL_MACRO"
                        and macro_id
                        and str(step.get("macro_id", "")) == macro_id
                    ):
                        step["macro_name"] = macro["name"]
            self.save()
            self.context.macros_changed.emit()

    def delete_macro(self) -> None:
        macro = self.current_macro()
        if not macro:
            return
        macro_id = str(macro.get("id", ""))
        macro_name = str(macro.get("name", ""))
        callers: list[str] = []
        for candidate in self.context.projects.data.get("macros", []):
            if candidate is macro:
                continue
            if any(
                step.get("action") == "CALL_MACRO"
                and (
                    (macro_id and str(step.get("macro_id", "")) == macro_id)
                    or (
                        not step.get("macro_id")
                        and str(step.get("macro_name", "")).casefold()
                        == macro_name.casefold()
                    )
                )
                for step in candidate.get("steps", [])
            ):
                callers.append(str(candidate.get("name", "Untitled")))
        message = f"Delete {macro_name}?"
        if callers:
            message += (
                "\n\nIt is called by: "
                + ", ".join(callers)
                + ". Those macros will fail validation until their Call Macro steps are changed."
            )
        if QMessageBox.question(self, "Delete Macro", message) != QMessageBox.Yes:
            return
        self.context.projects.data["macros"].remove(macro)
        self.save()
        self.context.macros_changed.emit()

    def export_macro(self) -> None:
        macro = self.current_macro()
        if macro is None:
            QMessageBox.information(
                self, "Choose a macro", "Create or select a macro to export."
            )
            return
        filename = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in macro["name"]
        ).strip("_")
        filename = (filename or "Vision_Macro") + ".vmsmacro.json"
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "Export Macro",
            filename,
            "Vision Macro Studio Macro (*.vmsmacro.json);;JSON (*.json)",
        )
        if not selected:
            return
        destination = Path(selected)
        if not destination.name.lower().endswith(".json"):
            destination = destination.with_name(
                destination.name + ".vmsmacro.json"
            )
        try:
            export_macro_file(
                destination,
                macro,
                __version__,
                screen_layout=list_monitors(),
                macro_library=self.context.projects.data.get("macros", []),
            )
        except (MacroFormatError, OSError, ValueError) as exc:
            QMessageBox.critical(
                self, "Macro export failed", f"The macro could not be exported: {exc}"
            )
            return
        self.context.log(f"Exported macro: {destination}")
        QMessageBox.information(
            self,
            "Macro exported",
            f"Saved {macro['name']} to:\n{destination}",
        )

    def import_macro(self) -> None:
        if not self.context.projects.data:
            QMessageBox.information(self, "Open a project", "Open a project first.")
            return
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Import Macro",
            "",
            "Vision Macro Studio Macro (*.vmsmacro.json *.json);;JSON (*.json)",
        )
        if not selected:
            return
        try:
            macro, metadata = import_macro_file(Path(selected))
        except MacroFormatError as exc:
            QMessageBox.critical(
                self, "Macro import failed", f"The macro could not be imported: {exc}"
            )
            return
        macros = self.context.projects.data["macros"]
        dependencies = list(metadata.get("dependencies", []))
        existing_ids = {str(item.get("id", "")) for item in macros}
        dependency_by_name: dict[str, dict] = {}
        added_dependencies = 0
        for dependency in dependencies:
            original_name = str(dependency.get("name", "Untitled"))
            dependency_id = str(dependency.get("id", "")).strip()
            if dependency_id and dependency_id in existing_ids:
                existing = next(
                    item for item in macros if str(item.get("id", "")) == dependency_id
                )
                dependency_by_name[original_name.casefold()] = existing
                continue
            if not dependency_id:
                dependency_id = str(uuid.uuid4())
                dependency["id"] = dependency_id
            dependency["name"] = unique_macro_name(
                original_name, [existing["name"] for existing in macros]
            )
            dependency_by_name[original_name.casefold()] = dependency
            macros.append(dependency)
            existing_ids.add(dependency_id)
            added_dependencies += 1

        for bundled in [macro, *dependencies]:
            for step in bundled.get("steps", []):
                if step.get("action") != "CALL_MACRO" or step.get("macro_id"):
                    continue
                target = dependency_by_name.get(
                    str(step.get("macro_name", "")).casefold()
                )
                if target is not None:
                    step["macro_id"] = target.get("id", "")
                    step["macro_name"] = target.get("name", "")
        macro_id = str(macro.get("id", "")).strip()
        if not macro_id or macro_id in existing_ids:
            macro["id"] = str(uuid.uuid4())
        macro["name"] = unique_macro_name(
            macro["name"], [existing["name"] for existing in macros]
        )
        macro["imported_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        notices: list[str] = []
        try:
            monitors = list_monitors()
        except Exception:
            monitors = []
        monitor_index = int(macro.get("monitor_index", 0))
        if monitors and not 0 <= monitor_index < len(monitors):
            macro["monitor_index"] = 0
            notices.append(
                "Its saved monitor is not available, so Watch was changed to Entire desktop."
            )
        project_classes = {
            class_name_key(name)
            for name in self.context.projects.data.get("classes", [])
        }
        missing = [
            name
            for name in referenced_objects(macro)
            if class_name_key(name) not in project_classes
        ]
        if missing:
            notices.append(
                "These object names are not in the current project: "
                + ", ".join(missing)
                + "."
            )
        if macro.get("detection_region"):
            notices.append(
                "This macro uses a scaled detection region. Verify it against the selected Watch source with Safe Step Preview."
            )
        if has_coordinate_steps(macro):
            if has_absolute_coordinate_steps(macro):
                notices.append(
                    "This macro contains absolute screen coordinates. Test each one because screen layouts can differ."
                )
            else:
                notices.append(
                    "This macro uses portable relative coordinates. Safe-preview them against this computer before running."
                )
            exported_layout = metadata.get("screen_layout", [])
            if exported_layout and monitors and exported_layout != monitors:
                notices.append("Its exported screen layout differs from this computer.")
        macros.append(macro)
        self.save()
        self.context.macros_changed.emit()
        self.macro_combo.setCurrentIndex(self.macro_combo.count() - 1)
        self.context.log(f"Imported macro: {macro['name']}")
        message = f"Imported {macro['name']} with {len(macro['steps'])} steps."
        if added_dependencies:
            message += f" Added {added_dependencies} reusable macro(s) from the bundle."
        if notices:
            message += "\n\n" + "\n".join(f"• {notice}" for notice in notices)
        QMessageBox.information(self, "Macro imported", message)

    def selected_index(self) -> int:
        return self.table.currentRow()

    def current_watch_bounds(self, macro: dict | None = None) -> dict[str, int]:
        selected = macro or self.current_macro()
        monitor_index = int(selected.get("monitor_index", 0)) if selected else 0
        return monitor_bounds(monitor_index)

    def macro_validation_issues(self):
        macro = self.current_macro()
        if macro is None:
            return []
        classes = self.context.projects.data.get("classes", [])
        return analyze_macro(
            macro,
            classes,
            self.context.projects.data.get("macros", []),
        )

    def show_flow_view(self) -> None:
        macro = self.current_macro()
        if macro is None:
            QMessageBox.information(
                self, "Choose a macro", "Create or select a macro first."
            )
            return
        MacroFlowDialog(macro, self).exec()

    def validate_current_macro(self) -> None:
        macro = self.current_macro()
        if macro is None:
            QMessageBox.information(
                self, "Choose a macro", "Create or select a macro to validate."
            )
            return
        issues = self.macro_validation_issues()
        counts = issue_counts(issues)
        self.context.log(
            f"Validated macro {macro['name']}: {counts['error']} error(s), "
            f"{counts['warning']} warning(s)."
        )
        dialog = MacroValidationDialog(macro["name"], issues, self)
        dialog.step_requested.connect(self.select_validation_step)
        dialog.exec()

    def select_validation_step(self, row: int) -> None:
        macro = self.current_macro()
        if macro is None or not 0 <= row < len(macro.get("steps", [])):
            return
        self.table.selectRow(row)
        item = self.table.item(row, 2)
        if item is not None:
            self.table.scrollToItem(item)

    def add_step(self) -> None:
        macro = self.current_macro()
        if not macro:
            self.new_macro()
            macro = self.current_macro()
        if not macro:
            return
        classes = self.context.projects.data.get("classes", [])
        dialog = StepDialog(
            classes,
            parent=self,
            watch_bounds=self.current_watch_bounds(macro),
            macro_choices=self.context.projects.data.get("macros", []),
            current_macro_id=str(macro.get("id", "")),
        )
        if dialog.exec():
            macro["steps"].append(dialog.result_step())
            self.save()
            self.refresh_steps()

    def add_section(self) -> None:
        macro = self.current_macro()
        if not macro:
            self.new_macro()
            macro = self.current_macro()
        if not macro:
            return
        dialog = StepDialog(
            self.context.projects.data.get("classes", []),
            {
                "enabled": True,
                "action": "SECTION",
                "name": "New Section",
            },
            self,
            watch_bounds=self.current_watch_bounds(macro),
            macro_choices=self.context.projects.data.get("macros", []),
            current_macro_id=str(macro.get("id", "")),
        )
        if not dialog.exec():
            return
        selected = self.selected_index()
        insertion = selected + 1 if selected >= 0 else len(macro["steps"])
        macro["steps"] = insert_step_preserving_destinations(
            macro["steps"], insertion, dialog.result_step()
        )
        self.save()
        self.refresh_steps()
        self.table.selectRow(insertion)

    def edit_step(self, *args) -> None:
        macro = self.current_macro()
        index = self.selected_index()
        if not macro or index < 0:
            return
        dialog = StepDialog(
            self.context.projects.data.get("classes", []),
            macro["steps"][index],
            self,
            watch_bounds=self.current_watch_bounds(macro),
            macro_choices=self.context.projects.data.get("macros", []),
            current_macro_id=str(macro.get("id", "")),
        )
        if dialog.exec():
            updated_step = dialog.result_step()
            macro["steps"][index] = updated_step
            self.save()
            self.refresh_steps()
            self.table.selectRow(index)
            description = self.describe_step(updated_step)
            self.debug.setText(
                f"Saved step {index + 1}: {description or updated_step['action']}"
            )
            self.context.log(
                f"Saved macro step {index + 1}: "
                f"{description or updated_step['action']}"
            )

    def duplicate_step(self) -> None:
        macro = self.current_macro()
        index = self.selected_index()
        if macro and index >= 0:
            macro["steps"] = duplicate_step_preserving_destinations(
                macro["steps"], index
            )
            copied_name = str(macro["steps"][index + 1].get("name", "")).strip()
            if copied_name:
                macro["steps"][index + 1]["name"] = copied_name + " Copy"
            self.save()
            self.refresh_steps()
            self.table.selectRow(index + 1)

    def delete_step(self) -> None:
        macro = self.current_macro()
        index = self.selected_index()
        if not macro or index < 0:
            return
        step_number = index + 1
        references: list[int] = []
        for source_index, step in enumerate(macro["steps"]):
            targets = step_destinations(step)
            if step_number in targets:
                references.append(source_index + 1)
        message = f"Delete step {step_number}?"
        if references:
            message += (
                "\n\nIt is referenced by step(s) "
                + ", ".join(str(value) for value in references)
                + ". Those routes will be marked invalid instead of silently "
                "pointing to a different step."
            )
        if QMessageBox.question(self, "Delete macro step", message) != QMessageBox.Yes:
            return
        macro["steps"] = delete_step_preserving_destinations(
            macro["steps"], index
        )
        self.save()
        self.refresh_steps()
        if macro["steps"]:
            self.table.selectRow(min(index, len(macro["steps"]) - 1))

    def move_step(self, delta: int) -> None:
        macro = self.current_macro()
        index = self.selected_index()
        target = index + delta
        if (
            macro
            and 0 <= index < len(macro["steps"])
            and 0 <= target < len(macro["steps"])
        ):
            macro["steps"] = reorder_steps_preserving_destinations(
                macro["steps"], index, target
            )
            self.save()
            self.refresh_steps()
            self.table.selectRow(target)

    def drag_step(self, source: int, target: int) -> None:
        macro = self.current_macro()
        if not macro or source == target:
            return
        try:
            macro["steps"] = reorder_steps_preserving_destinations(
                macro["steps"], source, target
            )
        except IndexError:
            return
        self.save()
        self.refresh_steps()
        self.table.selectRow(target)
        self.debug.setText(
            f"Moved step {source + 1} to step {target + 1}. Branch destinations "
            "were updated automatically."
        )

    def save(self) -> None:
        if self.context.projects.is_open:
            self.context.projects.save()

    def time_limit_changed(self, minutes: float) -> None:
        macro = self.current_macro()
        if macro is not None:
            macro["time_limit_minutes"] = float(minutes)
            self.save()

    def monitor_changed(self) -> None:
        macro = self.current_macro()
        if macro is None:
            return
        monitor_index = int(self.monitor_combo.currentData() or 0)
        macro["monitor_index"] = monitor_index
        self.save()
        self.context.config.update({"preferred_monitor": monitor_index})
        self.refresh_runtime_options()

    def draw_detection_region(self) -> None:
        macro = self.current_macro()
        if macro is None or self.worker is not None or self.debug_worker is not None:
            return
        try:
            bounds = self.current_watch_bounds(macro)
            existing = (
                absolute_region_from_normalized(macro["detection_region"], bounds)
                if macro.get("detection_region")
                else None
            )
            picker = DetectionRegionPickerOverlay(bounds, existing, self)
            app_window = self.window()
            previous_opacity = app_window.windowOpacity()
            try:
                app_window.setWindowOpacity(0.01)
                result = picker.exec()
            finally:
                app_window.setWindowOpacity(previous_opacity)
                app_window.raise_()
                app_window.activateWindow()
            if result != QDialog.Accepted or picker.selected_region is None:
                return
            macro["detection_region"] = normalized_region_from_absolute(
                picker.selected_region, bounds
            )
            self.save()
            self.refresh_runtime_options()
            self.context.log(
                "Saved macro detection region: "
                + detection_region_label(macro["detection_region"])
                + "."
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Detection region unavailable",
                f"The detection region could not be saved: {exc}",
            )

    def clear_detection_region(self) -> None:
        macro = self.current_macro()
        if macro is None:
            return
        macro.pop("detection_region", None)
        self.save()
        self.refresh_runtime_options()
        self.context.log("Macro detection region reset to the full Watch source.")

    def overlay_toggled(self, enabled: bool) -> None:
        self.context.config.update({"macro_overlay_enabled": bool(enabled)})
        if enabled and self.worker is not None:
            self.status_overlay.show()
            self.status_overlay.raise_()
        elif not enabled:
            self.status_overlay.hide()

    def save_overlay_position(self, x: int, y: int) -> None:
        self.context.config.update({"macro_overlay_x": x, "macro_overlay_y": y})

    def model_path(self) -> str | None:
        model = preferred_model(self.context.projects)
        return str(self.context.projects.path(model["path"])) if model else None

    def run_macro(self) -> None:
        self._start_worker(None, one_loop=False)

    def run_one_loop(self) -> None:
        self._start_worker(None, one_loop=True)

    def run_single_step(self) -> None:
        self._start_worker(self.selected_index(), one_loop=False)

    def _start_worker(self, single_step: int | None, one_loop: bool) -> None:
        if self.worker is not None or self.debug_worker is not None:
            return
        macro = self.current_macro()
        path = self.model_path()
        if not macro or not macro.get("steps"):
            QMessageBox.information(
                self, "Build a macro", "Add at least one step first."
            )
            return
        if single_step is not None and not 0 <= single_step < len(macro["steps"]):
            QMessageBox.information(
                self, "Select a step", "Select a macro step in the table first."
            )
            return
        if single_step is None:
            issues = self.macro_validation_issues()
            if issue_counts(issues)["error"]:
                self.context.log(
                    f"Macro start blocked because {macro['name']} has validation errors."
                )
                dialog = MacroValidationDialog(macro["name"], issues, self)
                dialog.step_requested.connect(self.select_validation_step)
                dialog.exec()
                return
        active_steps = (
            [macro["steps"][single_step]]
            if single_step is not None
            else [
                step
                for step in macro.get("steps", [])
                if step.get("enabled", True)
            ]
        )
        needs_detection = any(step_needs_detection(step) for step in active_steps)
        if not needs_detection and any(
            step.get("action") == "CALL_MACRO" for step in active_steps
        ):
            # The worker recursively checks only the called dependency chain.
            macro_library = self.context.projects.data.get("macros", [])
            probe = MacroWorker(
                deepcopy(macro),
                path,
                macro_library=deepcopy(macro_library),
            )
            if single_step is not None:
                called = find_macro_reference(active_steps[0], macro_library)
                needs_detection = bool(
                    called and probe._macro_needs_detection(called)
                )
            else:
                needs_detection = probe._macro_needs_detection(macro)
        if needs_detection and not path:
            QMessageBox.information(
                self,
                "Accept a model",
                "Train and accept a model before running object macros.",
            )
            return
        self.thread = QThread(self)
        time_limit_seconds = max(
            0.0, float(macro.get("time_limit_minutes", 0)) * 60
        )
        monitor_index = int(macro.get("monitor_index", 0))
        self.worker = MacroWorker(
            macro=deepcopy(macro),
            model_path=path,
            single_step=single_step,
            time_limit_seconds=time_limit_seconds,
            monitor_index=monitor_index,
            one_loop=one_loop,
            detection_region=deepcopy(macro.get("detection_region")),
            macro_library=deepcopy(
                self.context.projects.data.get("macros", [])
            ),
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.context.log)
        self.worker.current_step.connect(self.on_current_step)
        self.worker.detection_state.connect(self.on_detection)
        self.worker.observation_state.connect(self.on_observation)
        self.worker.decision_state.connect(self.on_decision)
        self.worker.time_limit_reached.connect(self.on_time_limit_reached)
        self.worker.failed.connect(self.on_failed)
        for signal in (self.worker.completed, self.worker.stopped, self.worker.failed):
            signal.connect(self.thread.quit)
        self.thread.finished.connect(self._worker_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.last_decision = ""
        self._set_execution_controls(False)
        self.status_overlay.begin(macro.get("name", "Untitled"))
        self.status_overlay.move(
            int(self.context.config.get("macro_overlay_x", 24)),
            int(self.context.config.get("macro_overlay_y", 24)),
        )
        if self.overlay_check.isChecked():
            self.status_overlay.show()
            self.status_overlay.raise_()
        self.thread.start()

    def test_selected_step(self) -> None:
        if self.worker is not None or self.debug_worker is not None:
            return
        macro = self.current_macro()
        index = self.selected_index()
        if not macro or not macro.get("steps"):
            QMessageBox.information(
                self, "Build a macro", "Create a macro with at least one step first."
            )
            return
        if not 0 <= index < len(macro["steps"]):
            QMessageBox.information(
                self, "Select a step", "Select a macro step in the table first."
            )
            return
        step = deepcopy(macro["steps"][index])
        path = self.model_path()
        if step_needs_detection(step) and not path:
            QMessageBox.information(
                self,
                "Accept a model",
                "This step uses object detection. Train and accept a model before previewing it.",
            )
            return
        self.pending_debug_report = None
        self.debug_thread = QThread(self)
        self.debug_worker = StepDebugWorker(
            step,
            index,
            len(macro["steps"]),
            path,
            int(macro.get("monitor_index", 0)),
            deepcopy(macro.get("detection_region")),
            3.0 if step_needs_screen_preview(step) else 0.0,
        )
        self.debug_worker.moveToThread(self.debug_thread)
        self.debug_thread.started.connect(self.debug_worker.run)
        self.debug_worker.completed.connect(self.on_debug_ready)
        self.debug_worker.failed.connect(self.on_debug_failed)
        self.debug_worker.completed.connect(self.debug_thread.quit)
        self.debug_worker.failed.connect(self.debug_thread.quit)
        self.debug_thread.finished.connect(self._debug_finished)
        self.debug_thread.finished.connect(self.debug_thread.deleteLater)
        self._set_execution_controls(False)
        self.debug.setText(
            f"Safely inspecting step {index + 1}… No mouse or keyboard input will be sent."
        )
        self.context.log(f"Safe preview started for macro step {index + 1}.")
        if step_needs_screen_preview(step):
            app_window = self.window()
            self.debug_minimized_window = True
            self.debug_window_was_maximized = app_window.isMaximized()
            app_window.showMinimized()
        self.debug_thread.start()

    def on_debug_ready(self, report: dict) -> None:
        self.pending_debug_report = report
        message = str(report.get("decision", "Preview completed."))
        self.last_decision = message
        self.debug.setText(
            f"Safe preview · step {report.get('step_number')}\n{message}"
        )
        self.context.log(
            f"Safe preview step {report.get('step_number')}: {message}"
        )

    def on_debug_failed(self, message: str) -> None:
        self.last_decision = f"Safe preview failed: {message}"
        self.debug.setText(self.last_decision)
        self.context.log(self.last_decision)
        QMessageBox.critical(self, "Safe preview failed", message)

    def _debug_finished(self) -> None:
        report = self.pending_debug_report
        self.debug_worker = None
        self.debug_thread = None
        self.pending_debug_report = None
        self._set_execution_controls(True)
        if self.debug_minimized_window:
            app_window = self.window()
            if self.debug_window_was_maximized:
                app_window.showMaximized()
            else:
                app_window.showNormal()
            app_window.raise_()
            app_window.activateWindow()
        self.debug_minimized_window = False
        self.debug_window_was_maximized = False
        if report is not None:
            MacroDebugDialog(report, self).exec()

    def on_current_step(self, index: int, step: dict) -> None:
        action = step.get("action", "").replace("_", " ")
        name = str(step.get("name", "")).strip()
        label = f"{name} · {action}" if name else action
        runtime_macro = str(step.get("_runtime_macro_name", "")).strip()
        prefix = (
            f"{runtime_macro} · "
            if int(step.get("_runtime_depth", 0)) > 0
            else ""
        )
        self.debug.setText(
            f"Current {prefix}step {index + 1}: {label}\nNext action is shown above. "
            "Elapsed execution is in the log."
        )
        self.status_overlay.set_step(index, step)

    def on_detection(self, name: str, found: bool, confidence: float) -> None:
        self.debug.setText(
            f"Looking for: {name}\nDetected: {'YES' if found else 'NO'}\nConfidence: {confidence:.0%}"
        )
        self.status_overlay.set_detection(name, found, confidence)

    def on_decision(self, message: str) -> None:
        self.last_decision = message
        self.debug.setText(f"Latest decision\n{message}")

    def on_observation(
        self,
        name: str,
        confidence: float,
        targets: str,
        minimum_confidence: float,
        is_target: bool,
    ) -> None:
        if is_target:
            self.debug.setText(
                f"Waiting for: {targets}\nSeen: {name} at {confidence:.0%}\n"
                f"Needs at least: {minimum_confidence:.0%}"
            )
        else:
            self.debug.setText(
                f"Waiting for: {targets}\nDifferent object seen: {name} at {confidence:.0%}"
            )
        self.status_overlay.set_observation(
            name, confidence, targets, minimum_confidence, is_target
        )

    def on_time_limit_reached(self, seconds: float) -> None:
        minutes = seconds / 60
        self.last_decision = f"Time limit reached after {minutes:g} minute(s)."
        self.debug.setText(self.last_decision)
        self.status_overlay.set_stopping("Time limit reached · stopping")

    def on_failed(self, message: str) -> None:
        self.last_decision = f"FAILED — {message}"
        self.debug.setText(self.last_decision)
        self.context.log(f"Macro failed: {message}")
        QMessageBox.critical(self, "Macro failed", message)

    def emergency_stop(self) -> None:
        if self.worker:
            self.last_decision = "Emergency stop requested."
            self.status_overlay.set_stopping("Emergency stop requested")
            self.worker.request_stop()
        else:
            self.status_overlay.hide()
        self.stop_recording()
        self.context.log(
            "Emergency stop requested; releasing keyboard and mouse inputs."
        )

    def _worker_finished(self) -> None:
        self.worker = None
        self.thread = None
        self._set_execution_controls(True)
        if self.last_decision:
            self.debug.setText(f"Last decision\n{self.last_decision}")
        else:
            self.debug.setText("Debug: idle")
        self.status_overlay.hide()

    def _set_execution_controls(self, enabled: bool) -> None:
        has_macro = self.current_macro() is not None
        active = bool(enabled and has_macro)
        for button in (
            self.run_button,
            self.loop_button,
            self.single_button,
            self.test_button,
            self.record_button,
            self.draw_region_button,
            self.validate_button,
        ):
            button.setEnabled(active)
        self.clear_region_button.setEnabled(
            active and bool((self.current_macro() or {}).get("detection_region"))
        )
        self.time_limit.setEnabled(active)
        self.monitor_combo.setEnabled(active)
        for button in self.edit_buttons:
            button.setEnabled(active)
        self.table.setDragEnabled(active)

    def start_recording(self) -> None:
        if self.recorder.active:
            return
        self.recorder.start()
        self.record_button.setEnabled(False)
        self.stop_record_button.setEnabled(True)
        self.context.log("Traditional macro recording started.")

    def stop_recording(self) -> None:
        if not self.recorder.active:
            return
        steps = self.recorder.stop()
        stop_key = str(self.context.config.get("stop_recording_hotkey", "<f7>"))
        stop_key = stop_key.strip("<>").lower()
        if (
            steps
            and steps[-1].get("action") == "PRESS_KEY"
            and str(steps[-1].get("value", "")).lower() == stop_key
        ):
            steps.pop()
            if steps and steps[-1].get("action") == "WAIT":
                steps.pop()
        self.record_button.setEnabled(True)
        self.stop_record_button.setEnabled(False)
        macro = self.current_macro()
        if macro and steps:
            macro["steps"].extend(steps)
            self.save()
            self.refresh_steps()
        self.context.log(
            f"Macro recording stopped; {len(steps)} recorded step(s) added."
        )
