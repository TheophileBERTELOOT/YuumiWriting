from __future__ import annotations

import uuid
import re
from pathlib import Path


NUMBER_RE = re.compile(r"\d+")


class ChapterOrderingError(RuntimeError):
    pass


def renumber_chapters(
    ordered_paths: list[Path],
    dragged_path: Path,
    target_path: Path,
) -> dict[Path, Path]:
    paths = [path.resolve() for path in ordered_paths]
    dragged_path = dragged_path.resolve()
    target_path = target_path.resolve()
    if dragged_path not in paths or target_path not in paths:
        raise ChapterOrderingError("Le fichier déplacé et la cible doivent être des chapitres numérotés.")
    if dragged_path == target_path:
        return {}

    paths.remove(dragged_path)
    target_index = paths.index(target_path)
    paths.insert(target_index, dragged_path)

    final_paths = [_renumbered_path(path, index) for index, path in enumerate(paths, 1)]
    return _apply_renames(paths, final_paths)


def _renumbered_path(path: Path, number: int) -> Path:
    match = NUMBER_RE.search(path.stem)
    if match is None:
        raise ChapterOrderingError(f"Le fichier n'a pas de numéro de chapitre : {path.name}")
    old_number = match.group(0)
    new_number = str(number).zfill(len(old_number))
    new_stem = path.stem[: match.start()] + new_number + path.stem[match.end() :]
    return path.with_name(new_stem + path.suffix)


def _apply_renames(old_paths: list[Path], final_paths: list[Path]) -> dict[Path, Path]:
    mapping = {
        old: new
        for old, new in zip(old_paths, final_paths)
        if old != new
    }
    if not mapping:
        return {}

    final_targets = set(mapping.values())
    moving_sources = set(mapping.keys())
    for target in final_targets:
        if target.exists() and target not in moving_sources:
            raise ChapterOrderingError(f"Impossible de renommer : {target.name} existe déjà.")

    temporary_paths: dict[Path, Path] = {}
    token = uuid.uuid4().hex
    for index, old_path in enumerate(mapping):
        temporary = old_path.with_name(f".yuumi-renumber-{token}-{index}{old_path.suffix}")
        old_path.rename(temporary)
        temporary_paths[temporary] = old_path

    completed: dict[Path, Path] = {}
    try:
        for temporary, old_path in temporary_paths.items():
            final_path = mapping[old_path]
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.rename(final_path)
            completed[old_path] = final_path
    except Exception:
        for temporary, old_path in temporary_paths.items():
            if temporary.exists() and not old_path.exists():
                temporary.rename(old_path)
        raise
    return completed
