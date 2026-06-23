from __future__ import annotations

from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "graphe",
    "timeline",
    "progression",
    "analysesllm",
}


def iter_text_files(root: Path, extensions: tuple[str, ...]) -> list[Path]:
    resolved_root = root.resolve()
    return sorted(
        path
        for path in resolved_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in extensions
        and not any(
            part.casefold() in IGNORED_DIRECTORIES
            for part in path.relative_to(resolved_root).parts[:-1]
        )
    )
