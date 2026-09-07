from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QDialog,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.gui.widgets import page_header, pil_to_pixmap
from app.vision.dataset import automatic_split, class_counts, quality_warnings
from app.gui.dataset_quality_dialog import DatasetQualityDialog
from app.gui.label_suggestions_dialog import LabelSuggestionsDialog
from app.vision.assistant import (
    dataset_quality_rows,
    merge_label_suggestions,
    near_duplicate_pairs,
)
from app.vision.detector import Detector


class DatasetPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Dataset",
                "Review classes, training/validation assignments, and the quality of your captured examples.",
            )
        )
        split_controls = QHBoxLayout()
        self.split = QSpinBox()
        self.split.setRange(50, 95)
        self.split.setSuffix("% training")
        self.split.setValue(int(context.config.get("train_split", 80)))
        split_controls.addWidget(self.split)
        for label, callback in (
            ("Automatic Split", self.auto_split),
            ("Toggle Train/Validation", self.toggle_split),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            split_controls.addWidget(button)
        split_controls.addStretch()
        layout.addLayout(split_controls)
        controls = QHBoxLayout()
        for label, callback in (
            ("Add Class", self.add_class),
            ("Rename Class", self.rename_class),
            ("Delete Class", self.delete_class),
            ("Reassign Object", self.reassign_object),
            ("Delete Selected Capture", self.delete_capture),
            ("Preview", self.preview_capture),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)

        assistant_bar = QHBoxLayout()
        quality = QPushButton("QUALITY DASHBOARD")
        quality.setToolTip(
            "Review per-class coverage, average box sizes, screen-location variety, "
            "and near-duplicate screenshots."
        )
        quality.clicked.connect(self.show_quality_dashboard)
        assistant_bar.addWidget(quality)
        assistant_bar.addStretch()
        assistant_bar.addWidget(QLabel("Suggestion confidence"))
        self.suggestion_confidence = QDoubleSpinBox()
        self.suggestion_confidence.setRange(0.05, 0.99)
        self.suggestion_confidence.setSingleStep(0.05)
        self.suggestion_confidence.setValue(0.35)
        assistant_bar.addWidget(self.suggestion_confidence)
        suggest = QPushButton("SUGGEST LABELS")
        suggest.setObjectName("Primary")
        suggest.setToolTip(
            "Use the accepted model to propose additional boxes on the selected screenshot. You approve each box before saving."
        )
        suggest.clicked.connect(self.suggest_labels)
        assistant_bar.addWidget(suggest)
        layout.addLayout(assistant_bar)
        self.class_table = QTableWidget(0, 4)
        self.class_table.setHorizontalHeaderLabels(
            ["Object class", "Examples", "Training images", "Validation images"]
        )
        self.class_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.class_table, 1)
        self.shot_table = QTableWidget(0, 4)
        self.shot_table.setHorizontalHeaderLabels(
            ["Screenshot", "Objects", "Split", "Created"]
        )
        self.shot_table.horizontalHeader().setStretchLastSection(True)
        self.shot_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.shot_table.doubleClicked.connect(self.preview_capture)
        layout.addWidget(self.shot_table, 2)
        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        self.warnings.setStyleSheet(
            "padding:12px; background:#111c2f; border-radius:6px;"
        )
        layout.addWidget(self.warnings)
        context.project_changed.connect(self.refresh)
        context.dataset_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.class_table.setRowCount(0)
        self.shot_table.setRowCount(0)
        project = self.context.projects
        if not project.data:
            self.warnings.setText("Open a project to manage its dataset.")
            return
        counts = class_counts(project)
        train_counts: Counter = Counter()
        val_counts: Counter = Counter()
        for shot in project.data["screenshots"]:
            target = train_counts if shot.get("split") == "train" else val_counts
            for name in {a["class_name"] for a in shot.get("annotations", [])}:
                target[name] += 1
        for name in project.data["classes"]:
            row = self.class_table.rowCount()
            self.class_table.insertRow(row)
            for col, value in enumerate(
                (name, counts[name], train_counts[name], val_counts[name])
            ):
                self.class_table.setItem(row, col, QTableWidgetItem(str(value)))
        for shot in project.data["screenshots"]:
            row = self.shot_table.rowCount()
            self.shot_table.insertRow(row)
            labels = ", ".join(a["class_name"] for a in shot.get("annotations", []))
            values = (
                shot["id"],
                labels,
                shot.get("split", "train"),
                shot.get("created_at", ""),
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, shot["id"])
                self.shot_table.setItem(row, col, item)
        self.warnings.setText("DATA CHECK\n• " + "\n• ".join(quality_warnings(project)))

    def auto_split(self) -> None:
        if not self.context.projects.data:
            return
        automatic_split(self.context.projects, self.split.value())
        self.context.dataset_changed.emit()
        self.context.log(
            f"Dataset split: {self.split.value()}% training / {100 - self.split.value()}% validation."
        )

    def add_class(self) -> None:
        if not self.context.projects.data:
            return
        name, ok = QInputDialog.getText(self, "Add Object Class", "Object name:")
        if ok and name.strip():
            self.context.projects.add_class(name)
            self.context.dataset_changed.emit()

    def rename_class(self) -> None:
        row = self.class_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select a class", "Select a class row first.")
            return
        old = self.class_table.item(row, 0).text()
        new, ok = QInputDialog.getText(self, "Rename Class", "New name:", text=old)
        if ok and new.strip():
            try:
                self.context.projects.rename_class(old, new)
                self.context.dataset_changed.emit()
            except Exception as exc:
                QMessageBox.critical(self, "Could not rename class", str(exc))

    def delete_class(self) -> None:
        row = self.class_table.currentRow()
        if row < 0:
            return
        name = self.class_table.item(row, 0).text()
        try:
            self.context.projects.remove_class(name)
            self.context.dataset_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Could not delete class", str(exc))

    def selected_shot_id(self) -> str | None:
        row = self.shot_table.currentRow()
        return self.shot_table.item(row, 0).data(Qt.UserRole) if row >= 0 else None

    def delete_capture(self) -> None:
        shot_id = self.selected_shot_id()
        if not shot_id:
            return
        if (
            QMessageBox.question(
                self, "Delete capture", "Delete this screenshot and all its boxes?"
            )
            == QMessageBox.Yes
        ):
            self.context.projects.remove_screenshot(shot_id)
            self.context.dataset_changed.emit()

    def toggle_split(self) -> None:
        shot_id = self.selected_shot_id()
        if not shot_id or not self.context.projects.data:
            return
        shot = next(
            s for s in self.context.projects.data["screenshots"] if s["id"] == shot_id
        )
        shot["split"] = "val" if shot.get("split") == "train" else "train"
        self.context.projects.save()
        self.context.dataset_changed.emit()

    def reassign_object(self) -> None:
        shot_id = self.selected_shot_id()
        if not shot_id or not self.context.projects.data:
            return
        shot = next(
            s for s in self.context.projects.data["screenshots"] if s["id"] == shot_id
        )
        annotations = shot.get("annotations", [])
        if not annotations:
            return
        choices = [
            f"{index + 1}. {ann['class_name']}" for index, ann in enumerate(annotations)
        ]
        selected, ok = QInputDialog.getItem(
            self, "Reassign Object", "Bounding box:", choices, 0, False
        )
        if not ok:
            return
        ann_index = choices.index(selected)
        classes = list(self.context.projects.data["classes"])
        new_name, ok = QInputDialog.getItem(
            self, "Reassign Object", "New class (or type a new one):", classes, 0, True
        )
        if ok and new_name.strip():
            normalized = self.context.projects.add_class(new_name)
            annotations[ann_index]["class_name"] = normalized
            self.context.projects.save()
            self.context.dataset_changed.emit()

    def preview_capture(self, *args) -> None:
        shot_id = self.selected_shot_id()
        if not shot_id or not self.context.projects.data:
            return
        shot = next(
            s for s in self.context.projects.data["screenshots"] if s["id"] == shot_id
        )
        from PIL import Image

        image = Image.open(self.context.projects.path(shot["image"])).convert("RGB")
        pixmap = pil_to_pixmap(image)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor("#28d7a1"), 4))
        for ann in shot["annotations"]:
            x, y, w, h = ann["bbox"]
            painter.drawRect(x, y, w, h)
            painter.drawText(x + 4, max(18, y - 5), ann["class_name"])
        painter.end()
        preview = QLabel()
        preview.setPixmap(
            pixmap.scaled(1100, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Capture Preview")
        dialog.layout().addWidget(preview, 0, 0, 1, dialog.layout().columnCount())
        dialog.exec()

    def show_quality_dashboard(self) -> None:
        project = self.context.projects
        if not project.data:
            QMessageBox.information(self, "Open a project", "Open a project first.")
            return
        rows = dataset_quality_rows(project)
        duplicates, truncated = near_duplicate_pairs(project)
        DatasetQualityDialog(
            project.data.get("name", "Project"),
            rows,
            duplicates,
            truncated,
            self,
        ).exec()

    def suggest_labels(self) -> None:
        shot_id = self.selected_shot_id()
        project = self.context.projects
        if not shot_id or not project.data:
            QMessageBox.information(
                self,
                "Select a capture",
                "Select one screenshot row before requesting label suggestions.",
            )
            return
        model = next(
            (
                item
                for item in project.data.get("models", [])
                if item.get("accepted")
            ),
            None,
        )
        if model is None:
            QMessageBox.information(
                self,
                "Accept a model",
                "Train and accept a model before requesting label suggestions.",
            )
            return
        model_path = project.path(model["path"])
        if not model_path.is_file():
            QMessageBox.warning(
                self, "Model unavailable", "The accepted model file could not be found."
            )
            return
        shot = next(
            item for item in project.data["screenshots"] if item["id"] == shot_id
        )
        from PIL import Image

        try:
            image = Image.open(project.path(shot["image"])).convert("RGB")
            confidence = self.suggestion_confidence.value()
            detections = Detector(model_path).predict(image, confidence)
            suggestions = merge_label_suggestions(
                shot.get("annotations", []),
                detections,
                project.data.get("classes", []),
                minimum_confidence=confidence,
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Suggestions unavailable", f"The model could not analyze this capture: {exc}"
            )
            return
        if not suggestions:
            QMessageBox.information(
                self,
                "No new suggestions",
                "The model did not find any new, non-duplicate boxes above that confidence. Try a lower threshold or another capture.",
            )
            return
        dialog = LabelSuggestionsDialog(image, suggestions, model["name"], self)
        if dialog.exec() != QDialog.Accepted:
            return
        selected = dialog.selected_annotations()
        if not selected:
            return
        added = project.add_annotations(shot_id, selected)
        self.context.dataset_changed.emit()
        self.context.log(
            f"Accepted {added} model-suggested label(s) for capture {shot_id}."
        )
        QMessageBox.information(
            self, "Labels added", f"Added {added} approved label(s) to the capture."
        )
