from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.vision.assistant import best_model_by_map50
from app.vision.model_manager import training_source_label


class ModelComparisonDialog(QDialog):
    def __init__(self, models: list[dict], classes: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Compare Models")
        self.resize(1100, 720)
        layout = QVBoxLayout(self)
        best = best_model_by_map50(models)
        summary = QLabel(
            f"Highest saved overall mAP50: {best['name']} ({best['metrics']['mAP50']:.3f}). "
            "This is informational and does not change the accepted model."
            if best
            else "No saved mAP50 values are available yet."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        tabs = QTabWidget()

        overview = QTableWidget(0, 7)
        overview.setHorizontalHeaderLabels(
            ["Model", "Status", "Started from", "mAP50", "mAP50-95", "Created", "Notes"]
        )
        overview.horizontalHeader().setStretchLastSection(True)
        for model in models:
            row = overview.rowCount()
            overview.insertRow(row)
            metrics = model.get("metrics", {})
            values = (
                model.get("name", "Untitled"),
                "Accepted" if model.get("accepted") else "Candidate",
                training_source_label(model),
                f"{metrics['mAP50']:.3f}" if isinstance(metrics.get("mAP50"), (int, float)) else "—",
                f"{metrics['mAP50-95']:.3f}" if isinstance(metrics.get("mAP50-95"), (int, float)) else "—",
                model.get("created_at", ""),
                model.get("notes", ""),
            )
            for column, value in enumerate(values):
                overview.setItem(row, column, QTableWidgetItem(str(value)))
        tabs.addTab(overview, "Overview")

        class_table = QTableWidget(len(classes), len(models) + 1)
        class_table.setHorizontalHeaderLabels(
            ["Class", *[str(model.get("name", "Untitled")) for model in models]]
        )
        for row, class_name in enumerate(classes):
            class_table.setItem(row, 0, QTableWidgetItem(class_name))
            values: list[tuple[int, float]] = []
            for model_column, model in enumerate(models, 1):
                value = (
                    model.get("metrics", {})
                    .get("per_class", {})
                    .get(class_name, {})
                    .get("mAP50")
                )
                item = QTableWidgetItem(
                    f"{value:.3f}" if isinstance(value, (int, float)) else "—"
                )
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                class_table.setItem(row, model_column, item)
                if isinstance(value, (int, float)):
                    values.append((model_column, float(value)))
            if values:
                maximum = max(value for _column, value in values)
                for column, value in values:
                    if value == maximum:
                        class_table.item(row, column).setBackground(QColor("#174a50"))
        class_table.horizontalHeader().setStretchLastSection(True)
        tabs.addTab(class_table, "Per-Class mAP50")
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ModelReportDialog(QDialog):
    def __init__(self, model_name: str, reports: list[tuple[str, Path]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Training Reports — {model_name}")
        self.resize(1000, 760)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        for label, path in reports:
            page = QScrollArea()
            page.setWidgetResizable(True)
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(path))
            image_label.setPixmap(
                pixmap.scaled(
                    940,
                    660,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            page.setWidget(image_label)
            tabs.addTab(page, label)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

