from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.gui.widgets import page_header


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
        buttons.addWidget(save)
        buttons.addWidget(clear)
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
            from pathlib import Path

            Path(path).write_text(self.text.toPlainText(), encoding="utf-8")
