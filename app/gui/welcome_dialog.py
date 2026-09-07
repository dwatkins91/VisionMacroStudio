from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import __release_name__, __version__
from app.gui.system_check_dialog import SystemCheckDialog


def _page(title: str, body: str) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(8, 8, 8, 8)
    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    text = QLabel(body)
    text.setWordWrap(True)
    text.setTextFormat(Qt.TextFormat.RichText)
    text.setOpenExternalLinks(True)
    text.setStyleSheet("font-size: 11pt; line-height: 1.35;")
    layout.addWidget(heading)
    layout.addWidget(text)
    layout.addStretch()
    return page


class WelcomeDialog(QDialog):
    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Welcome to Vision Macro Studio")
        self.resize(700, 510)
        layout = QVBoxLayout(self)
        self.pages = QStackedWidget()
        self.pages.addWidget(
            _page(
                "Welcome",
                f"<b>Vision Macro Studio {__version__}</b> is the {__release_name__}. "
                "It brings capture, labeling, YOLO training, safe testing, and visual macro "
                "automation into one Windows desktop app.<br><br>"
                "A good first run is <b>Create or open a project → Capture → Dataset → "
                "Train → Test Model → Accept → Build a macro</b>.<br><br>"
                "You can also create the built-in sample project from the Project page to "
                "explore counters, branches, and portable coordinates without a model.",
            )
        )
        self.pages.addWidget(
            _page(
                "Safety and privacy",
                "Macros send real mouse and keyboard input to your desktop. Start with "
                "<b>Safe Step Preview</b>, use short time limits, and keep <b>F12</b> ready "
                "as the emergency stop.<br><br>"
                "Captures, labels, models, macros, and logs stay in the project folder you "
                "choose. Vision Macro Studio does not upload them. A first training run may "
                "download the selected pretrained model from Ultralytics.<br><br>"
                "Use automation only where you are authorized and where it follows the "
                "target application's rules.",
            )
        )
        storage_page = QWidget()
        storage_layout = QVBoxLayout(storage_page)
        heading = QLabel("Choose project storage")
        heading.setObjectName("PageTitle")
        explanation = QLabel(
            "New projects are stored here. This path is local to this Windows account and "
            "is not embedded into shared macros or application builds."
        )
        explanation.setWordWrap(True)
        self.project_directory = QLineEdit(
            str(context.config.get("project_directory", ""))
        )
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.project_directory, 1)
        path_row.addWidget(browse)
        check = QPushButton("Check My Computer")
        check.clicked.connect(self.check_computer)
        storage_layout.addWidget(heading)
        storage_layout.addWidget(explanation)
        storage_layout.addSpacing(10)
        storage_layout.addLayout(path_row)
        storage_layout.addSpacing(18)
        storage_layout.addWidget(check, alignment=Qt.AlignmentFlag.AlignLeft)
        storage_layout.addStretch()
        self.pages.addWidget(storage_page)
        layout.addWidget(self.pages, 1)
        nav = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.back)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("Primary")
        self.next_button.clicked.connect(self.next)
        nav.addWidget(self.back_button)
        nav.addStretch()
        self.progress = QLabel()
        self.progress.setObjectName("Subtitle")
        nav.addWidget(self.progress)
        nav.addStretch()
        nav.addWidget(self.next_button)
        layout.addLayout(nav)
        self.update_navigation()

    def browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Project Directory", self.project_directory.text()
        )
        if folder:
            self.project_directory.setText(folder)

    def check_computer(self) -> None:
        if self.project_directory.text().strip():
            self.context.config.data["project_directory"] = self.project_directory.text().strip()
        dialog = SystemCheckDialog(self.context, self)
        dialog.run_checks()
        dialog.exec()

    def back(self) -> None:
        self.pages.setCurrentIndex(max(0, self.pages.currentIndex() - 1))
        self.update_navigation()

    def next(self) -> None:
        if self.pages.currentIndex() < self.pages.count() - 1:
            self.pages.setCurrentIndex(self.pages.currentIndex() + 1)
            self.update_navigation()
            return
        values = {"onboarding_completed": True}
        if self.project_directory.text().strip():
            values["project_directory"] = self.project_directory.text().strip()
            values["model_directory"] = str(Path(self.project_directory.text().strip()) / "Models")
        self.context.config.update(values)
        self.context.settings_changed.emit()
        self.context.log("First-run setup completed.")
        self.accept()

    def update_navigation(self) -> None:
        index = self.pages.currentIndex()
        self.back_button.setEnabled(index > 0)
        self.next_button.setText("Get Started" if index == self.pages.count() - 1 else "Next")
        self.progress.setText(f"{index + 1} of {self.pages.count()}")
