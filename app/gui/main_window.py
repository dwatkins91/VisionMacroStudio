from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.capture.hotkeys import HotkeyService
from app.core.context import AppContext
from app.gui.pages.capture_page import CapturePage
from app.gui.pages.dataset_page import DatasetPage
from app.gui.pages.logs_page import LogsPage
from app.gui.pages.macros_page import MacrosPage
from app.gui.pages.models_page import ModelsPage
from app.gui.pages.project_page import ProjectPage
from app.gui.pages.settings_page import SettingsPage
from app.gui.pages.testing_page import TestingPage
from app.gui.pages.training_page import TrainingPage
from app import __release_name__, __repository_url__, __version__
from app.gui.about_dialog import AboutDialog
from app.gui.system_check_dialog import SystemCheckDialog
from app.gui.welcome_dialog import WelcomeDialog


class MainWindow(QMainWindow):
    NAV_ITEMS = [
        "Project",
        "Capture",
        "Dataset",
        "Train",
        "Test Model",
        "Models",
        "Macros",
        "Logs",
        "Settings",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Vision Macro Studio {__version__}")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 680)
        self.context = AppContext()
        self.hotkeys = HotkeyService()
        self._create_menus()
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 12)
        side_layout.setSpacing(1)
        brand = QLabel("VISION\nMACRO STUDIO")
        brand.setObjectName("Brand")
        side_layout.addWidget(brand)
        self.stack = QStackedWidget()
        self.pages = {
            "Project": ProjectPage(self.context),
            "Capture": CapturePage(self.context),
            "Dataset": DatasetPage(self.context),
            "Train": TrainingPage(self.context),
            "Test Model": TestingPage(self.context),
            "Models": ModelsPage(self.context),
            "Macros": MacrosPage(self.context),
            "Logs": LogsPage(self.context),
            "Settings": SettingsPage(self.context),
        }
        self.nav_buttons: list[QPushButton] = []
        for index, name in enumerate(self.NAV_ITEMS):
            button = QPushButton(name)
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side_layout.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(self.pages[name])
        side_layout.addStretch()
        stop = QPushButton("EMERGENCY STOP")
        stop.setObjectName("StopButton")
        stop.clicked.connect(self.pages["Macros"].emergency_stop)
        side_layout.addWidget(stop)
        self.project_label = QLabel("No project open")
        self.project_label.setWordWrap(True)
        self.project_label.setObjectName("Subtitle")
        self.project_label.setContentsMargins(12, 8, 12, 4)
        side_layout.addWidget(self.project_label)
        version_label = QLabel(f"v{__version__} · {__release_name__}")
        version_label.setObjectName("VersionLabel")
        version_label.setContentsMargins(12, 0, 12, 4)
        side_layout.addWidget(version_label)
        root.addWidget(sidebar)
        divider_host = QWidget()
        divider_host.setObjectName("DividerHost")
        divider_host.setFixedWidth(16)
        divider_layout = QVBoxLayout(divider_host)
        divider_layout.setContentsMargins(7, 26, 7, 26)
        divider_layout.setSpacing(0)
        divider = QFrame()
        divider.setObjectName("ContentDivider")
        divider.setFixedWidth(2)
        divider_layout.addWidget(
            divider, 1, Qt.AlignmentFlag.AlignHCenter
        )
        root.addWidget(divider_host)
        root.addWidget(self.stack, 1)
        self.context.project_changed.connect(self.update_project_label)
        self.context.settings_changed.connect(self.reload_hotkeys)
        self.pages["Train"].training_completed.connect(
            lambda: self.navigate(self.NAV_ITEMS.index("Test Model"))
        )
        self.hotkeys.capture_requested.connect(self.pages["Capture"].request_capture)
        self.hotkeys.record_requested.connect(self.pages["Macros"].start_recording)
        self.hotkeys.stop_recording_requested.connect(
            self.pages["Macros"].stop_recording
        )
        self.hotkeys.run_macro_requested.connect(self.pages["Macros"].run_macro)
        self.hotkeys.emergency_stop_requested.connect(
            self.pages["Macros"].emergency_stop
        )
        self.hotkeys.error.connect(self.context.log)
        self.navigate(0)
        self.update_project_label()
        QTimer.singleShot(0, self.reload_hotkeys)
        QTimer.singleShot(450, self.show_welcome_if_needed)

    def _create_menus(self) -> None:
        help_menu = self.menuBar().addMenu("Help")
        for text, callback in (
            ("Welcome and First Steps", self.show_welcome),
            ("Check My Computer", self.show_system_check),
            ("Open Online User Guide", self.open_user_guide),
            ("View Releases", self.open_releases),
            ("About and License", self.show_about),
        ):
            action = QAction(text, self)
            action.triggered.connect(callback)
            help_menu.addAction(action)

    def show_welcome_if_needed(self) -> None:
        if not bool(self.context.config.get("onboarding_completed", False)):
            self.show_welcome()

    def show_welcome(self) -> None:
        WelcomeDialog(self.context, self).exec()

    def show_system_check(self) -> None:
        dialog = SystemCheckDialog(self.context, self)
        dialog.run_checks()
        dialog.exec()

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def open_user_guide(self) -> None:
        QDesktopServices.openUrl(QUrl(f"{__repository_url__}/blob/main/docs/USER_GUIDE.md"))

    def open_releases(self) -> None:
        QDesktopServices.openUrl(QUrl(f"{__repository_url__}/releases"))

    def navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def update_project_label(self) -> None:
        project = self.context.projects
        self.project_label.setText(
            f"Project\n{project.data['name']}" if project.data else "No project open"
        )

    def reload_hotkeys(self) -> None:
        self.hotkeys.restart(self.context.config.data)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hotkeys.stop()
        self.pages["Macros"].emergency_stop()
        self.pages["Test Model"].stop_live()
        self.pages["Train"].stop_training()
        event.accept()
