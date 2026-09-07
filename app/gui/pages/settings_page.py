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
    QLabel,
)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app.core.context import AppContext
from app.gui.widgets import page_header
from app.core.config import application_data_dir
from app.gui.system_check_dialog import SystemCheckDialog


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
        support = QHBoxLayout()
        check = QPushButton("Check My Computer")
        check.clicked.connect(self.check_computer)
        app_data = QPushButton("Open App Settings Folder")
        app_data.clicked.connect(self.open_app_data)
        support.addWidget(check)
        support.addWidget(app_data)
        support.addStretch()
        layout.addLayout(support)
        privacy = QLabel(
            "Local storage: general settings are kept in the app settings folder. "
            "Captures, datasets, model weights, macros, and logs stay in each project folder. "
            "Use Logs > Create Diagnostic Package for a scrubbed support bundle."
        )
        privacy.setObjectName("Subtitle")
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
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

    def check_computer(self) -> None:
        dialog = SystemCheckDialog(self.context, self)
        dialog.run_checks()
        dialog.exec()

    def open_app_data(self) -> None:
        path = application_data_dir()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
