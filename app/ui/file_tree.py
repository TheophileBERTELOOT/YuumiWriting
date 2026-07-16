from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QAbstractItemView, QFileSystemModel, QMessageBox, QTreeView

from app.core.chapter_ordering import ChapterOrderingError, renumber_chapters
from app.core.latex_exporter import LatexProjectExporter


class FileTree(QTreeView):
    file_selected = Signal(Path)
    file_renamed = Signal(Path, Path)
    files_reordered = Signal(object)

    def __init__(self, project_root: Path, accepted_extensions: tuple[str, ...]) -> None:
        super().__init__()
        self.accepted_extensions = accepted_extensions
        self._dragged_path: Path | None = None
        self._pending_click_path: Path | None = None
        self._ignore_click_after_double = False
        self._single_click_timer = QTimer(self)
        self._single_click_timer.setSingleShot(True)
        self._single_click_timer.setInterval(self._double_click_interval())
        self._single_click_timer.timeout.connect(self._emit_pending_click)
        self._double_click_suppression_timer = QTimer(self)
        self._double_click_suppression_timer.setSingleShot(True)
        self._double_click_suppression_timer.setInterval(self._double_click_interval())
        self._double_click_suppression_timer.timeout.connect(self._clear_double_click_suppression)

        self.model = QFileSystemModel(self)
        self.model.setReadOnly(False)
        self.model.fileRenamed.connect(self._on_file_renamed)
        self.setModel(self.model)

        self.setHeaderHidden(False)
        self.setColumnWidth(0, 260)
        for col in range(1, 4):
            self.hideColumn(col)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)
        self.set_project_root(project_root)

    def set_project_root(self, project_root: Path) -> None:
        """Change le dossier affiché dans l'arborescence de gauche."""
        self.project_root = project_root.resolve()
        self.model.setRootPath(str(self.project_root))
        self.setRootIndex(self.model.index(str(self.project_root)))

    def _on_double_clicked(self, index) -> None:  # Qt index type
        self._single_click_timer.stop()
        self._pending_click_path = None
        self._ignore_click_after_double = True
        self._double_click_suppression_timer.start()
        if not index.isValid():
            return
        index = index.siblingAtColumn(0)
        path = Path(self.model.filePath(index))
        if self._can_rename(path):
            self.setCurrentIndex(index)
            self.edit(index)

    def _on_clicked(self, index) -> None:  # Qt index type
        if self._ignore_click_after_double:
            self._ignore_click_after_double = False
            self._double_click_suppression_timer.stop()
            return
        if not index.isValid():
            return
        index = index.siblingAtColumn(0)
        path = Path(self.model.filePath(index))
        self._pending_click_path = path if self._can_open(path) else None
        if self._pending_click_path is not None:
            self._single_click_timer.start()

    def _emit_pending_click(self) -> None:
        path = self._pending_click_path
        self._pending_click_path = None
        if path is not None and self._can_open(path):
            self.file_selected.emit(path)

    def _clear_double_click_suppression(self) -> None:
        self._ignore_click_after_double = False

    def keyPressEvent(self, event) -> None:  # Qt key event
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            path = self._current_file_path()
            if path is not None:
                self.file_selected.emit(path)
                event.accept()
                return
        super().keyPressEvent(event)

    def _on_file_renamed(self, directory: str, old_name: str, new_name: str) -> None:
        old_path = Path(directory) / old_name
        new_path = Path(directory) / new_name
        self.file_renamed.emit(old_path, new_path)

    def startDrag(self, supported_actions) -> None:  # Qt drag actions
        index = self.currentIndex()
        path = Path(self.model.filePath(index))
        self._dragged_path = path if self._is_numbered_chapter(path) else None
        if self._dragged_path is not None:
            super().startDrag(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._dragged_path is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        target = self._path_at(event.position().toPoint())
        if self._dragged_path is not None and target is not None and self._is_numbered_chapter(target):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        target = self._path_at(event.position().toPoint())
        dragged = self._dragged_path
        self._dragged_path = None
        if dragged is None or target is None or not self._is_numbered_chapter(target):
            event.ignore()
            return
        try:
            chapter_paths = LatexProjectExporter(
                self.project_root,
                self.accepted_extensions,
            ).source_paths()
            mapping = renumber_chapters(chapter_paths, dragged, target)
        except ChapterOrderingError as exc:
            QMessageBox.warning(self, "Réordonner les chapitres", str(exc))
            event.ignore()
            return
        except Exception as exc:
            QMessageBox.critical(self, "Réordonner les chapitres", str(exc))
            event.ignore()
            return

        self.model.setRootPath(str(self.project_root))
        if mapping:
            self.files_reordered.emit(mapping)
            moved_to = mapping.get(dragged.resolve())
            if moved_to is not None:
                self.setCurrentIndex(self.model.index(str(moved_to)))
        event.acceptProposedAction()

    def _path_at(self, point) -> Path | None:
        index = self.indexAt(point)
        if not index.isValid():
            return None
        return Path(self.model.filePath(index))

    def _is_numbered_chapter(self, path: Path) -> bool:
        if not path.is_file() or path.suffix.lower() not in self.accepted_extensions:
            return False
        return path.resolve() in {
            chapter.resolve()
            for chapter in LatexProjectExporter(self.project_root, self.accepted_extensions).source_paths()
        }

    def _can_rename(self, path: Path) -> bool:
        return self._can_open(path) and path != self.project_root

    def _can_open(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in self.accepted_extensions

    def _current_file_path(self) -> Path | None:
        index = self.currentIndex()
        if not index.isValid():
            return None
        path = Path(self.model.filePath(index))
        if self._can_open(path):
            return path
        return None

    def _double_click_interval(self) -> int:
        app = QApplication.instance()
        if app is None:
            return 250
        return app.styleHints().mouseDoubleClickInterval()
