from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.context import AppContext
from app.core.projects import ProjectError
from app.gui.widgets import page_header
from app.core.sample_project import populate_sample_project


class ProjectPage(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(
            page_header(
                "Project",
                "Create or open a workspace that keeps captures, models, and macros together.",
            )
        )
        self.status = QLabel("No project open")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            "font-size: 14pt; padding: 18px; background:#111c2f; border-radius:8px;"
        )
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        for text, callback in (
            ("New Project", self.new_project),
            ("Create Sample", self.create_sample_project),
            ("Open Project", self.open_project),
            ("Rename", self.rename_project),
            ("Export", self.export_project),
            ("Import", self.import_project),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        delete = QPushButton("Delete Current Project")
        delete.setObjectName("Danger")
        delete.clicked.connect(self.delete_project)
        layout.addWidget(delete, alignment=Qt.AlignLeft)
        self.storage = QLabel()
        self.storage.setObjectName("Subtitle")
        self.storage.setWordWrap(True)
        layout.addWidget(self.storage)
        open_storage = QPushButton("Open Project Storage Folder")
        open_storage.clicked.connect(self.open_storage_folder)
        layout.addWidget(open_storage, alignment=Qt.AlignLeft)
        layout.addStretch()
        context.project_changed.connect(self.refresh)
        context.settings_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        project = self.context.projects
        if project.is_open:
            data = project.data or {}
            self.status.setText(
                f"<b>{data.get('name')}</b><br>{project.root}<br><br>"
                f"{len(data.get('screenshots', []))} screenshots · {len(data.get('classes', []))} classes · "
                f"{len(data.get('models', []))} models · {len(data.get('macros', []))} macros"
            )
        else:
            self.status.setText(
                "No project is open. Create one to begin capturing objects."
            )
        self.storage.setText(
            "Default project storage: "
            + str(self.context.config.get("project_directory", ""))
            + "\nCaptures, datasets, models, macros, and logs remain in the selected project folder."
        )

    def new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        parent = Path(self.context.config.get("project_directory"))
        try:
            root = self.context.projects.create(parent, name)
            self.context.log(f"Created project: {root}")
            self.context.project_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Could not create project", str(exc))

    def open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Open Project", self.context.config.get("project_directory")
        )
        if not folder:
            return
        try:
            self.context.projects.open(Path(folder))
            self.context.log(f"Opened project: {folder}")
            self.context.project_changed.emit()
        except ProjectError as exc:
            QMessageBox.critical(self, "Could not open project", str(exc))

    def create_sample_project(self) -> None:
        parent = Path(self.context.config.get("project_directory"))
        try:
            root = self.context.projects.create(parent, "Vision Macro Studio Sample")
            populate_sample_project(self.context.projects)
            self.context.log(f"Created built-in sample project: {root}")
            self.context.project_changed.emit()
            QMessageBox.information(
                self,
                "Sample project created",
                "Open Macros to explore three examples. The counter tutorial sends no "
                "mouse or keyboard input. Input steps in the other templates start disabled.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not create sample project", str(exc))

    def open_storage_folder(self) -> None:
        folder = Path(self.context.config.get("project_directory", ""))
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def rename_project(self) -> None:
        if not self.context.projects.is_open:
            return
        current = self.context.projects.data["name"]
        name, ok = QInputDialog.getText(
            self, "Rename Project", "New display name:", text=current
        )
        if ok and name.strip():
            self.context.projects.rename(name)
            self.context.project_changed.emit()

    def export_project(self) -> None:
        if not self.context.projects.is_open:
            QMessageBox.information(self, "Open a project", "Open a project first.")
            return
        name = self.context.projects.data["name"] + ".zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Project", name, "ZIP archives (*.zip)"
        )
        if path:
            try:
                self.context.projects.export_zip(Path(path))
                self.context.log(f"Exported project to {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export failed", str(exc))

    def import_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Project", "", "ZIP archives (*.zip)"
        )
        if not path:
            return
        try:
            self.context.projects.import_zip(
                Path(path), Path(self.context.config.get("project_directory"))
            )
            self.context.project_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def delete_project(self) -> None:
        if not self.context.projects.is_open:
            return
        name = self.context.projects.data["name"]
        answer = QMessageBox.warning(
            self,
            "Delete project",
            f"Permanently delete {name} and every capture/model inside it?\n\nExport a backup first if needed.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer == QMessageBox.Yes:
            self.context.projects.delete_project()
            self.context.project_changed.emit()
