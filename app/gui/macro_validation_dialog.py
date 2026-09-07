from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from app.automation.validator import MacroIssue, issue_counts


class MacroValidationDialog(QDialog):
    step_requested = Signal(int)

    def __init__(self, macro_name: str, issues: list[MacroIssue], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Macro Validation")
        self.resize(720, 460)
        layout = QVBoxLayout(self)
        counts = issue_counts(issues)
        if counts["error"]:
            headline = f"{counts['error']} error(s) must be fixed"
            color = "#ff6b7d"
        elif counts["warning"]:
            headline = f"Ready with {counts['warning']} warning(s)"
            color = "#ffc857"
        else:
            headline = "Validation passed"
            color = "#55ddb1"
        title = QLabel(headline)
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color};")
        layout.addWidget(title)
        subtitle = QLabel(
            f"{macro_name} · Double-click an issue to select its step in the builder."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.issue_list = QListWidget()
        self.issue_list.setAlternatingRowColors(True)
        if issues:
            colors = {
                "error": QColor("#ff8291"),
                "warning": QColor("#ffd479"),
                "info": QColor("#8fd7ff"),
            }
            for issue in issues:
                prefix = issue.severity.upper()
                item = QListWidgetItem(f"{prefix}  ·  {issue.message}")
                item.setForeground(colors.get(issue.severity, QColor("white")))
                if issue.step_number is not None:
                    item.setData(Qt.UserRole, issue.step_number - 1)
                self.issue_list.addItem(item)
        else:
            item = QListWidgetItem(
                "PASS  ·  No broken destinations, missing classes, disabled branch targets, "
                "unreachable steps, or unbounded loops were found."
            )
            item.setForeground(QColor("#55ddb1"))
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.issue_list.addItem(item)
        self.issue_list.itemDoubleClicked.connect(self._open_issue)
        layout.addWidget(self.issue_list, 1)

        note = QLabel(
            "Warnings do not block a run. Errors indicate that the macro cannot "
            "run reliably as configured."
        )
        note.setWordWrap(True)
        note.setObjectName("Subtitle")
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_issue(self, item: QListWidgetItem, _column: int = 0) -> None:
        row = item.data(Qt.UserRole)
        if isinstance(row, int) and row >= 0:
            self.step_requested.emit(row)
            self.accept()
