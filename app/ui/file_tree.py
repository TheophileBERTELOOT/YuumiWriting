from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class FileTree(QTreeView):
    file_selected = Signal(Path)

    def __init__(self, project_root: Path, accepted_extensions: tuple[str, ...]) -> None:
        super().__init__()
        self.accepted_extensions = accepted_extensions

        self.model = QFileSystemModel(self)
        self.setModel(self.model)

        self.setHeaderHidden(False)
        self.setColumnWidth(0, 260)
        for col in range(1, 4):
            self.hideColumn(col)

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
