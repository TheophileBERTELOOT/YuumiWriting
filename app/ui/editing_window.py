from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core.editing_progress import EditingProgressTracker


class EditingWindow(QMainWindow):
    def __init__(self, project_root: Path, extensions: tuple[str, ...], stylesheet: str = "") -> None:
        super().__init__()
        self.tracker = EditingProgressTracker(project_root, extensions)
        self.rows: dict[str, tuple[QComboBox, QSlider, QLabel]] = {}
        self.setWindowTitle(f"Édition des chapitres - {project_root.name}")
        self.resize(980, 720)
        self.setStyleSheet(
            (stylesheet or "")
            + """
            QMainWindow {
                background: #202124;
            }
            QWidget#editingRoot,
            QWidget#editingGrid {
                background: #202124;
            }
            QWidget#editingRow {
                background: #2b2d33;
                border: 1px solid #3b3e47;
                border-radius: 6px;
            }
            QLabel#chapterName {
                color: #f4f1ea;
                font-weight: 700;
            }
            QLabel#chapterPath {
                color: #b9bdc8;
            }
            QLabel#sliderChapterName {
                color: #f4f1ea;
                font-weight: 700;
            }
            QLabel#percentLabel {
                color: #f4f1ea;
                font-weight: 700;
            }
            QComboBox {
                background: #f4f1ea;
                color: #1f2024;
                border: 1px solid #c9c0ad;
                border-radius: 4px;
                padding: 5px 8px;
            }
            QPushButton {
                background: #7ca6d9;
                color: #111318;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #95b8e4;
            }
            QSlider::groove:horizontal {
                background: #3b3e47;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #76b37a;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #f4f1ea;
                border: 2px solid #76b37a;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            """
        )

        central = QWidget()
        central.setObjectName("editingRoot")
        layout = QVBoxLayout(central)
        header = QHBoxLayout()
        title = QLabel("<h2>Édition des chapitres</h2>")
        title.setStyleSheet("color: #f2f2f2;")
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh_rows)
        header.addWidget(title, 1)
        header.addWidget(refresh)
        layout.addLayout(header)

        self.grid_container = QWidget()
        self.grid_container.setObjectName("editingGrid")
        self.grid = QGridLayout(self.grid_container)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(8)
        self.grid.setColumnStretch(0, 3)
        self.grid.setColumnStretch(1, 2)
        self.grid.setColumnStretch(2, 4)
        self.grid.setColumnStretch(3, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, 1)
        self.setCentralWidget(central)
        self.refresh_rows()

    def refresh_rows(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rows.clear()

        try:
            data = self.tracker.load_data()
            states = self.tracker.chapter_states()
        except Exception as exc:
            QMessageBox.critical(self, "Suivi d'édition invalide", str(exc))
            return

        stages = list(data["stages"])
        headers = ["Chapitre", "Statut", "Completion de l'étape", "", ""]
        for column, header in enumerate(headers):
            label = QLabel(f"<b>{header}</b>")
            label.setStyleSheet("color: #eeeeee;")
            self.grid.addWidget(label, 0, column)

        if not states:
            empty = QLabel("Aucun chapitre numéroté trouvé.")
            empty.setStyleSheet("color: #d6aa4c;")
            self.grid.addWidget(empty, 1, 0, 1, 4)
            return

        for row, state in enumerate(states, 1):
            row_frame = QWidget()
            row_frame.setObjectName("editingRow")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(10, 8, 10, 8)
            row_layout.setSpacing(10)

            chapter_cell = QWidget()
            chapter_layout = QVBoxLayout(chapter_cell)
            chapter_layout.setContentsMargins(0, 0, 0, 0)
            chapter_layout.setSpacing(2)
            chapter_name = QLabel(Path(state.path).stem.replace("_", " "))
            chapter_name.setObjectName("chapterName")
            chapter_path = QLabel(state.path)
            chapter_path.setObjectName("chapterPath")
            chapter_path.setWordWrap(True)
            chapter_layout.addWidget(chapter_name)
            chapter_layout.addWidget(chapter_path)

            status_box = QComboBox()
            status_box.addItems(stages)
            status_box.setCurrentText(state.status)

            slider_cell = QWidget()
            slider_layout = QVBoxLayout(slider_cell)
            slider_layout.setContentsMargins(0, 0, 0, 0)
            slider_layout.setSpacing(4)
            slider_chapter_name = QLabel(f"{Path(state.path).stem.replace('_', ' ')}")
            slider_chapter_name.setObjectName("sliderChapterName")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setSingleStep(5)
            slider.setPageStep(10)
            slider.setValue(state.completion)
            slider_layout.addWidget(slider_chapter_name)
            slider_layout.addWidget(slider)

            percent = QLabel(f"{state.completion}%")
            percent.setObjectName("percentLabel")
            percent.setMinimumWidth(48)
            percent.setAlignment(Qt.AlignmentFlag.AlignCenter)

            save = QPushButton("OK")
            save.clicked.connect(lambda checked=False, path=state.path: self._save_row(path))
            slider.valueChanged.connect(lambda value, label=percent: label.setText(f"{value}%"))
            status_box.currentTextChanged.connect(
                lambda status, path=state.path, slider=slider: self._status_changed(path, status, slider)
            )

            self.rows[state.path] = (status_box, slider, percent)
            row_layout.addWidget(chapter_cell, 3)
            row_layout.addWidget(status_box, 2)
            row_layout.addWidget(slider_cell, 4)
            row_layout.addWidget(percent)
            row_layout.addWidget(save)
            self.grid.addWidget(row_frame, row, 0, 1, 5)

        self.grid.setRowStretch(len(states) + 1, 1)

    def _status_changed(self, path: str, status: str, slider: QSlider) -> None:
        if status == "Non relu":
            slider.setValue(0)
        elif status == "Verrouillé":
            slider.setValue(100)
        self._save_row(path)

    def _save_row(self, path: str) -> None:
        row = self.rows.get(path)
        if row is None:
            return
        status_box, slider, _ = row
        try:
            self.tracker.update_chapter(path, status_box.currentText(), slider.value())
        except Exception as exc:
            QMessageBox.critical(self, "Sauvegarde impossible", str(exc))
