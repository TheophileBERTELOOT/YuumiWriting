from __future__ import annotations

from pathlib import Path


class DocumentManager:
    """Gestion simple du document courant.

    Cette classe est volontairement indépendante de Qt pour rester testable.
    """

    def __init__(self) -> None:
        self.current_path: Path | None = None
        self.is_dirty: bool = False

    def open_file(self, path: Path) -> str:
        path = path.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {path}")
        if not path.is_file():
            raise IsADirectoryError(f"Ce chemin n'est pas un fichier: {path}")

        content = path.read_text(encoding="utf-8")
        self.current_path = path
        self.is_dirty = False
        return content

    def save(self, content: str) -> Path:
        if self.current_path is None:
            raise ValueError("Aucun fichier courant. Utilise save_as().")
        self.current_path.write_text(content, encoding="utf-8")
        self.is_dirty = False
        return self.current_path

    def save_as(self, path: Path, content: str) -> Path:
        path = path.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.current_path = path
        self.is_dirty = False
        return path

    def mark_dirty(self) -> None:
        self.is_dirty = True

    def new_document(self) -> None:
        self.current_path = None
        self.is_dirty = False
