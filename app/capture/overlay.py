from __future__ import annotations

from typing import Any

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget

from .grabber import ScreenGrab


class CaptureOverlay(QWidget):
    capture_completed = Signal(object, object, object)
    capture_cancelled = Signal()

    def __init__(self, grab: ScreenGrab, class_names: list[str]) -> None:
        super().__init__()
        self.grab = grab
        self.class_names = list(class_names)
        self.annotations: list[dict[str, Any]] = []
        self.start_point: QPoint | None = None
        self.current_point: QPoint | None = None
        self.pixmap = QPixmap.fromImage(ImageQt(grab.image))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setGeometry(grab.left, grab.top, grab.image.width, grab.image.height)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 105))
        for ann in self.annotations:
            x, y, w, h = ann["bbox"]
            rect = QRect(x, y, w, h)
            painter.drawPixmap(rect, self.pixmap, rect)
            painter.setPen(QPen(QColor("#28d7a1"), 3))
            painter.drawRect(rect)
            painter.fillRect(
                QRect(x, max(0, y - 24), max(90, len(ann["class_name"]) * 8), 24),
                QColor("#28d7a1"),
            )
            painter.setPen(QColor("#08111f"))
            painter.drawText(x + 6, max(17, y - 6), ann["class_name"])
        selection = self.selection_rect()
        if selection and selection.width() > 1 and selection.height() > 1:
            painter.drawPixmap(selection, self.pixmap, selection)
            painter.setPen(QPen(QColor("#5ecbff"), 3))
            painter.drawRect(selection)
        painter.setPen(QColor("white"))
        painter.fillRect(QRect(18, 18, 610, 64), QColor(8, 17, 31, 220))
        painter.drawText(
            35,
            45,
            "Drag a box around an object. Repeat for more objects on this screenshot.",
        )
        painter.drawText(
            35,
            69,
            "ENTER = save screenshot     ESC = cancel     BACKSPACE = undo last box",
        )

    def selection_rect(self) -> QRect | None:
        if self.start_point is None or self.current_point is None:
            return None
        return (
            QRect(self.start_point, self.current_point)
            .normalized()
            .intersected(self.rect())
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.start_point = event.position().toPoint()
            self.current_point = self.start_point
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.start_point is not None:
            self.current_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton or self.start_point is None:
            return
        self.current_point = event.position().toPoint()
        rect = self.selection_rect()
        self.start_point = None
        self.current_point = None
        if rect is None or rect.width() < 5 or rect.height() < 5:
            self.update()
            return
        choices = self.class_names or ["Object_A"]
        label, accepted = QInputDialog.getItem(
            self,
            "Label object",
            "What object is this? Choose an existing name or type a new one:",
            choices,
            0,
            True,
        )
        label = label.strip().replace(" ", "_")
        if accepted and label:
            if label not in self.class_names:
                self.class_names.append(label)
            self.annotations.append(
                {
                    "class_name": label,
                    "bbox": [rect.x(), rect.y(), rect.width(), rect.height()],
                }
            )
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not self.annotations:
                QMessageBox.information(
                    self,
                    "Nothing selected",
                    "Draw and label at least one object first.",
                )
                return
            self.capture_completed.emit(
                self.grab.image, self.annotations, (self.grab.left, self.grab.top)
            )
            self.close()
        elif event.key() == Qt.Key_Backspace and self.annotations:
            self.annotations.pop()
            self.update()
        elif event.key() == Qt.Key_Escape:
            self.capture_cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)
