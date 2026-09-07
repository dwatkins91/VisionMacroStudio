from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.system_check import CheckResult, checks_summary, run_system_checks


class SystemCheckWorker(QObject):
    completed = Signal(object)

    def __init__(self, project_directory: str) -> None:
        super().__init__()
        self.project_directory = project_directory

    @Slot()
    def run(self) -> None:
        self.completed.emit(
            run_system_checks(self.project_directory, deep=True, include_display=True)
        )


class SystemCheckDialog(QDialog):
    checks_completed = Signal(object)

    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.results: list[CheckResult] = []
        self.thread: QThread | None = None
        self.worker: SystemCheckWorker | None = None
        self.setWindowTitle("Check My Computer")
        self.resize(820, 570)
        layout = QVBoxLayout(self)
        heading = QLabel("System readiness")
        heading.setObjectName("PageTitle")
        intro = QLabel(
            "This local check imports the packaged components, verifies writable folders, "
            "and confirms screen access. It does not capture, save, or upload your screen."
        )
        intro.setObjectName("Subtitle")
        intro.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(intro)
        self.summary = QLabel("Ready to check this computer.")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            "font-size: 12pt; padding: 12px; background:#111c2f; border-radius:7px;"
        )
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Status", "Check", "Details"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run Checks")
        self.run_button.setObjectName("Primary")
        self.run_button.clicked.connect(self.run_checks)
        copy_button = QPushButton("Copy Report")
        copy_button.clicked.connect(self.copy_report)
        save_button = QPushButton("Save Report")
        save_button.clicked.connect(self.save_report)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.run_button)
        buttons.addWidget(copy_button)
        buttons.addWidget(save_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def run_checks(self) -> None:
        if self.thread is not None:
            return
        self.table.setRowCount(0)
        self.summary.setText("Checking installed components and local access…")
        self.run_button.setEnabled(False)
        self.thread = QThread(self)
        self.worker = SystemCheckWorker(
            str(self.context.config.get("project_directory", ""))
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.completed.connect(self.show_results)
        self.worker.completed.connect(self.thread.quit)
        self.thread.finished.connect(self._thread_finished)
        self.thread.start()

    @Slot(object)
    def show_results(self, results: list[CheckResult]) -> None:
        self.results = results
        summary = checks_summary(results)
        counts = summary["counts"]
        if summary["ready"]:
            text = (
                f"READY — {counts['pass']} passed"
                + (f", {counts['warn']} advisory warning(s)." if counts["warn"] else ".")
            )
        else:
            text = f"NEEDS ATTENTION — {counts['fail']} required check(s) failed."
        self.summary.setText(text)
        colors = {"pass": "#55ddb1", "warn": "#f3c969", "fail": "#ff657a"}
        labels = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
        self.table.setRowCount(len(results))
        for row, result in enumerate(results):
            status_item = QTableWidgetItem(labels.get(result.status, result.status.upper()))
            status_item.setForeground(QColor(colors.get(result.status, "#e8eef8")))
            self.table.setItem(row, 0, status_item)
            self.table.setItem(row, 1, QTableWidgetItem(result.label))
            self.table.setItem(row, 2, QTableWidgetItem(result.detail))
        self.context.system_checks = list(results)
        self.checks_completed.emit(results)

    def _thread_finished(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Again")

    def report_data(self) -> dict:
        return checks_summary(self.results)

    def copy_report(self) -> None:
        if not self.results:
            QMessageBox.information(self, "Run checks first", "Run the system check first.")
            return
        QApplication.clipboard().setText(json.dumps(self.report_data(), indent=2))
        self.context.log("Copied the privacy-safe system check report.")

    def save_report(self) -> None:
        if not self.results:
            QMessageBox.information(self, "Run checks first", "Run the system check first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save System Check", "VisionMacroStudio-System-Check.json", "JSON (*.json)"
        )
        if path:
            Path(path).write_text(json.dumps(self.report_data(), indent=2), encoding="utf-8")
            self.context.log("Saved a privacy-safe system check report.")

    def closeEvent(self, event) -> None:
        if self.thread is not None and self.thread.isRunning():
            QMessageBox.information(
                self, "Check in progress", "Please wait for the current system check to finish."
            )
            event.ignore()
            return
        super().closeEvent(event)
