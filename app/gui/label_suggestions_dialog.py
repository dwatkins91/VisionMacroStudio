from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.gui.widgets import pil_to_pixmap


class LabelSuggestionsDialog(QDialog):
    """Review model-proposed boxes before any annotation is changed."""

    def __init__(
        self, image: Image.Image, suggestions: list[dict], model_name: str, parent=None
    ) -> None:
        super().__init__(parent)
        self.suggestions = suggestions
        self.setWindowTitle("Review Suggested Labels")
        self.resize(1050, 820)
        layout = QVBoxLayout(self)
        intro = QLabel(
            f"Suggested by {model_name}. Uncheck any incorrect box; nothing is saved until Apply."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Subtitle")
        layout.addWidget(intro)

        pixmap = pil_to_pixmap(image.convert("RGB"))
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor("#28d7a1"), 4))
        for suggestion in suggestions:
            x, y, width, height = suggestion["bbox"]
            painter.drawRect(x, y, width, height)
            painter.drawText(
                x + 4,
                max(18, y - 5),
                f"{suggestion['class_name']} {suggestion['confidence']:.0%}",
            )
        painter.end()
        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setPixmap(
            pixmap.scaled(
                1000,
                590,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        layout.addWidget(preview, 1)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Use", "Class", "Confidence", "Box"])
        self.table.horizontalHeader().setStretchLastSection(True)
        for suggestion in suggestions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            use = QTableWidgetItem()
            use.setFlags(use.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            use.setCheckState(Qt.CheckState.Checked)
            use.setData(Qt.ItemDataRole.UserRole, suggestion)
            self.table.setItem(row, 0, use)
            self.table.setItem(row, 1, QTableWidgetItem(suggestion["class_name"]))
            self.table.setItem(
                row, 2, QTableWidgetItem(f"{suggestion['confidence']:.1%}")
            )
            self.table.setItem(
                row, 3, QTableWidgetItem(", ".join(str(v) for v in suggestion["bbox"]))
            )
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.accept
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_annotations(self) -> list[dict]:
        selected: list[dict] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            suggestion = dict(item.data(Qt.ItemDataRole.UserRole))
            selected.append(
                {
                    "class_name": suggestion["class_name"],
                    "bbox": list(suggestion["bbox"]),
                }
            )
        return selected

