from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app import (
    __copyright__,
    __license__,
    __release_name__,
    __repository_url__,
    __version__,
)
from app.main import asset_path


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Vision Macro Studio")
        self.setFixedWidth(560)
        layout = QVBoxLayout(self)
        logo = QLabel()
        pixmap = QPixmap(str(asset_path("vision_macro_eye.png")))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(92, 92, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Vision Macro Studio")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version = QLabel(f"Version {__version__} — {__release_name__}")
        version.setObjectName("Subtitle")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notice = QLabel(
            f"{__copyright__}<br><br>"
            f"Licensed under the {__license__}. You may share and modify this program "
            "under that license. This program comes with absolutely no warranty. "
            "The complete corresponding source is available from the project repository."
        )
        notice.setWordWrap(True)
        notice.setTextFormat(Qt.TextFormat.RichText)
        notice.setStyleSheet("padding: 14px; background:#111c2f; border-radius:8px;")
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(notice)
        buttons = QHBoxLayout()
        source = QPushButton("View Source")
        source.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(__repository_url__)))
        license_button = QPushButton("View License")
        license_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"{__repository_url__}/blob/main/LICENSE"))
        )
        close = QPushButton("Close")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        buttons.addWidget(source)
        buttons.addWidget(license_button)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
