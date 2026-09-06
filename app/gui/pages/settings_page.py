from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.gui.widgets import page_header


class SettingsPage(QWidget):
    HOTKEY_FIELDS = (
        ("Capture hotkey", "capture_hotkey"),
        ("Start recording hotkey", "start_recording_hotkey"),
        ("Stop recording hotkey", "stop_recording_hotkey"),
        ("Run macro hotkey", "run_macro_hotkey"),
        ("Emergency stop hotkey", "emergency_stop_hotkey"),
    )

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.fields = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Settings",
                "Hotkeys use pynput notation such as <f8>, <ctrl>+<shift>+c, or <f12>.",
            )
        )
        form = QFormLayout()
        for label, key in self.HOTKEY_FIELDS:
            field = QLineEdit(str(context.config.get(key)))
            self.fields[key] = field
            form.addRow(label, field)
        self.split = QSpinBox()
        self.split.setRange(50, 95)
        self.split.setSuffix("% train")
        self.split.setValue(int(context.config.get("train_split", 80)))
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.1, 0.99)
        self.confidence.setSingleStep(0.05)
        self.confidence.setValue(float(context.config.get("confidence", 0.7)))
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(int(context.config.get("detection_fps", 5)))
        self.device = QComboBox()
        self.device.addItems(["auto", "cpu", "gpu"])
        self.device.setCurrentText(context.config.get("device", "auto"))
        self.project_dir = QLineEdit(context.config.get("project_directory"))
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_projects)
        project_row = QHBoxLayout()
        project_row.addWidget(self.project_dir)
        project_row.addWidget(browse)
        form.addRow("Default dataset split", self.split)
        form.addRow("Default confidence", self.confidence)
        form.addRow("Detection FPS", self.fps)
        form.addRow("Preferred device", self.device)
        form.addRow("Project directory", project_row)
        layout.addLayout(form)
        save = QPushButton("Save Settings")
        save.setObjectName("Primary")
        save.clicked.connect(self.save)
        layout.addWidget(save)
        layout.addStretch()

    def browse_projects(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Project Directory", self.project_dir.text()
        )
        if folder:
            self.project_dir.setText(folder)

    def save(self) -> None:
        values = {key: field.text().strip() for key, field in self.fields.items()}
        values.update(
            {
                "train_split": self.split.value(),
                "confidence": self.confidence.value(),
                "detection_fps": self.fps.value(),
                "device": self.device.currentText(),
                "project_directory": self.project_dir.text().strip(),
            }
        )
        self.context.config.update(values)
        self.context.settings_changed.emit()
        self.context.log("Settings saved and global hotkeys reloaded.")
