from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QCursor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QDialog


class DetectionRegionPickerOverlay(QDialog):
    """Overlay for drawing the part of a Watch source used by macro inference."""

    def __init__(
        self,
        watch_bounds: dict[str, int],
        initial_region: dict[str, int] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.watch_bounds = dict(watch_bounds)
        self.selected_region: dict[str, int] | None = None
        self._start: QPoint | None = None
        self._current: QPoint | None = None
        if initial_region:
            self._start = QPoint(
                int(initial_region["left"]) - int(watch_bounds["left"]),
                int(initial_region["top"]) - int(watch_bounds["top"]),
            )
            self._current = QPoint(
                self._start.x() + int(initial_region["width"]),
                self._start.y() + int(initial_region["height"]),
            )
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setGeometry(
            int(watch_bounds["left"]),
            int(watch_bounds["top"]),
            int(watch_bounds["width"]),
            int(watch_bounds["height"]),
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def selection(self) -> QRect | None:
        if self._start is None or self._current is None:
            return None
        return QRect(self._start, self._current).normalized().intersected(self.rect())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(3, 8, 18, 150))
        selection = self.selection()
        if selection and selection.width() > 0 and selection.height() > 0:
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#55ddb1"), 3))
            painter.drawRect(selection)
            painter.fillRect(
                QRect(selection.left(), selection.top(), min(240, selection.width()), 28),
                QColor(8, 17, 31, 225),
            )
            painter.setPen(QColor("white"))
            painter.drawText(
                selection.left() + 8,
                selection.top() + 20,
                f"{selection.width()} × {selection.height()} px",
            )

        panel = QRect(18, 18, min(720, self.width() - 36), 74)
        painter.fillRect(panel, QColor(8, 17, 31, 235))
        painter.setPen(QColor("white"))
        painter.drawText(
            panel.adjusted(16, 10, -16, -34),
            Qt.AlignLeft | Qt.AlignVCenter,
            "Drag around the area the model should watch",
        )
        painter.setPen(QColor("#55ddb1"))
        painter.drawText(
            panel.adjusted(16, 37, -16, -8),
            Qt.AlignLeft | Qt.AlignVCenter,
            "Release to save · Escape or right-click cancels",
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._start = event.position().toPoint()
            self._current = self._start
            self.update()
        elif event.button() == Qt.RightButton:
            self.reject()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None and event.buttons() & Qt.LeftButton:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton or self._start is None:
            return
        self._current = event.position().toPoint()
        selection = self.selection()
        if selection is None or selection.width() < 10 or selection.height() < 10:
            self._start = None
            self._current = None
            self.update()
            return
        global_top_left = self.mapToGlobal(selection.topLeft())
        self.selected_region = {
            "left": global_top_left.x(),
            "top": global_top_left.y(),
            "width": selection.width(),
            "height": selection.height(),
        }
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
