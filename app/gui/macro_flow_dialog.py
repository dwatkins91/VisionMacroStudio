from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
)

from app.automation.flowchart import flow_edges


EDGE_COLORS = {
    "next": "#7694bd",
    "match": "#28d7a1",
    "true": "#28d7a1",
    "false": "#ef718a",
    "failure": "#ef718a",
    "jump": "#f2b45f",
    "repeat": "#b48cff",
}


class MacroFlowDialog(QDialog):
    """Scrollable, connected overview of a numbered macro."""

    def __init__(self, macro: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Macro Flow — {macro.get('name', 'Untitled')}")
        self.resize(980, 760)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Connected flow view · green = match/true · red = false/timeout · "
            "gold = jump · violet = repeat"
        )
        intro.setObjectName("Subtitle")
        layout.addWidget(intro)
        scene = QGraphicsScene(self)
        view = QGraphicsView(scene)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(view, 1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        steps = list(macro.get("steps", []))
        node_width = 430.0
        node_height = 68.0
        gap = 52.0
        top = 30.0
        nodes: dict[int, QRectF] = {}
        for index, step in enumerate(steps):
            y = top + index * (node_height + gap)
            rect = QRectF(190, y, node_width, node_height)
            nodes[index] = rect
            action = str(step.get("action", "Unknown")).replace("_", " ").title()
            name = str(step.get("name", "")).strip()
            if step.get("action") == "SECTION":
                fill, border = "#174a50", "#28d7a1"
                title = f"◆  {name or 'Section'}"
                subtitle = "Visual divider"
            elif not step.get("enabled", True):
                fill, border = "#222b3b", "#59677c"
                title = f"{index + 1}. {name or action}"
                subtitle = f"{action} · disabled"
            else:
                fill, border = "#111c2f", "#5277a5"
                title = f"{index + 1}. {name or action}"
                subtitle = action if name else str(step.get("comment", ""))
                if step.get("action") == "CALL_MACRO":
                    subtitle = (
                        "Call → "
                        + str(step.get("macro_name") or step.get("macro_id") or "Missing")
                        + " → return"
                    )
                elif step.get("action") == "IF_VARIABLE":
                    subtitle = (
                        f"{step.get('variable', 'counter')} "
                        f"{step.get('comparison', '==')} "
                        f"{step.get('compare_value', '0')}"
                    )
            scene.addRect(rect, QPen(QColor(border), 2), QBrush(QColor(fill)))
            title_item = scene.addText(title)
            title_font = QFont(title_item.font())
            title_font.setBold(True)
            title_font.setPointSize(10)
            title_item.setFont(title_font)
            title_item.setDefaultTextColor(QColor("#e9f2ff"))
            title_item.setPos(rect.left() + 14, rect.top() + 8)
            if subtitle:
                subtitle_item = scene.addText(subtitle)
                subtitle_item.setDefaultTextColor(QColor("#9eb8da"))
                subtitle_item.setPos(rect.left() + 14, rect.top() + 34)

        for lane, edge in enumerate(flow_edges(steps)):
            source = nodes.get(int(edge["source"]))
            target = nodes.get(int(edge["target"]))
            if source is None or target is None:
                continue
            kind = str(edge["kind"])
            color = QColor(EDGE_COLORS.get(kind, "#7694bd"))
            pen = QPen(color, 2)
            if kind == "next" and edge["target"] == edge["source"] + 1:
                start_x = source.center().x()
                start_y = source.bottom()
                end_x = target.center().x()
                end_y = target.top()
                path = QPainterPath()
                path.moveTo(start_x, start_y)
                path.lineTo(end_x, end_y)
                label_x = start_x + 8
                label_y = (start_y + end_y) / 2 - 10
            else:
                backward = int(edge["target"]) <= int(edge["source"])
                side_x = 105 - (lane % 4) * 25 if backward else 700 + (lane % 4) * 25
                start_x = source.left() if backward else source.right()
                end_x = target.left() if backward else target.right()
                start_y = source.center().y()
                end_y = target.center().y()
                path = QPainterPath()
                path.moveTo(start_x, start_y)
                path.cubicTo(side_x, start_y, side_x, end_y, end_x, end_y)
                label_x = side_x - 34
                label_y = (start_y + end_y) / 2 - 12
            scene.addPath(path, pen)
            label = scene.addText(str(edge["label"]))
            label.setDefaultTextColor(color)
            label.setPos(label_x, label_y)

        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-45, -35, 45, 35))
