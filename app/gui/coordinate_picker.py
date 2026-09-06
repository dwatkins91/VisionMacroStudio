from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog


class CoordinatePickerOverlay(QDialog):
    """Full-desktop overlay for safely selecting a macro screen coordinate."""

    def __init__(
        self,
        mode: str = "click",
        countdown_seconds: int = 3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode if mode in {"click", "hover"} else "click"
        self.remaining = max(1, int(countdown_seconds))
        self.selected_coordinate: tuple[int, int] | None = None
        self._finished = False
        self._mouse_controller = None
        try:
            from pynput.mouse import Controller

            self._mouse_controller = Controller()
        except Exception:
            pass
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._countdown_tick)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setGeometry(self._virtual_geometry())

    @staticmethod
    def _virtual_geometry() -> QRect:
        screens = QApplication.screens()
        if not screens:
            return QRect(0, 0, 1920, 1080)
        geometry = QRect(screens[0].geometry())
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        return geometry

    def _cursor_position(self) -> QPoint:
        try:
            x, y = self._mouse_controller.position
            return QPoint(round(x), round(y))
        except Exception:
            return QCursor.pos()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus()
        if self.mode == "hover":
            self._timer.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(3, 8, 18, 92))
        global_position = self._cursor_position()
        position = self.mapFromGlobal(global_position)
        painter.setPen(QPen(QColor("#55ddb1"), 1))
        painter.drawLine(0, position.y(), self.width(), position.y())
        painter.drawLine(position.x(), 0, position.x(), self.height())
        painter.setPen(QPen(QColor("#5ecbff"), 2))
        painter.drawEllipse(position, 7, 7)

        instruction = (
            "Click the desired position · Escape cancels"
            if self.mode == "click"
            else f"Hover over the desired position · Capturing in {self.remaining}s · Escape cancels"
        )
        detail = f"X {global_position.x()}    Y {global_position.y()}"
        panel = QRect(18, 18, 620, 72)
        painter.fillRect(panel, QColor(8, 17, 31, 225))
        painter.setPen(QColor("white"))
        painter.drawText(34, 47, instruction)
        painter.setPen(QColor("#55ddb1"))
        painter.drawText(34, 73, detail)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.mode == "click" and event.button() == Qt.LeftButton:
            self._select_current_position()
        elif event.button() == Qt.RightButton:
            self._cancel()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(event)

    def _countdown_tick(self) -> None:
        self.remaining -= 1
        if self.remaining <= 0:
            self._select_current_position()
        else:
            self.update()

    def _select_current_position(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._timer.stop()
        position = self._cursor_position()
        self.selected_coordinate = (position.x(), position.y())
        self.accept()

    def _cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._timer.stop()
        self.reject()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        if not self._finished:
            self._finished = True
        super().closeEvent(event)
