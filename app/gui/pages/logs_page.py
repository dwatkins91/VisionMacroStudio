from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.gui.widgets import page_header
from app.core.diagnostics import create_diagnostic_package
from app.core.system_check import run_system_checks


class LogsPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Logs",
                "See exactly what capture, training, detection, and macro actions did.",
            )
        )
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        buttons = QHBoxLayout()
        save = QPushButton("Save Log")
        save.clicked.connect(self.save_log)
        clear = QPushButton("Clear View")
        clear.clicked.connect(self.text.clear)
        diagnostic = QPushButton("Create Diagnostic Package")
        diagnostic.clicked.connect(self.create_diagnostic_package)
        buttons.addWidget(save)
        buttons.addWidget(clear)
        buttons.addWidget(diagnostic)
        buttons.addStretch()
        layout.addLayout(buttons)
        context.log_message.connect(self.append)

    def append(self, message: str) -> None:
        self.text.appendPlainText(f"{datetime.now().strftime('%H:%M:%S')} - {message}")

    def save_log(self) -> None:
        default = "vision_macro_log.txt"
        if self.context.projects.is_open:
            default = str(
                self.context.projects.path("logs")
                / f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", default, "Text files (*.txt)"
        )
        if path:
            Path(path).write_text(self.text.toPlainText(), encoding="utf-8")

    def create_diagnostic_package(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Create Diagnostic Package",
            f"VisionMacroStudio-Diagnostics-{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "ZIP archives (*.zip)",
        )
        if not path:
            return
        try:
            checks = self.context.system_checks or run_system_checks(
                self.context.config.get("project_directory"),
                deep=False,
                include_display=False,
            )
            result = create_diagnostic_package(
                Path(path),
                config=self.context.config.data,
                project=self.context.projects,
                log_text=self.text.toPlainText(),
                checks=checks,
            )
            self.context.log(f"Created privacy-safe diagnostic package: {result.name}")
            QMessageBox.information(
                self,
                "Diagnostic package created",
                "The ZIP excludes captures, model files, project paths, and settings paths. "
                "Typed text and window titles are redacted. Review the ZIP before attaching "
                "it to a public GitHub issue.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Diagnostic package failed", str(exc))
