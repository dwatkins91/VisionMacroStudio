from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.gui.widgets import page_header
from app.vision.model_manager import (
    accept_model,
    delete_model,
    training_source_label,
)


class ModelsPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Model Library",
                "Keep multiple versions, test them, and explicitly choose the model used by macros.",
            )
        )
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Model",
                "Status",
                "Started from",
                "Created",
                "Classes",
                "mAP50",
                "File",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        accept = QPushButton("ACCEPT MODEL")
        accept.setObjectName("Primary")
        accept.clicked.connect(self.accept_selected)
        delete = QPushButton("Delete Model")
        delete.setObjectName("Danger")
        delete.clicked.connect(self.delete_selected)
        buttons.addWidget(accept)
        buttons.addWidget(delete)
        buttons.addStretch()
        layout.addLayout(buttons)
        context.project_changed.connect(self.refresh)
        context.models_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if not self.context.projects.data:
            return
        for model in self.context.projects.data["models"]:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                model["name"],
                "Accepted" if model.get("accepted") else "Candidate",
                training_source_label(model),
                model.get("created_at", ""),
                ", ".join(model.get("classes", [])),
                f"{model.get('metrics', {}).get('mAP50', 0):.3f}",
                model["path"],
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, model["id"])
                self.table.setItem(row, col, item)

    def selected_id(self) -> str | None:
        row = self.table.currentRow()
        return self.table.item(row, 0).data(Qt.UserRole) if row >= 0 else None

    def accept_selected(self) -> None:
        model_id = self.selected_id()
        if model_id:
            accept_model(self.context.projects, model_id)
            self.context.models_changed.emit()
            self.context.log(f"Accepted model: {model_id}")

    def delete_selected(self) -> None:
        model_id = self.selected_id()
        if (
            model_id
            and QMessageBox.question(
                self, "Delete model", f"Delete {model_id}? This cannot be undone."
            )
            == QMessageBox.Yes
        ):
            delete_model(self.context.projects, model_id)
            self.context.models_changed.emit()
