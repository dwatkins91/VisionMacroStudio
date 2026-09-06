from __future__ import annotations

import numpy as np
from PIL.ImageQt import ImageQt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def page_header(title: str, subtitle: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 10)
    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    sub = QLabel(subtitle)
    sub.setObjectName("Subtitle")
    sub.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(sub)
    return widget


def pil_to_pixmap(image) -> QPixmap:
    return QPixmap.fromImage(ImageQt(image))


def array_to_pixmap(array: np.ndarray) -> QPixmap:
    contiguous = np.ascontiguousarray(array)
    height, width = contiguous.shape[:2]
    channels = 1 if contiguous.ndim == 2 else contiguous.shape[2]
    if channels == 1:
        image = QImage(contiguous.data, width, height, width, QImage.Format_Grayscale8)
    else:
        image = QImage(
            contiguous.data, width, height, width * channels, QImage.Format_RGB888
        )
    return QPixmap.fromImage(image.copy())
