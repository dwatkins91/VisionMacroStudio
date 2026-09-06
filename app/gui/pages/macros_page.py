from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from app.automation.engine import MacroWorker
from app.automation.control import destination_steps, object_names
from app.automation.macro_io import (
    MacroFormatError,
    export_macro_file,
    has_coordinate_steps,
    import_macro_file,
    referenced_objects,
    unique_macro_name,
)
from app.automation.recorder import MacroRecorder
from app.capture.grabber import list_monitors
from app.core.context import AppContext
from app.gui.macro_overlay import MacroStatusOverlay
from app.gui.step_dialog import StepDialog
from app.gui.widgets import page_header
from app.vision.detector import class_name_key
from app.vision.model_manager import preferred_model


class MacrosPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.thread = None
        self.worker = None
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
                "Build resilient automation from detected objects. Coordinate recording is available, but object actions are preferred.",
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
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["On", "#", "Action", "Details"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.edit_step)
        self.table.itemChanged.connect(self._enabled_changed)
        layout.addWidget(self.table, 1)
        edit_bar = QHBoxLayout()
        for text, callback in (
            ("Add Step", self.add_step),
            ("Edit", self.edit_step),
            ("Duplicate", self.duplicate_step),
            ("Delete Step", self.delete_step),
            ("Move Up", lambda: self.move_step(-1)),
            ("Move Down", lambda: self.move_step(1)),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            edit_bar.addWidget(button)
        edit_bar.addStretch()
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
        run_bar = QHBoxLayout()
        self.run_button = QPushButton("RUN MACRO")
        self.run_button.setObjectName("Primary")
        self.run_button.clicked.connect(self.run_macro)
        single = QPushButton("Run Selected Step")
        single.clicked.connect(self.run_single_step)
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self.start_recording)
        self.stop_record_button = QPushButton("Stop Recording")
        self.stop_record_button.clicked.connect(self.stop_recording)
        self.stop_record_button.setEnabled(False)
        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.clicked.connect(self.emergency_stop)
        run_bar.addWidget(self.run_button)
        run_bar.addWidget(single)
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
        self.monitor_combo.setEnabled(macro is not None and self.worker is None)
        self.monitor_combo.blockSignals(False)
        model = preferred_model(self.context.projects)
        model_name = str(model.get("name", "none")) if model else "none"
        self.model_status.setText(f"Model: {model_name}")
        self.model_status.setToolTip(
            f"Macros use the accepted model: {model_name}"
            if model
            else "Accept a model before running detection steps."
        )

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
            return
        for index, step in enumerate(macro.get("steps", [])):
            row = self.table.rowCount()
            self.table.insertRow(row)
            enabled = QTableWidgetItem()
            enabled.setFlags(enabled.flags() | Qt.ItemIsUserCheckable)
            enabled.setCheckState(
                Qt.Checked if step.get("enabled", True) else Qt.Unchecked
            )
            enabled.setData(Qt.UserRole, index)
            self.table.setItem(row, 0, enabled)
            self.table.setItem(row, 1, QTableWidgetItem(str(index + 1)))
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(step.get("action", "").replace("_", " ").title()),
            )
            self.table.setItem(row, 3, QTableWidgetItem(self.describe_step(step)))

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

        action = step.get("action")
        if action == "CLICK_FIRST_AVAILABLE":
            names = object_names(step.get("objects", []))
            return (
                f"{' → '.join(names)} · ≥{float(step.get('confidence', 0.7)):.0%}"
                f" · timeout {seconds_range('timeout', 'timeout_max', 30)}"
            )
        if action == "WAIT_FOR_ANY_OBJECT":
            names = object_names(step.get("objects", []))
            targets = destination_steps(step.get("target_steps", []))
            routes = [
                f"{name}→{'next' if target == 0 else target}"
                for name, target in zip(names, targets)
            ]
            return (
                f"{', '.join(routes)} · ≥{float(step.get('confidence', 0.7)):.0%}"
                f" · timeout {seconds_range('timeout', 'timeout_max', 30)}"
            )
        if "OBJECT" in str(action) or "DISAPPEARS" in str(action):
            return (
                f"{step.get('object')} · ≥{float(step.get('confidence', 0.7)):.0%}"
                f" · timeout {seconds_range('timeout', 'timeout_max', 30)}"
            )
        if action in ("PRESS_KEY", "TYPE_TEXT"):
            return str(step.get("value", ""))
        if action == "WAIT":
            return seconds_range("duration", "duration_max", 1)
        if action == "MOVE_MOUSE":
            return f"({step.get('x')}, {step.get('y')})"
        if action in ("CLICK", "DOUBLE_CLICK", "RIGHT_CLICK"):
            return (
                f"({step.get('x')}, {step.get('y')}) "
                f"±{step.get('random_offset', 0)} px"
            )
        if action == "REPEAT":
            return f"repeat {step.get('count', 1)} time(s), return to step {step.get('target_step', 1)}"
        if action == "GOTO_STEP":
            return f"go to step {step.get('target_step', 1)}"
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
            macro["name"] = name.strip()
            self.save()
            self.context.macros_changed.emit()

    def delete_macro(self) -> None:
        macro = self.current_macro()
        if (
            macro
            and QMessageBox.question(self, "Delete Macro", f"Delete {macro['name']}?")
            == QMessageBox.Yes
        ):
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
        if has_coordinate_steps(macro):
            notices.append(
                "This macro contains screen coordinates. Test each coordinate step because screen layouts can differ."
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
        if notices:
            message += "\n\n" + "\n".join(f"• {notice}" for notice in notices)
        QMessageBox.information(self, "Macro imported", message)

    def selected_index(self) -> int:
        return self.table.currentRow()

    def add_step(self) -> None:
        macro = self.current_macro()
        if not macro:
            self.new_macro()
            macro = self.current_macro()
        if not macro:
            return
        classes = self.context.projects.data.get("classes", [])
        dialog = StepDialog(classes, parent=self)
        if dialog.exec():
            macro["steps"].append(dialog.result_step())
            self.save()
            self.refresh_steps()

    def edit_step(self, *args) -> None:
        macro = self.current_macro()
        index = self.selected_index()
        if not macro or index < 0:
            return
        dialog = StepDialog(
            self.context.projects.data.get("classes", []), macro["steps"][index], self
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
            macro["steps"].insert(index + 1, deepcopy(macro["steps"][index]))
            self.save()
            self.refresh_steps()
            self.table.selectRow(index + 1)

    def delete_step(self) -> None:
        macro = self.current_macro()
        index = self.selected_index()
        if macro and index >= 0:
            macro["steps"].pop(index)
            self.save()
            self.refresh_steps()

    def move_step(self, delta: int) -> None:
        macro = self.current_macro()
        index = self.selected_index()
        target = index + delta
        if (
            macro
            and 0 <= index < len(macro["steps"])
            and 0 <= target < len(macro["steps"])
        ):
            macro["steps"][index], macro["steps"][target] = (
                macro["steps"][target],
                macro["steps"][index],
            )
            self.save()
            self.refresh_steps()
            self.table.selectRow(target)

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
        self._start_worker(None)

    def run_single_step(self) -> None:
        self._start_worker(self.selected_index())

    def _start_worker(self, single_step: int | None) -> None:
        if self.worker is not None:
            return
        macro = self.current_macro()
        path = self.model_path()
        if not macro or not macro.get("steps"):
            QMessageBox.information(
                self, "Build a macro", "Add at least one step first."
            )
            return
        needs_detection = any(
            step.get("enabled", True)
            and step.get("action")
            in (
                "WAIT_FOR_OBJECT",
                "WAIT_FOR_ANY_OBJECT",
                "WAIT_UNTIL_DISAPPEARS",
                "CLICK_OBJECT",
                "RIGHT_CLICK_OBJECT",
                "CLICK_FIRST_AVAILABLE",
            )
            for step in macro.get("steps", [])
        )
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
            deepcopy(macro),
            path,
            single_step,
            time_limit_seconds,
            monitor_index,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.context.log)
        self.worker.current_step.connect(self.on_current_step)
        self.worker.detection_state.connect(self.on_detection)
        self.worker.observation_state.connect(self.on_observation)
        self.worker.time_limit_reached.connect(self.on_time_limit_reached)
        self.worker.failed.connect(self.on_failed)
        for signal in (self.worker.completed, self.worker.stopped, self.worker.failed):
            signal.connect(self.thread.quit)
        self.thread.finished.connect(self._worker_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.run_button.setEnabled(False)
        self.time_limit.setEnabled(False)
        self.status_overlay.begin(macro.get("name", "Untitled"))
        self.status_overlay.move(
            int(self.context.config.get("macro_overlay_x", 24)),
            int(self.context.config.get("macro_overlay_y", 24)),
        )
        if self.overlay_check.isChecked():
            self.status_overlay.show()
            self.status_overlay.raise_()
        self.thread.start()

    def on_current_step(self, index: int, step: dict) -> None:
        self.debug.setText(
            f"Current step {index + 1}: {step.get('action', '').replace('_', ' ')}\nNext action is shown above. Elapsed execution is in the log."
        )
        self.status_overlay.set_step(index, step)

    def on_detection(self, name: str, found: bool, confidence: float) -> None:
        self.debug.setText(
            f"Looking for: {name}\nDetected: {'YES' if found else 'NO'}\nConfidence: {confidence:.0%}"
        )
        self.status_overlay.set_detection(name, found, confidence)

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
        self.debug.setText(f"Time limit reached after {minutes:g} minute(s).")
        self.status_overlay.set_stopping("Time limit reached · stopping")

    def on_failed(self, message: str) -> None:
        self.context.log(f"Macro failed: {message}")
        QMessageBox.critical(self, "Macro failed", message)

    def emergency_stop(self) -> None:
        if self.worker:
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
        self.run_button.setEnabled(True)
        self.time_limit.setEnabled(self.current_macro() is not None)
        self.monitor_combo.setEnabled(self.current_macro() is not None)
        self.debug.setText("Debug: idle")
        self.status_overlay.hide()

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
