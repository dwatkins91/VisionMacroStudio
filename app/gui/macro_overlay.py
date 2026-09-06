from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class MacroStatusOverlay(QWidget):
    """Small always-on-top, two-line macro status window."""

    position_changed = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
        self.setCursor(Qt.SizeAllCursor)
        self._drag_offset: QPoint | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("MacroOverlayPanel")
        panel.setStyleSheet(
            """
            QFrame#MacroOverlayPanel {
                background-color: rgba(7, 14, 26, 232);
                border: 1px solid rgba(85, 221, 177, 185);
                border-radius: 6px;
            }
            QLabel { background: transparent; padding: 0; }
            """
        )
        lines = QVBoxLayout(panel)
        lines.setContentsMargins(7, 4, 7, 4)
        lines.setSpacing(1)
        self.step_line = QLabel("Macro starting…")
        self.step_line.setStyleSheet(
            "color: #f1f5fb; font: 600 9pt 'Segoe UI';"
        )
        self.detection_line = QLabel("No detection yet")
        self.detection_line.setStyleSheet(
            "color: #9eabc0; font: 8pt 'Segoe UI';"
        )
        for label in (self.step_line, self.detection_line):
            label.setMaximumWidth(360)
            label.setTextInteractionFlags(Qt.NoTextInteraction)
            lines.addWidget(label)
        outer.addWidget(panel)
        self.adjustSize()
        self.hide()

    def begin(self, macro_name: str) -> None:
        self.step_line.setText(f"Starting · {macro_name}")
        self.detection_line.setText("No detection yet")
        self.detection_line.setStyleSheet(
            "color: #9eabc0; font: 8pt 'Segoe UI';"
        )
        self.adjustSize()

    def set_step(self, index: int, step: dict) -> None:
        action = str(step.get("action", "")).replace("_", " ").title()
        self.step_line.setText(f"Step {index + 1} · {action}")
        self.adjustSize()

    def set_detection(self, name: str, found: bool, confidence: float) -> None:
        if found:
            self.detection_line.setText(f"Found · {name} · {confidence:.0%}")
            color = "#55ddb1"
        else:
            self.detection_line.setText(f"Searching · {name} · no match")
            color = "#ffcb6b"
        self.detection_line.setStyleSheet(
            f"color: {color}; font: 8pt 'Segoe UI';"
        )
        self.adjustSize()

    def set_observation(
        self,
        name: str,
        confidence: float,
        targets: str,
        minimum_confidence: float,
        is_target: bool,
    ) -> None:
        if is_target:
            self.detection_line.setText(
                f"Low · {name} · {confidence:.0%} < {minimum_confidence:.0%}"
            )
            color = "#ffcb6b"
        else:
            self.detection_line.setText(
                f"Seen · {name} · {confidence:.0%} · waiting for {targets}"
            )
            color = "#84b8ff"
        self.detection_line.setStyleSheet(
            f"color: {color}; font: 8pt 'Segoe UI';"
        )
        self.adjustSize()

    def set_stopping(self, reason: str) -> None:
        self.step_line.setText(reason)
        self.adjustSize()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.position_changed.emit(self.x(), self.y())
            event.accept()
            return
        super().mouseReleaseEvent(event)
