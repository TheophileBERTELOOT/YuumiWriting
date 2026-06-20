from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


NODE_COLORS = (
    "#4f86c6",
    "#7f6bb3",
    "#4c9f70",
    "#c77d4f",
    "#b85c7a",
    "#3e9ca6",
    "#9a8b42",
    "#8a6b52",
)
EDGE_COLORS = ("#7ca6d9", "#d6aa4c", "#76b37a", "#d46a6a", "#b594d6")
EDGE_STYLES = (
    Qt.PenStyle.SolidLine,
    Qt.PenStyle.DashLine,
    Qt.PenStyle.DotLine,
    Qt.PenStyle.DashDotLine,
)


def _stable_index(value: str, size: int) -> int:
    digest = hashlib.sha256(value.strip().casefold().encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % size


def _fill_combo(combo: QComboBox, values: set[str], current: str = "") -> None:
    combo.setEditable(True)
    combo.addItems(sorted(value for value in values if value))
    combo.setCurrentText(current)


class NodeDialog(QDialog):
    def __init__(self, types: set[str], name: str = "", node_type: str = "", text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nœud")
        self.resize(430, 330)
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(name)
        self.type_combo = QComboBox()
        _fill_combo(self.type_combo, types, node_type)
        self.text_edit = QTextEdit(text)
        self.text_edit.setPlaceholderText("Notes, description, informations libres…")
        layout.addRow("Nom :", self.name_edit)
        layout.addRow("Type :", self.type_combo)
        layout.addRow("Texte :", self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, str, str]:
        return self.name_edit.text().strip(), self.type_combo.currentText().strip(), self.text_edit.toPlainText()

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Nom requis", "Donnez un nom au nœud.")
            return
        super().accept()


class EdgeDialog(QDialog):
    def __init__(self, nodes: list[tuple[str, str]], types: set[str], source_id: str = "", target_id: str = "", edge_type: str = "", text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Arête")
        self.resize(430, 330)
        layout = QFormLayout(self)
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        for node_id, name in nodes:
            self.source_combo.addItem(name, node_id)
            self.target_combo.addItem(name, node_id)
        self._select_id(self.source_combo, source_id)
        self._select_id(self.target_combo, target_id)
        self.type_combo = QComboBox()
        _fill_combo(self.type_combo, types, edge_type)
        self.text_edit = QTextEdit(text)
        self.text_edit.setPlaceholderText("Notes, description, informations libres…")
        layout.addRow("Nœud de départ :", self.source_combo)
        layout.addRow("Nœud d’arrivée :", self.target_combo)
        layout.addRow("Type :", self.type_combo)
        layout.addRow("Texte :", self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @staticmethod
    def _select_id(combo: QComboBox, node_id: str) -> None:
        index = combo.findData(node_id)
        if index >= 0:
            combo.setCurrentIndex(index)

    def values(self) -> tuple[str, str, str, str]:
        return (
            str(self.source_combo.currentData()),
            str(self.target_combo.currentData()),
            self.type_combo.currentText().strip(),
            self.text_edit.toPlainText(),
        )


@dataclass
class NodeData:
    id: str
    name: str
    type: str
    text: str


class NodeItem(QGraphicsRectItem):
    def __init__(self, data: NodeData, edit_callback: Callable[[str], None]) -> None:
        super().__init__(-70, -28, 140, 56)
        self.data = data
        self.edit_callback = edit_callback
        self.edges: list[EdgeItem] = []
        self.label = QGraphicsSimpleTextItem(self)
        self.label.setBrush(QBrush(Qt.GlobalColor.white))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setZValue(2)
        self.refresh()

    def refresh(self) -> None:
        color = QColor(NODE_COLORS[_stable_index(self.data.type, len(NODE_COLORS))])
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("#f1f1f1") if self.isSelected() else color.lighter(125), 2))
        self.label.setText(self.data.name)
        bounds = self.label.boundingRect()
        self.label.setPos(-bounds.width() / 2, -bounds.height() / 2)
        self.setToolTip(f"Type : {self.data.type or 'sans type'}\n{self.data.text}")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.refresh()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:
        self.edit_callback(self.data.id)
        event.accept()


@dataclass
class EdgeData:
    id: str
    source: str
    target: str
    type: str
    text: str


class EdgeItem(QGraphicsPathItem):
    def __init__(self, data: EdgeData, source: NodeItem, target: NodeItem, edit_callback: Callable[[str], None]) -> None:
        super().__init__()
        self.data = data
        self.source = source
        self.target = target
        self.edit_callback = edit_callback
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(1)
        source.edges.append(self)
        target.edges.append(self)
        self.refresh()
        self.update_path()

    def refresh(self) -> None:
        index = _stable_index(self.data.type, len(EDGE_COLORS))
        color = QColor(EDGE_COLORS[index])
        width = 4 if self.isSelected() else 2
        self.setPen(QPen(color, width, EDGE_STYLES[index % len(EDGE_STYLES)], Qt.PenCapStyle.RoundCap))
        self.setToolTip(f"Type : {self.data.type or 'sans type'}\n{self.data.text}")

    def update_path(self) -> None:
        start = self.source.scenePos()
        end = self.target.scenePos()
        path = QPainterPath(start)
        if self.source is self.target:
            path.cubicTo(start + QPointF(90, -100), start + QPointF(-90, -100), start)
        else:
            delta = end - start
            normal = QPointF(-delta.y(), delta.x())
            length = max((delta.x() ** 2 + delta.y() ** 2) ** 0.5, 1)
            bend = normal / length * 18
            midpoint = (start + end) / 2 + bend
            path.quadTo(midpoint, end)
        self.setPath(path)

    def shape(self) -> QPainterPath:
        stroker = QPainterPath()
        from PySide6.QtGui import QPainterPathStroker
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(14)
        return path_stroker.createStroke(self.path()).united(stroker)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.refresh()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:
        self.edit_callback(self.data.id)
        event.accept()


class GraphView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#202124")))

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class GraphWindow(QMainWindow):
    def __init__(self, project_root: Path, stylesheet: str = "") -> None:
        super().__init__()
        self.graph_dir = project_root / "graphe"
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        self.current_path: Path | None = None
        self.nodes: dict[str, NodeItem] = {}
        self.edges: dict[str, EdgeItem] = {}
        self._next_id = 1
        self.setWindowTitle("Graphe")
        self.resize(1100, 760)
        if stylesheet:
            self.setStyleSheet(stylesheet)

        central = QWidget()
        layout = QVBoxLayout(central)
        toolbar = QHBoxLayout()
        for text, callback in (
            ("Nouveau nœud", self.create_node),
            ("Nouvelle arête", self.create_edge),
            ("Modifier", self.edit_selected),
            ("Supprimer", self.delete_selected),
            ("Nouveau graphe", self.clear_graph),
            ("Sauvegarder", self.save_graph),
            ("Charger", self.load_graph),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        hint = QLabel("Double-cliquez un élément pour le modifier · molette pour zoomer")
        hint.setStyleSheet("color: #c9c9c9; padding: 4px;")
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(QRectF(-2000, -1500, 4000, 3000))
        self.view = GraphView(self.scene)
        layout.addLayout(toolbar)
        layout.addWidget(hint)
        layout.addWidget(self.view, 1)
        self.setCentralWidget(central)

    def _new_id(self, prefix: str) -> str:
        result = f"{prefix}{self._next_id}"
        self._next_id += 1
        return result

    def node_types(self) -> set[str]:
        return {item.data.type for item in self.nodes.values() if item.data.type}

    def edge_types(self) -> set[str]:
        return {item.data.type for item in self.edges.values() if item.data.type}

    def create_node(self) -> None:
        dialog = NodeDialog(self.node_types(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, node_type, text = dialog.values()
        data = NodeData(self._new_id("n"), name, node_type, text)
        item = NodeItem(data, self.edit_node)
        offset = len(self.nodes) * 35
        item.setPos(-180 + offset % 540, -120 + (offset // 540) * 110)
        self.nodes[data.id] = item
        self.scene.addItem(item)

    def edit_node(self, node_id: str) -> None:
        item = self.nodes[node_id]
        dialog = NodeDialog(self.node_types(), item.data.name, item.data.type, item.data.text, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            item.data.name, item.data.type, item.data.text = dialog.values()
            item.refresh()

    def create_edge(self) -> None:
        if not self.nodes:
            QMessageBox.information(self, "Arête", "Créez d’abord au moins un nœud.")
            return
        node_choices = [(item.data.id, item.data.name) for item in self.nodes.values()]
        selected_nodes = [item for item in self.scene.selectedItems() if isinstance(item, NodeItem)]
        source_id = selected_nodes[0].data.id if selected_nodes else ""
        target_id = selected_nodes[1].data.id if len(selected_nodes) > 1 else ""
        dialog = EdgeDialog(node_choices, self.edge_types(), source_id, target_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source, target, edge_type, text = dialog.values()
        data = EdgeData(self._new_id("e"), source, target, edge_type, text)
        item = EdgeItem(data, self.nodes[source], self.nodes[target], self.edit_edge)
        self.edges[data.id] = item
        self.scene.addItem(item)

    def edit_edge(self, edge_id: str) -> None:
        item = self.edges[edge_id]
        choices = [(node.data.id, node.data.name) for node in self.nodes.values()]
        dialog = EdgeDialog(choices, self.edge_types(), item.data.source, item.data.target, item.data.type, item.data.text, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source, target, edge_type, text = dialog.values()
        if item.source is not self.nodes[source] or item.target is not self.nodes[target]:
            item.source.edges.remove(item)
            item.target.edges.remove(item)
            item.source = self.nodes[source]
            item.target = self.nodes[target]
            item.source.edges.append(item)
            item.target.edges.append(item)
        item.data.source, item.data.target, item.data.type, item.data.text = source, target, edge_type, text
        item.refresh()
        item.update_path()

    def edit_selected(self) -> None:
        selected = self.scene.selectedItems()
        if len(selected) != 1:
            QMessageBox.information(self, "Modifier", "Sélectionnez un seul nœud ou une seule arête.")
        elif isinstance(selected[0], NodeItem):
            self.edit_node(selected[0].data.id)
        elif isinstance(selected[0], EdgeItem):
            self.edit_edge(selected[0].data.id)

    def delete_selected(self) -> None:
        selected = self.scene.selectedItems()
        node_ids = {item.data.id for item in selected if isinstance(item, NodeItem)}
        edge_ids = {item.data.id for item in selected if isinstance(item, EdgeItem)}
        edge_ids.update(edge_id for edge_id, edge in self.edges.items() if edge.data.source in node_ids or edge.data.target in node_ids)
        for edge_id in edge_ids:
            edge = self.edges.pop(edge_id, None)
            if edge is not None:
                if edge in edge.source.edges:
                    edge.source.edges.remove(edge)
                if edge in edge.target.edges:
                    edge.target.edges.remove(edge)
                self.scene.removeItem(edge)
        for node_id in node_ids:
            node = self.nodes.pop(node_id, None)
            if node is not None:
                self.scene.removeItem(node)

    def clear_graph(self) -> None:
        if (self.nodes or self.edges) and QMessageBox.question(self, "Nouveau graphe", "Effacer le graphe actuel ?") != QMessageBox.StandardButton.Yes:
            return
        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()
        self.current_path = None
        self._next_id = 1
        self.setWindowTitle("Graphe")

    def _serialize(self) -> dict:
        return {
            "version": 1,
            "nodes": [
                {"id": node.data.id, "name": node.data.name, "type": node.data.type, "text": node.data.text, "x": node.x(), "y": node.y()}
                for node in self.nodes.values()
            ],
            "edges": [vars(edge.data) for edge in self.edges.values()],
        }

    def save_graph(self) -> None:
        path = self.current_path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(self, "Sauvegarder le graphe", str(self.graph_dir / "graphe.json"), "Graphes JSON (*.json)")
            if not filename:
                return
            path = Path(filename)
            if path.suffix.lower() != ".json":
                path = path.with_suffix(".json")
        try:
            path.write_text(json.dumps(self._serialize(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Sauvegarde impossible", str(exc))
            return
        self.current_path = path
        self.setWindowTitle(f"Graphe — {path.stem}")

    def load_graph(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Charger un graphe", str(self.graph_dir), "Graphes JSON (*.json)")
        if not filename:
            return
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            nodes = payload.get("nodes", [])
            edges = payload.get("edges", [])
            if not isinstance(nodes, list) or not isinstance(edges, list):
                raise ValueError("Format de graphe invalide.")
            self.scene.clear()
            self.nodes.clear()
            self.edges.clear()
            numeric_ids: list[int] = []
            for raw in nodes:
                data = NodeData(str(raw["id"]), str(raw.get("name", "")), str(raw.get("type", "")), str(raw.get("text", "")))
                item = NodeItem(data, self.edit_node)
                item.setPos(float(raw.get("x", 0)), float(raw.get("y", 0)))
                self.nodes[data.id] = item
                self.scene.addItem(item)
                if data.id[1:].isdigit():
                    numeric_ids.append(int(data.id[1:]))
            for raw in edges:
                data = EdgeData(str(raw["id"]), str(raw["source"]), str(raw["target"]), str(raw.get("type", "")), str(raw.get("text", "")))
                if data.source not in self.nodes or data.target not in self.nodes:
                    raise ValueError(f"L’arête {data.id} référence un nœud absent.")
                item = EdgeItem(data, self.nodes[data.source], self.nodes[data.target], self.edit_edge)
                self.edges[data.id] = item
                self.scene.addItem(item)
                if data.id[1:].isdigit():
                    numeric_ids.append(int(data.id[1:]))
            self._next_id = max(numeric_ids, default=0) + 1
        except Exception as exc:
            QMessageBox.critical(self, "Chargement impossible", str(exc))
            return
        self.current_path = Path(filename)
        self.setWindowTitle(f"Graphe — {self.current_path.stem}")
        if self.nodes:
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80), Qt.AspectRatioMode.KeepAspectRatio)
