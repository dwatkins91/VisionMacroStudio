from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.gui.widgets import page_header
from app.gui.model_comparison_dialog import ModelComparisonDialog, ModelReportDialog
from app.vision.assistant import best_model_by_map50
from app.vision.model_manager import (
    accept_model,
    delete_model,
    training_source_label,
    update_model_notes,
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
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Model",
                "Status",
                "Started from",
                "Created",
                "Classes",
                "mAP50",
                "mAP50-95",
                "Notes",
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
        compare = QPushButton("COMPARE MODELS")
        compare.clicked.connect(self.compare_models)
        notes = QPushButton("Edit Notes")
        notes.clicked.connect(self.edit_notes)
        reports = QPushButton("View Training Report")
        reports.clicked.connect(self.view_report)
        buttons.addWidget(accept)
        buttons.addWidget(compare)
        buttons.addWidget(notes)
        buttons.addWidget(reports)
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
        models = self.context.projects.data["models"]
        best = best_model_by_map50(models)
        for model in models:
            row = self.table.rowCount()
            self.table.insertRow(row)
            status: list[str] = []
            if model.get("accepted"):
                status.append("Accepted")
            else:
                status.append("Candidate")
            if best is model:
                status.append("Best mAP50")
            metrics = model.get("metrics", {})
            values = (
                model["name"],
                " · ".join(status),
                training_source_label(model),
                model.get("created_at", ""),
                ", ".join(model.get("classes", [])),
                f"{metrics['mAP50']:.3f}" if isinstance(metrics.get("mAP50"), (int, float)) else "—",
                f"{metrics['mAP50-95']:.3f}" if isinstance(metrics.get("mAP50-95"), (int, float)) else "—",
                model.get("notes", ""),
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

    def selected_model(self) -> dict | None:
        model_id = self.selected_id()
        if not model_id or not self.context.projects.data:
            return None
        return next(
            (
                model
                for model in self.context.projects.data.get("models", [])
                if model.get("id") == model_id
            ),
            None,
        )

    def accept_selected(self) -> None:
        model_id = self.selected_id()
        if model_id:
            accept_model(self.context.projects, model_id)
            self.context.models_changed.emit()
            self.context.log(f"Accepted model: {model_id}")

    def compare_models(self) -> None:
        if not self.context.projects.data:
            return
        models = list(self.context.projects.data.get("models", []))
        if len(models) < 2:
            QMessageBox.information(
                self, "Train another model", "At least two saved models are needed for comparison."
            )
            return
        classes = list(self.context.projects.data.get("classes", []))
        for model in models:
            for class_name in model.get("classes", []):
                if class_name not in classes:
                    classes.append(class_name)
        ModelComparisonDialog(models, classes, self).exec()

    def edit_notes(self) -> None:
        model = self.selected_model()
        if model is None:
            QMessageBox.information(self, "Select a model", "Select a model row first.")
            return
        notes, ok = QInputDialog.getMultiLineText(
            self,
            "Model Notes",
            "Notes about strengths, weaknesses, or training changes:",
            str(model.get("notes", "")),
        )
        if ok:
            update_model_notes(self.context.projects, model["id"], notes)
            self.context.models_changed.emit()

    def view_report(self) -> None:
        model = self.selected_model()
        if model is None:
            QMessageBox.information(self, "Select a model", "Select a model row first.")
            return
        labels = {
            "confusion_matrix_normalized": "Normalized Confusion",
            "confusion_matrix": "Confusion Matrix",
            "results_plot": "Training Curves",
        }
        reports = []
        for key, label in labels.items():
            relative = str(model.get("reports", {}).get(key, ""))
            if not relative:
                continue
            path = self.context.projects.path(relative)
            if path.is_file():
                reports.append((label, path))
        if not reports:
            QMessageBox.information(
                self,
                "No saved report",
                "This model predates v0.2.0 or its training report files are unavailable. New training runs save confusion and training plots here.",
            )
            return
        ModelReportDialog(model["name"], reports, self).exec()

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
