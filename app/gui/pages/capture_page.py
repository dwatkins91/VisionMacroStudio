from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.capture.grabber import grab_screen
from app.capture.overlay import CaptureOverlay
from app.core.context import AppContext
from app.gui.widgets import page_header


class CapturePage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.overlay = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Capture",
                "Freeze the screen, draw one or more boxes, name the objects, then press Enter to save.",
            )
        )
        self.instructions = QLabel()
        self.instructions.setWordWrap(True)
        self.instructions.setStyleSheet(
            "font-size: 13pt; padding:22px; background:#111c2f; border-radius:8px;"
        )
        layout.addWidget(self.instructions)
        button = QPushButton("CAPTURE OBJECT NOW")
        button.setObjectName("Primary")
        button.clicked.connect(self.request_capture)
        layout.addWidget(button, alignment=Qt.AlignLeft)
        note = QLabel(
            "Tip: capture the same object in different locations, sizes, backgrounds, and visual states. The full screenshot—not only the crop—is saved for proper object-detection training."
        )
        note.setWordWrap(True)
        note.setObjectName("Subtitle")
        layout.addWidget(note)
        layout.addStretch()
        context.project_changed.connect(self.refresh)
        context.dataset_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        if self.context.projects.is_open:
            data = self.context.projects.data
            hotkey = self.context.config.get("capture_hotkey", "<f8>")
            self.instructions.setText(
                f"Project: <b>{data['name']}</b><br>Capture hotkey: <b>{hotkey}</b><br>"
                f"Saved screenshots: <b>{len(data['screenshots'])}</b> · Classes: <b>{len(data['classes'])}</b>"
            )
        else:
            self.instructions.setText("Create or open a project before capturing.")

    def request_capture(self) -> None:
        if not self.context.projects.is_open:
            QMessageBox.information(
                self, "Open a project", "Create or open a project first."
            )
            return
        if self.overlay is not None:
            return
        self.window().hide()
        QTimer.singleShot(250, self._begin_capture)

    def _begin_capture(self) -> None:
        try:
            grab = grab_screen(0)
            classes = list(self.context.projects.data["classes"])
            self.overlay = CaptureOverlay(grab, classes)
            self.overlay.capture_completed.connect(self._save_capture)
            self.overlay.capture_cancelled.connect(self._cancel_capture)
            self.overlay.show()
        except Exception as exc:
            self.window().show()
            self.overlay = None
            QMessageBox.critical(self, "Capture failed", str(exc))

    def _save_capture(self, image, annotations, origin) -> None:
        try:
            self.context.projects.add_screenshot(image, annotations, origin)
            labels = ", ".join(a["class_name"] for a in annotations)
            self.context.log(f"Saved capture with {len(annotations)} box(es): {labels}")
            self.context.dataset_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Could not save capture", str(exc))
        finally:
            self.overlay = None
            self.window().show()
            self.window().raise_()

    def _cancel_capture(self) -> None:
        self.overlay = None
        self.window().show()
        self.context.log("Capture cancelled.")
