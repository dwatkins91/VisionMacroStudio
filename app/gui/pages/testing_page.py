from __future__ import annotations

import threading
import time

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.capture.grabber import grab_screen, list_monitors
from app.core.context import AppContext
from app.gui.widgets import array_to_pixmap, page_header
from app.vision.detector import Detector, draw_detections


class LiveDetectionWorker(QObject):
    frame = Signal(object, object, float, float)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self, model_path: str, confidence: float, monitor: int, target_fps: int
    ) -> None:
        super().__init__()
        self.model_path = model_path
        self.confidence = confidence
        self.monitor = monitor
        self.target_fps = target_fps
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    @Slot()
    def run(self) -> None:
        try:
            detector = Detector(self.model_path)
            while not self.stop_event.is_set():
                started = time.perf_counter()
                grab = grab_screen(self.monitor)
                array = np.asarray(grab.image)
                inference_start = time.perf_counter()
                detections = detector.predict(array, self.confidence)
                inference_ms = (time.perf_counter() - inference_start) * 1000
                annotated = draw_detections(array, detections)
                elapsed = time.perf_counter() - started
                fps = 1 / max(elapsed, 0.0001)
                self.frame.emit(annotated, detections, fps, inference_ms)
                self.stop_event.wait(max(0, 1 / max(1, self.target_fps) - elapsed))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class TestingPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.thread = None
        self.worker = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Test Model",
                "Open a saved image or watch live detections on a monitor before accepting a model.",
            )
        )
        controls = QHBoxLayout()
        self.model_combo = QComboBox()
        self.monitor_combo = QComboBox()
        self.confidence = QSlider(Qt.Horizontal)
        self.confidence.setRange(10, 99)
        self.confidence.setValue(
            round(float(context.config.get("confidence", 0.7)) * 100)
        )
        self.confidence_label = QLabel()
        self.confidence.valueChanged.connect(self._update_confidence)
        controls.addWidget(QLabel("Model"))
        controls.addWidget(self.model_combo, 2)
        controls.addWidget(QLabel("Source"))
        controls.addWidget(self.monitor_combo)
        controls.addWidget(self.confidence_label)
        controls.addWidget(self.confidence, 1)
        layout.addLayout(controls)
        buttons = QHBoxLayout()
        saved = QPushButton("Test Saved Image")
        saved.clicked.connect(self.test_image)
        self.live = QPushButton("Start Live Screen Test")
        self.live.setObjectName("Primary")
        self.live.clicked.connect(self.toggle_live)
        buttons.addWidget(saved)
        buttons.addWidget(self.live)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.status = QLabel("Select a model.")
        layout.addWidget(self.status)
        self.preview = QLabel("Detection preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(640, 360)
        self.preview.setStyleSheet(
            "background:#060b14; border:1px solid #263650; border-radius:8px;"
        )
        layout.addWidget(self.preview, 1)
        context.project_changed.connect(self.refresh)
        context.models_changed.connect(lambda: self.refresh(select_latest=True))
        self._update_confidence()
        self.refresh()

    def _update_confidence(self) -> None:
        self.confidence_label.setText(f"Confidence: {self.confidence.value()}%")

    def refresh(self, select_latest: bool = False) -> None:
        selected = None if select_latest else self.model_combo.currentData()
        self.model_combo.clear()
        project = self.context.projects
        if project.data:
            for model in project.data["models"]:
                label = model["name"] + (
                    "  ✓ accepted" if model.get("accepted") else ""
                )
                self.model_combo.addItem(label, model)
        if selected:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i).get("id") == selected.get("id"):
                    self.model_combo.setCurrentIndex(i)
                    break
        elif select_latest and self.model_combo.count():
            self.model_combo.setCurrentIndex(self.model_combo.count() - 1)
        self.monitor_combo.clear()
        try:
            monitors = list_monitors()
            self.monitor_combo.addItem("Entire desktop", 0)
            for index, monitor in enumerate(monitors[1:], 1):
                self.monitor_combo.addItem(
                    f"Monitor {index} ({monitor['width']}×{monitor['height']})", index
                )
        except Exception:
            self.monitor_combo.addItem("Entire desktop", 0)

    def model_path(self) -> str | None:
        model = self.model_combo.currentData()
        if not model or not self.context.projects.root:
            return None
        return str(self.context.projects.path(model["path"]))

    def test_image(self) -> None:
        path = self.model_path()
        if not path:
            QMessageBox.information(
                self, "Train a model", "Train or open a model first."
            )
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Test Saved Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not filename:
            return
        try:
            image = Image.open(filename).convert("RGB")
            array = np.asarray(image)
            started = time.perf_counter()
            detections = Detector(path).predict(array, self.confidence.value() / 100)
            elapsed = (time.perf_counter() - started) * 1000
            annotated = draw_detections(array, detections)
            pixmap = array_to_pixmap(annotated).scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.preview.setPixmap(pixmap)
            objects = (
                ", ".join(
                    f"{d['class_name']} {d['confidence']:.0%}" for d in detections
                )
                or "none"
            )
            self.status.setText(
                f"{len(detections)} detection(s) in {elapsed:.0f} ms: {objects}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Test failed", str(exc))

    def toggle_live(self) -> None:
        if self.worker is not None:
            self.stop_live()
            return
        path = self.model_path()
        if not path:
            QMessageBox.information(
                self, "Train a model", "Train or open a model first."
            )
            return
        self.thread = QThread(self)
        self.worker = LiveDetectionWorker(
            path,
            self.confidence.value() / 100,
            int(self.monitor_combo.currentData() or 0),
            int(self.context.config.get("detection_fps", 5)),
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.frame.connect(self.on_frame)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._live_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.live.setText("Stop Live Screen Test")
        self.context.log("Live screen test started.")
        self.thread.start()

    def on_frame(self, array, detections, fps: float, inference_ms: float) -> None:
        self.preview.setPixmap(
            array_to_pixmap(array).scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
        objects = (
            ", ".join(f"{d['class_name']} {d['confidence']:.0%}" for d in detections)
            or "none"
        )
        self.status.setText(
            f"FPS {fps:.1f} · inference {inference_ms:.0f} ms · visible: {objects}"
        )

    def on_failed(self, message: str) -> None:
        self.context.log(f"Live detection failed: {message}")
        QMessageBox.critical(self, "Live detection failed", message)

    def stop_live(self) -> None:
        if self.worker:
            self.worker.stop()

    def _live_finished(self) -> None:
        self.worker = None
        self.thread = None
        self.live.setText("Start Live Screen Test")
        self.context.log("Live screen test stopped.")
