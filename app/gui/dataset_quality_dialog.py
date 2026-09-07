from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DatasetQualityDialog(QDialog):
    def __init__(
        self,
        project_name: str,
        rows: list[dict],
        duplicates: list[tuple[str, str, int]],
        duplicate_scan_truncated: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Dataset Quality — {project_name}")
        self.resize(1050, 680)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        coverage = QWidget()
        coverage_layout = QVBoxLayout(coverage)
        coverage_layout.addWidget(
            QLabel(
                "Position spread measures how much a class moves around the image; a very low value can signal overfitting to one location."
            )
        )
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            [
                "Class",
                "Instances",
                "Train images",
                "Validation images",
                "Average box",
                "Position spread",
                "Recommendation",
            ]
        )
        table.horizontalHeader().setStretchLastSection(True)
        for row_data in rows:
            row = table.rowCount()
            table.insertRow(row)
            values = (
                row_data["class_name"],
                row_data["instances"],
                row_data["train_images"],
                row_data["val_images"],
                f"{row_data['average_box_percent']:.2f}%",
                f"{row_data['position_spread']:.3f}",
                row_data["recommendation"],
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(str(value)))
        coverage_layout.addWidget(table)
        tabs.addTab(coverage, "Class Coverage")

        duplicate_page = QWidget()
        duplicate_layout = QVBoxLayout(duplicate_page)
        duplicate_text = QTextEdit()
        duplicate_text.setReadOnly(True)
        if duplicates:
            duplicate_text.setPlainText(
                "\n".join(
                    f"{first}  ↔  {second}   (visual distance {distance})"
                    for first, second, distance in duplicates
                )
            )
        else:
            duplicate_text.setPlainText(
                "No near-identical screenshot pairs were found in the scan."
            )
        duplicate_layout.addWidget(duplicate_text)
        note = (
            "Only the first 500 screenshots were scanned to keep the dashboard responsive."
            if duplicate_scan_truncated
            else "Lower visual distance means the screenshots are more alike. Review before deleting anything."
        )
        duplicate_layout.addWidget(QLabel(note))
        tabs.addTab(duplicate_page, f"Near Duplicates ({len(duplicates)})")
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

