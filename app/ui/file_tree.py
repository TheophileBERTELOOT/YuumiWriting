from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QFileSystemModel, QMessageBox, QTreeView

from app.core.chapter_ordering import ChapterOrderingError, renumber_chapters
from app.core.latex_exporter import LatexProjectExporter


class FileTree(QTreeView):
    file_selected = Signal(Path)
    files_reordered = Signal(object)

    def __init__(self, project_root: Path, accepted_extensions: tuple[str, ...]) -> None:
        super().__init__()
        self.accepted_extensions = accepted_extensions
        self._dragged_path: Path | None = None

        self.model = QFileSystemModel(self)
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

        self.doubleClicked.connect(self._on_double_clicked)
        self.set_project_root(project_root)

    def set_project_root(self, project_root: Path) -> None:
        """Change le dossier affiché dans l'arborescence de gauche."""
        self.project_root = project_root.resolve()
        self.model.setRootPath(str(self.project_root))
        self.setRootIndex(self.model.index(str(self.project_root)))

    def _on_double_clicked(self, index) -> None:  # Qt index type
        path = Path(self.model.filePath(index))
        if path.is_file() and path.suffix.lower() in self.accepted_extensions:
            self.file_selected.emit(path)

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
