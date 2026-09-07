from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from app.gui.widgets import array_to_pixmap


class MacroDebugDialog(QDialog):
    """Read-only result of a safe, single-frame macro-step inspection."""

    def __init__(self, report: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Debug Step {report['step_number']}")
        self.resize(940, 720)
        layout = QVBoxLayout(self)

        safe = QLabel("SAFE PREVIEW · No mouse or keyboard input was sent")
        safe.setStyleSheet(
            "color:#55ddb1; font-weight:700; padding:8px; "
            "background:#102a29; border:1px solid #2d8f75; border-radius:6px;"
        )
        layout.addWidget(safe)

        title = QLabel(
            f"Step {report['step_number']} · {report.get('action_label', 'Unknown')}"
        )
        title.setStyleSheet("font-size:16pt; font-weight:700;")
        layout.addWidget(title)

        decision = QLabel(str(report.get("decision", "No decision available.")))
        decision.setWordWrap(True)
        decision.setTextInteractionFlags(Qt.TextSelectableByMouse)
        decision.setStyleSheet(
            "font-size:11pt; padding:10px; background:#111c2f; "
            "border:1px solid #344a6b; border-radius:6px;"
        )
        layout.addWidget(decision)

        details = list(report.get("details", []))
        if details:
            detail_label = QLabel("\n".join(f"• {line}" for line in details))
            detail_label.setWordWrap(True)
            detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            detail_label.setStyleSheet("color:#b7c5da; padding:4px;")
            layout.addWidget(detail_label)

        preview = report.get("preview")
        if preview is not None:
            preview_label = QLabel()
            preview_label.setAlignment(Qt.AlignCenter)
            preview_label.setMinimumSize(720, 400)
            preview_label.setStyleSheet(
                "background:#060b14; border:1px solid #263650; border-radius:8px;"
            )
            pixmap = array_to_pixmap(preview).scaled(
                880, 470, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            preview_label.setPixmap(pixmap)
            layout.addWidget(preview_label, 1)
        else:
            no_preview = QLabel(
                "This step does not inspect the screen. Its configured effect is shown above."
            )
            no_preview.setAlignment(Qt.AlignCenter)
            no_preview.setStyleSheet(
                "color:#8494ad; padding:28px; background:#0a1322; "
                "border:1px solid #263650; border-radius:8px;"
            )
            layout.addWidget(no_preview, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
