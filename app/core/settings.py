from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    autosave_enabled: bool = False
    autosave_interval_ms: int = 30_000
    accepted_extensions: tuple[str, ...] = (".txt", ".md", ".tex")
    default_project_root: Path = Path.cwd()
