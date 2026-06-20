from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


DAY_WIDTH = 28
ROW_HEIGHT = 48
LEFT_MARGIN = 250
TOP_MARGIN = 70


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


@dataclass
class EventData:
    id: str
    name: str
    start: str
    duration: int
    text: str
    parent: str | None = None

    @property
    def start_date(self) -> date:
        return date.fromisoformat(self.start)

    @property
    def end_date(self) -> date:
        return self.start_date + timedelta(days=max(self.duration, 1))


@dataclass
class LinkData:
    id: str
    source: str
    target: str
    text: str = ""


@dataclass
class MarkerData:
    id: str
    name: str
    day: str
    text: str = ""

    @property
    def marker_date(self) -> date:
        return date.fromisoformat(self.day)


class EventDialog(QDialog):
    def __init__(
        self,
        events: list[EventData],
        current_id: str = "",
        name: str = "",
        start: date | None = None,
        duration: int = 1,
        text: str = "",
        parent_id: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Événement")
        self.resize(470, 390)
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(name)
        self.start_edit = QDateEdit(_to_qdate(start or date.today()))
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("dd/MM/yyyy")
        self.duration_edit = QSpinBox()
        self.duration_edit.setRange(1, 100_000)
        self.duration_edit.setValue(max(duration, 1))
        self.duration_edit.setSuffix(" jour(s)")
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("Aucun — événement principal", None)
        forbidden = self._descendants(events, current_id)
        for event in events:
            if event.id != current_id and event.id not in forbidden:
                self.parent_combo.addItem(event.name, event.id)
        index = self.parent_combo.findData(parent_id)
        if index >= 0:
            self.parent_combo.setCurrentIndex(index)
        self.text_edit = QTextEdit(text)
        self.text_edit.setPlaceholderText("Données, notes ou description de l’événement…")
        layout.addRow("Nom :", self.name_edit)
        layout.addRow("Début :", self.start_edit)
        layout.addRow("Durée :", self.duration_edit)
        layout.addRow("Sous-événement de :", self.parent_combo)
        layout.addRow("Données :", self.text_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @staticmethod
    def _descendants(events: list[EventData], event_id: str) -> set[str]:
        descendants: set[str] = set()
        pending = [event_id]
        while pending:
            parent_id = pending.pop()
            children = [event.id for event in events if event.parent == parent_id]
            descendants.update(children)
            pending.extend(children)
        return descendants

    def values(self) -> tuple[str, str, int, str, str | None]:
        return (
            self.name_edit.text().strip(),
            _from_qdate(self.start_edit.date()).isoformat(),
            self.duration_edit.value(),
            self.text_edit.toPlainText(),
            self.parent_combo.currentData(),
        )

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Nom requis", "Donnez un nom à l’événement.")
            return
        super().accept()


class LinkDialog(QDialog):
    def __init__(self, events: list[EventData], source: str = "", target: str = "", text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lier deux événements")
        layout = QFormLayout(self)
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        for event in events:
            self.source_combo.addItem(event.name, event.id)
            self.target_combo.addItem(event.name, event.id)
        for combo, value in ((self.source_combo, source), (self.target_combo, target)):
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.text_edit = QTextEdit(text)
        self.text_edit.setPlaceholderText("Données ou description de la liaison…")
        layout.addRow("De :", self.source_combo)
        layout.addRow("Vers :", self.target_combo)
        layout.addRow("Données :", self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, str, str]:
        return str(self.source_combo.currentData()), str(self.target_combo.currentData()), self.text_edit.toPlainText()

    def accept(self) -> None:
        if self.source_combo.currentData() == self.target_combo.currentData():
            QMessageBox.warning(self, "Liaison invalide", "Choisissez deux événements différents.")
            return
        super().accept()


class MarkerDialog(QDialog):
    def __init__(self, name: str = "", day: date | None = None, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Marqueur chronologique")
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(name)
        self.day_edit = QDateEdit(_to_qdate(day or date.today()))
        self.day_edit.setCalendarPopup(True)
        self.day_edit.setDisplayFormat("dd/MM/yyyy")
        self.text_edit = QTextEdit(text)
        self.text_edit.setPlaceholderText("Données ou notes associées au marqueur…")
        layout.addRow("Nom :", self.name_edit)
        layout.addRow("Date :", self.day_edit)
        layout.addRow("Données :", self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, str, str]:
        return self.name_edit.text().strip(), _from_qdate(self.day_edit.date()).isoformat(), self.text_edit.toPlainText()

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Nom requis", "Donnez un nom au marqueur.")
            return
        super().accept()


class EditableRect(QGraphicsRectItem):
    def __init__(self, kind: str, object_id: str, callback: Callable[[str], None], rect: QRectF) -> None:
        super().__init__(rect)
        self.kind = kind
        self.object_id = object_id
        self.callback = callback
        self.setData(0, kind)
        self.setData(1, object_id)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def mouseDoubleClickEvent(self, event) -> None:
        self.callback(self.object_id)
        event.accept()


class EditablePath(QGraphicsPathItem):
    def __init__(self, object_id: str, callback: Callable[[str], None], path: QPainterPath) -> None:
        super().__init__(path)
        self.setData(0, "link")
        self.setData(1, object_id)
        self.callback = callback
        self.object_id = object_id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def mouseDoubleClickEvent(self, event) -> None:
        self.callback(self.object_id)
        event.accept()


class TimelineView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#202124")))

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)


class TimelineWindow(QMainWindow):
    def __init__(self, project_root: Path, stylesheet: str = "") -> None:
        super().__init__()
        self.timeline_dir = project_root / "Timeline"
        self.timeline_dir.mkdir(parents=True, exist_ok=True)
        self.current_path: Path | None = None
        self.events: dict[str, EventData] = {}
        self.links: dict[str, LinkData] = {}
        self.markers: dict[str, MarkerData] = {}
        self._next_id = 1
        self.setWindowTitle("Timeline")
        self.resize(1250, 780)
        if stylesheet:
            self.setStyleSheet(stylesheet)

        central = QWidget()
        layout = QVBoxLayout(central)
        toolbar = QHBoxLayout()
        for label, callback in (
            ("Ajouter un événement", self.create_event),
            ("Ajouter un marqueur", self.create_marker),
            ("Lier deux événements", self.create_link),
            ("Modifier", self.edit_selected),
            ("Supprimer", self.delete_selected),
            ("Nouvelle timeline", self.clear_timeline),
            ("Sauvegarder", self.save_timeline),
            ("Charger", self.load_timeline),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        hint = QLabel("Double-cliquez un élément pour le modifier · Ctrl + molette pour zoomer")
        hint.setStyleSheet("color: #c9c9c9; padding: 4px;")
        self.scene = QGraphicsScene(self)
        self.view = TimelineView(self.scene)
        layout.addLayout(toolbar)
        layout.addWidget(hint)
        layout.addWidget(self.view, 1)
        self.setCentralWidget(central)
        self.redraw()

    def _new_id(self, prefix: str) -> str:
        object_id = f"{prefix}{self._next_id}"
        self._next_id += 1
        return object_id

    def _ordered_events(self) -> list[tuple[EventData, int]]:
        result: list[tuple[EventData, int]] = []
        visited: set[str] = set()

        def append_branch(event: EventData, depth: int) -> None:
            if event.id in visited:
                return
            visited.add(event.id)
            result.append((event, depth))
            children = sorted(
                (item for item in self.events.values() if item.parent == event.id),
                key=lambda item: (item.start, item.name.casefold()),
            )
            for child in children:
                append_branch(child, depth + 1)

        roots = sorted(
            (event for event in self.events.values() if not event.parent or event.parent not in self.events),
            key=lambda item: (item.start, item.name.casefold()),
        )
        for root in roots:
            append_branch(root, 0)
        for event in self.events.values():
            append_branch(event, 0)
        return result

    def _date_range(self) -> tuple[date, date]:
        dates = [date.today()]
        for event in self.events.values():
            dates.extend((event.start_date, event.end_date))
        dates.extend(marker.marker_date for marker in self.markers.values())
        first = min(dates) - timedelta(days=2)
        last = max(dates) + timedelta(days=3)
        return first, last

    def redraw(self) -> None:
        self.scene.clear()
        ordered = self._ordered_events()
        first, last = self._date_range()
        days = max((last - first).days, 7)
        height = TOP_MARGIN + max(len(ordered), 1) * ROW_HEIGHT + 80
        width = LEFT_MARGIN + days * DAY_WIDTH + 80
        self.scene.setSceneRect(0, 0, width, height)
        self.scene.addRect(0, 0, width, height, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#202124")))

        for day_index in range(days + 1):
            current = first + timedelta(days=day_index)
            x = LEFT_MARGIN + day_index * DAY_WIDTH
            major = current.weekday() == 0 or day_index == 0
            pen = QPen(QColor("#4a4b50" if major else "#323338"), 1)
            self.scene.addLine(x, 42, x, height, pen)
            if major:
                label = self.scene.addSimpleText(current.strftime("%d/%m/%Y"))
                label.setBrush(QBrush(QColor("#dddddd")))
                label.setPos(x + 3, 16)

        row_positions: dict[str, tuple[float, float, float]] = {}
        for row, (event, depth) in enumerate(ordered):
            y = TOP_MARGIN + row * ROW_HEIGHT
            if row % 2:
                self.scene.addRect(0, y, width, ROW_HEIGHT, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#25262a")))
            name = self.scene.addSimpleText(("   " * depth) + ("↳ " if depth else "") + event.name)
            name.setBrush(QBrush(QColor("#eeeeee")))
            name.setPos(12, y + 14)
            x = LEFT_MARGIN + (event.start_date - first).days * DAY_WIDTH
            bar_width = max(event.duration * DAY_WIDTH, 18)
            rect = QRectF(x, y + 10, bar_width, 28)
            item = EditableRect("event", event.id, self.edit_event, rect)
            color = QColor("#7f6bb3" if event.parent else "#4f86c6")
            item.setBrush(QBrush(color))
            item.setPen(QPen(color.lighter(135), 2))
            item.setToolTip(
                f"{event.name}\nDu {event.start_date.strftime('%d/%m/%Y')} pendant {event.duration} jour(s)\n{event.text}"
            )
            self.scene.addItem(item)
            bar_label = QGraphicsSimpleTextItem(event.name, item)
            bar_label.setBrush(QBrush(Qt.GlobalColor.white))
            bar_label.setPos(6, 5)
            row_positions[event.id] = (x, x + bar_width, y + 24)

        for link in self.links.values():
            if link.source not in row_positions or link.target not in row_positions:
                continue
            _, source_end, source_y = row_positions[link.source]
            target_start, _, target_y = row_positions[link.target]
            path = QPainterPath(QPointF(source_end, source_y))
            elbow = max(source_end + 14, (source_end + target_start) / 2)
            path.lineTo(elbow, source_y)
            path.lineTo(elbow, target_y)
            path.lineTo(target_start, target_y)
            item = EditablePath(link.id, self.edit_link, path)
            item.setPen(QPen(QColor("#d6aa4c"), 3, Qt.PenStyle.DashLine))
            item.setToolTip(link.text or "Liaison entre événements")
            item.setZValue(3)
            self.scene.addItem(item)

        for marker in self.markers.values():
            x = LEFT_MARGIN + (marker.marker_date - first).days * DAY_WIDTH
            rect = QRectF(x - 5, 42, 10, height - 42)
            item = EditableRect("marker", marker.id, self.edit_marker, rect)
            item.setBrush(QBrush(QColor(212, 106, 106, 75)))
            item.setPen(QPen(QColor("#d46a6a"), 2, Qt.PenStyle.DotLine))
            item.setToolTip(f"{marker.name} — {marker.marker_date.strftime('%d/%m/%Y')}\n{marker.text}")
            item.setZValue(4)
            self.scene.addItem(item)
            label = self.scene.addSimpleText(f"◆ {marker.name}")
            label.setBrush(QBrush(QColor("#f08b8b")))
            label.setPos(x + 5, 45)
            label.setZValue(5)

    def create_event(self) -> None:
        dialog = EventDialog(list(self.events.values()), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, start, duration, text, parent_id = dialog.values()
            event = EventData(self._new_id("ev"), name, start, duration, text, parent_id)
            self.events[event.id] = event
            self.redraw()

    def edit_event(self, event_id: str) -> None:
        event = self.events[event_id]
        dialog = EventDialog(list(self.events.values()), event.id, event.name, event.start_date, event.duration, event.text, event.parent, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            event.name, event.start, event.duration, event.text, event.parent = dialog.values()
            self.redraw()

    def create_marker(self) -> None:
        dialog = MarkerDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, day, text = dialog.values()
            marker = MarkerData(self._new_id("mk"), name, day, text)
            self.markers[marker.id] = marker
            self.redraw()

    def edit_marker(self, marker_id: str) -> None:
        marker = self.markers[marker_id]
        dialog = MarkerDialog(marker.name, marker.marker_date, marker.text, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            marker.name, marker.day, marker.text = dialog.values()
            self.redraw()

    def create_link(self) -> None:
        if len(self.events) < 2:
            QMessageBox.information(self, "Liaison", "Créez au moins deux événements.")
            return
        dialog = LinkDialog(list(self.events.values()), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            source, target, text = dialog.values()
            link = LinkData(self._new_id("ln"), source, target, text)
            self.links[link.id] = link
            self.redraw()

    def edit_link(self, link_id: str) -> None:
        link = self.links[link_id]
        dialog = LinkDialog(list(self.events.values()), link.source, link.target, link.text, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            link.source, link.target, link.text = dialog.values()
            self.redraw()

    def edit_selected(self) -> None:
        selected = [item for item in self.scene.selectedItems() if item.data(0)]
        if len(selected) != 1:
            QMessageBox.information(self, "Modifier", "Sélectionnez un événement, un marqueur ou une liaison.")
            return
        kind, object_id = selected[0].data(0), selected[0].data(1)
        {"event": self.edit_event, "marker": self.edit_marker, "link": self.edit_link}[kind](object_id)

    def delete_selected(self) -> None:
        selected = [item for item in self.scene.selectedItems() if item.data(0)]
        if not selected:
            QMessageBox.information(self, "Supprimer", "Sélectionnez au moins un élément.")
            return
        event_ids = {item.data(1) for item in selected if item.data(0) == "event"}
        pending = list(event_ids)
        while pending:
            parent_id = pending.pop()
            children = {event.id for event in self.events.values() if event.parent == parent_id}
            new_children = children - event_ids
            event_ids.update(new_children)
            pending.extend(new_children)
        for event_id in event_ids:
            self.events.pop(event_id, None)
        for item in selected:
            if item.data(0) == "marker":
                self.markers.pop(item.data(1), None)
            elif item.data(0) == "link":
                self.links.pop(item.data(1), None)
        self.links = {
            link_id: link
            for link_id, link in self.links.items()
            if link.source not in event_ids and link.target not in event_ids
        }
        self.redraw()

    def clear_timeline(self) -> None:
        if (self.events or self.links or self.markers) and QMessageBox.question(self, "Nouvelle timeline", "Effacer la timeline actuelle ?") != QMessageBox.StandardButton.Yes:
            return
        self.events.clear()
        self.links.clear()
        self.markers.clear()
        self.current_path = None
        self._next_id = 1
        self.setWindowTitle("Timeline")
        self.redraw()

    def _serialize(self) -> dict:
        return {
            "version": 1,
            "events": [asdict(event) for event in self.events.values()],
            "links": [asdict(link) for link in self.links.values()],
            "markers": [asdict(marker) for marker in self.markers.values()],
        }

    def save_timeline(self) -> None:
        path = self.current_path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(self, "Sauvegarder la timeline", str(self.timeline_dir / "timeline.json"), "Timelines JSON (*.json)")
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
        self.setWindowTitle(f"Timeline — {path.stem}")

    def load_timeline(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Charger une timeline", str(self.timeline_dir), "Timelines JSON (*.json)")
        if not filename:
            return
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            raw_events = payload.get("events", [])
            raw_links = payload.get("links", [])
            raw_markers = payload.get("markers", [])
            events = {str(raw["id"]): EventData(str(raw["id"]), str(raw["name"]), date.fromisoformat(str(raw["start"])).isoformat(), max(int(raw["duration"]), 1), str(raw.get("text", "")), str(raw["parent"]) if raw.get("parent") else None) for raw in raw_events}
            links = {str(raw["id"]): LinkData(str(raw["id"]), str(raw["source"]), str(raw["target"]), str(raw.get("text", ""))) for raw in raw_links}
            markers = {str(raw["id"]): MarkerData(str(raw["id"]), str(raw["name"]), date.fromisoformat(str(raw["day"])).isoformat(), str(raw.get("text", ""))) for raw in raw_markers}
            if any(link.source not in events or link.target not in events for link in links.values()):
                raise ValueError("Une liaison référence un événement absent.")
            if any(event.parent and event.parent not in events for event in events.values()):
                raise ValueError("Un sous-événement référence un parent absent.")
        except Exception as exc:
            QMessageBox.critical(self, "Chargement impossible", str(exc))
            return
        self.events, self.links, self.markers = events, links, markers
        numeric_ids = [int(''.join(char for char in object_id if char.isdigit())) for object_id in (*events, *links, *markers) if any(char.isdigit() for char in object_id)]
        self._next_id = max(numeric_ids, default=0) + 1
        self.current_path = Path(filename)
        self.setWindowTitle(f"Timeline — {self.current_path.stem}")
        self.redraw()
