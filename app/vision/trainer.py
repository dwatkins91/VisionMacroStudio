from __future__ import annotations

import shutil
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.core.projects import ProjectManager

from .dataset import export_yolo
from .assistant import extract_training_metrics, preserve_training_reports
from .model_manager import next_model_name, register_model

MODEL_FILES = {
    "Nano / Fast": "yolo11n.pt",
    "Small": "yolo11s.pt",
    "Medium": "yolo11m.pt",
}


class TrainingWorker(QObject):
    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, project: ProjectManager, settings: dict) -> None:
        super().__init__()
        self.project = project
        self.settings = settings
        self.stop_event = threading.Event()
        self._model = None

    def request_stop(self) -> None:
        self.stop_event.set()
        trainer = getattr(self._model, "trainer", None)
        if trainer is not None:
            trainer.stop = True

    @Slot()
    def run(self) -> None:
        try:
            from ultralytics import YOLO

            yaml_path = export_yolo(self.project)
            epochs = int(self.settings["epochs"])
            model_name = next_model_name(self.project)
            base_model_file = MODEL_FILES.get(
                self.settings["model_size"], "yolo11n.pt"
            )
            starting_model_path = self.settings.get("starting_model_path")
            if starting_model_path:
                model_file = str(starting_model_path)
                source_name = str(
                    self.settings.get("starting_model_name") or Path(model_file).stem
                )
                self.progress.emit(0, epochs, f"Preparing {source_name}")
                source = {
                    "type": "project_model",
                    "model_id": self.settings.get("starting_model_id"),
                    "name": source_name,
                }
            else:
                model_file = base_model_file
                self.progress.emit(0, epochs, f"Preparing {model_file}")
                source = {
                    "type": "pretrained",
                    "model_file": model_file,
                }
            self._model = YOLO(model_file)

            def epoch_callback(trainer) -> None:
                current = int(getattr(trainer, "epoch", 0)) + 1
                self.progress.emit(
                    current, epochs, f"Training epoch {current} of {epochs}"
                )
                if self.stop_event.is_set():
                    trainer.stop = True

            self._model.add_callback("on_train_epoch_end", epoch_callback)
            device = self.settings.get("device", "auto")
            if device == "auto":
                device = None
            elif device == "gpu":
                device = 0
            results = self._model.train(
                data=str(yaml_path),
                epochs=epochs,
                imgsz=int(self.settings["image_size"]),
                batch=int(self.settings["batch_size"]),
                device=device,
                project=str(self.project.path("exports/training_runs")),
                name=model_name,
                exist_ok=True,
                plots=True,
                verbose=True,
            )
            if self.stop_event.is_set():
                self.stopped.emit()
                return
            run_dir = Path(results.save_dir)
            best = run_dir / "weights" / "best.pt"
            if not best.exists():
                raise RuntimeError("Training finished, but best.pt was not created.")
            destination = self.project.path(f"models/{model_name}.pt")
            shutil.copy2(best, destination)
            classes = list(self.project.data["classes"])
            metrics = extract_training_metrics(results, classes)
            absolute_reports = preserve_training_reports(
                run_dir,
                self.project.path(f"models/reports/{model_name}"),
            )
            reports = {
                key: str(Path(path).relative_to(self.project.root)).replace("\\", "/")
                for key, path in absolute_reports.items()
            }
            record = register_model(
                self.project,
                model_name,
                str(destination.relative_to(self.project.root)).replace("\\", "/"),
                classes,
                metrics,
                {
                    "source": source,
                    "epochs": epochs,
                    "image_size": int(self.settings["image_size"]),
                    "batch_size": int(self.settings["batch_size"]),
                    "device": self.settings.get("device", "auto"),
                    "base_model_size": self.settings["model_size"],
                },
                reports,
            )
            self.completed.emit(record)
        except Exception as exc:
            self.failed.emit(str(exc))
