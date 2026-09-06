from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.gui.widgets import page_header
from app.vision.dataset import automatic_split, quality_warnings
from app.vision.trainer import TrainingWorker


class TrainingPage(QWidget):
    training_completed = Signal()

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.thread = None
        self.worker = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Train",
                "Start fresh from pretrained YOLO or refine one of your saved models using the full current dataset.",
            )
        )
        settings_box = QGroupBox("Training settings")
        form = QFormLayout(settings_box)
        self.starting_model = QComboBox()
        self.starting_model.setToolTip(
            "Choose fresh training or continue learning from a model already saved in this project."
        )
        self.starting_model.currentIndexChanged.connect(
            self.update_starting_model_controls
        )
        self.model_size = QComboBox()
        self.model_size.addItems(["Nano / Fast", "Small", "Medium"])
        self.epochs = QSpinBox()
        self.epochs.setRange(1, 1000)
        self.epochs.setValue(50)
        self.image_size = QComboBox()
        self.image_size.addItems(["416", "640", "800"])
        self.image_size.setCurrentText("640")
        self.batch_size = QSpinBox()
        self.batch_size.setRange(-1, 128)
        self.batch_size.setValue(-1)
        self.batch_size.setSpecialValueText("Automatic")
        self.device = QComboBox()
        self.device.addItems(["Automatic", "CPU", "GPU"])
        form.addRow("Start from", self.starting_model)
        form.addRow("Model size (base only)", self.model_size)
        form.addRow("Epochs", self.epochs)
        form.addRow("Image size", self.image_size)
        form.addRow("Batch size", self.batch_size)
        form.addRow("Device", self.device)
        layout.addWidget(settings_box)
        self.quality = QLabel()
        self.quality.setWordWrap(True)
        self.quality.setStyleSheet(
            "padding:12px; background:#111c2f; border-radius:6px;"
        )
        layout.addWidget(self.quality)
        self.status = QLabel("Ready")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        buttons = QHBoxLayout()
        self.train_button = QPushButton("TRAIN MODEL")
        self.train_button.setObjectName("Primary")
        self.train_button.clicked.connect(self.start_training)
        self.stop_button = QPushButton("STOP TRAINING")
        self.stop_button.setObjectName("Danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_training)
        buttons.addWidget(self.train_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()
        context.project_changed.connect(self.refresh)
        context.dataset_changed.connect(self.refresh)
        context.models_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        selected_id = self.starting_model.currentData()
        self.starting_model.blockSignals(True)
        self.starting_model.clear()
        self.starting_model.addItem("Pretrained YOLO base (fresh training)", None)
        if self.context.projects.data:
            for model in reversed(self.context.projects.data.get("models", [])):
                details = []
                if model.get("accepted"):
                    details.append("Accepted")
                map50 = model.get("metrics", {}).get("mAP50")
                if isinstance(map50, (int, float)):
                    details.append(f"mAP50 {map50:.3f}")
                suffix = f" ({', '.join(details)})" if details else ""
                self.starting_model.addItem(model["name"] + suffix, model["id"])
        selected_index = self.starting_model.findData(selected_id)
        self.starting_model.setCurrentIndex(max(0, selected_index))
        self.starting_model.blockSignals(False)
        self.update_starting_model_controls()
        self.quality.setText(
            "DATA QUALITY\n• " + "\n• ".join(quality_warnings(self.context.projects))
        )

    def update_starting_model_controls(self) -> None:
        continuing = self.starting_model.currentData() is not None
        self.model_size.setEnabled(not continuing)
        if continuing:
            self.model_size.setToolTip(
                "The selected model already determines whether this is Nano, Small, or Medium."
            )
        else:
            self.model_size.setToolTip("Choose the pretrained YOLO model size.")

    def start_training(self) -> None:
        project = self.context.projects
        if not project.data or not project.data["screenshots"]:
            QMessageBox.information(
                self,
                "Capture examples",
                "Capture and label some objects before training.",
            )
            return
        if not any(s.get("split") == "val" for s in project.data["screenshots"]):
            automatic_split(project, int(self.context.config.get("train_split", 80)))
            self.context.dataset_changed.emit()
        warnings = quality_warnings(project)
        if any("only has" in warning for warning in warnings):
            answer = QMessageBox.warning(
                self,
                "Small dataset",
                "Your dataset is small. Training may be unreliable. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        starting_model_id = self.starting_model.currentData()
        starting_model = None
        if starting_model_id is not None:
            starting_model = next(
                (
                    model
                    for model in project.data.get("models", [])
                    if model.get("id") == starting_model_id
                ),
                None,
            )
            if starting_model is None:
                QMessageBox.warning(
                    self,
                    "Starting model unavailable",
                    "That model is no longer in this project. Choose another starting model.",
                )
                self.refresh()
                return
            starting_path = project.path(starting_model["path"])
            if not starting_path.is_file():
                QMessageBox.warning(
                    self,
                    "Starting model file missing",
                    f"The saved file for {starting_model['name']} could not be found.",
                )
                return
            if starting_model.get("classes", []) != project.data.get("classes", []):
                answer = QMessageBox.warning(
                    self,
                    "Class list changed",
                    "This model was trained with a different set of object classes. "
                    "Starting from the pretrained YOLO base is usually safer. "
                    "Continue from this model anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    return
        settings = {
            "model_size": self.model_size.currentText(),
            "epochs": self.epochs.value(),
            "image_size": int(self.image_size.currentText()),
            "batch_size": self.batch_size.value(),
            "device": self.device.currentText().lower().replace("automatic", "auto"),
        }
        if starting_model is not None:
            settings.update(
                {
                    "starting_model_id": starting_model["id"],
                    "starting_model_name": starting_model["name"],
                    "starting_model_path": str(project.path(starting_model["path"])),
                }
            )
        self.thread = QThread(self)
        self.worker = TrainingWorker(project, settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.stopped.connect(self.on_stopped)
        for signal in (self.worker.completed, self.worker.failed, self.worker.stopped):
            signal.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.train_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("Starting training…")
        source_description = (
            starting_model["name"]
            if starting_model is not None
            else f"the pretrained {self.model_size.currentText()} base"
        )
        self.context.log(
            f"Model training started from {source_description} "
            f"for {self.epochs.value()} epochs."
        )
        self.thread.start()

    def on_progress(self, epoch: int, total: int, message: str) -> None:
        self.progress.setValue(round(epoch / max(1, total) * 100))
        self.status.setText(message)

    def stop_training(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.status.setText("Stopping safely after the current operation…")

    def _reset(self) -> None:
        self.train_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.worker = None
        self.thread = None

    def on_completed(self, model: dict) -> None:
        self.progress.setValue(100)
        self.status.setText(f"Training complete: {model['name']}")
        self.context.log(f"Training complete: {model['name']}")
        self.context.models_changed.emit()
        self.training_completed.emit()
        self._reset()

    def on_failed(self, message: str) -> None:
        self.status.setText("Training failed")
        self.context.log(f"Training failed: {message}")
        QMessageBox.critical(self, "Training failed", message)
        self._reset()

    def on_stopped(self) -> None:
        self.status.setText("Training stopped.")
        self.context.log("Training stopped by user.")
        self._reset()
