from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .config import ConfigManager
from .projects import ProjectManager


class AppContext(QObject):
    project_changed = Signal()
    dataset_changed = Signal()
    models_changed = Signal()
    macros_changed = Signal()
    settings_changed = Signal()
    log_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigManager()
        self.projects = ProjectManager()
        self.system_checks = []

    def log(self, message: str) -> None:
        self.log_message.emit(message)
