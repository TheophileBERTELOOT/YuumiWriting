from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
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
WORD_RE = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*|\d+", re.UNICODE)


@dataclass
class ProgressRecord:
    day: str
    words_written: int
    total_words: int
    files: dict[str, int]

    @classmethod
    def from_dict(cls, value: dict) -> "ProgressRecord":
        return cls(
            str(value["date"]),
            max(int(value.get("words_written", 0)), 0),
            max(int(value.get("total_words", 0)), 0),
            {str(path): max(int(count), 0) for path, count in value.get("files", {}).items()},
        )

    def to_dict(self) -> dict:
        return {
            "date": self.day,
            "words_written": self.words_written,
            "total_words": self.total_words,
            "files": self.files,
        }


class ProgressTracker:
    def __init__(self, project_root: Path, extensions: tuple[str, ...]) -> None:
        self.project_root = project_root.resolve()
        self.extensions = extensions
        self.progress_dir = self.project_root / "Progression"
        self.log_path = self.progress_dir / "progression.jsonl"

    def _file_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in sorted(self.project_root.rglob("*")):
            if (
                path.is_file()
                and path.suffix.lower() in self.extensions
                and not any(part.casefold() in IGNORED_DIRECTORIES for part in path.parts)
            ):
                relative = path.relative_to(self.project_root).as_posix()
                content = path.read_text(encoding="utf-8", errors="replace")
                counts[relative] = len(WORD_RE.findall(content))
        return counts

    def load_records(self) -> list[ProgressRecord]:
        if not self.log_path.exists():
            return []
        records: list[ProgressRecord] = []
        for line_number, line in enumerate(self.log_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(ProgressRecord.from_dict(json.loads(line)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Ligne {line_number} invalide dans {self.log_path.name}.") from exc
        return sorted(records, key=lambda record: record.day)

    def record_save(self, today: date | None = None) -> ProgressRecord:
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        current_day = (today or date.today()).isoformat()
        counts = self._file_counts()
        total = sum(counts.values())
        records = self.load_records()
        previous_counts = records[-1].files if records else counts
        additions = sum(max(count - previous_counts.get(path, 0), 0) for path, count in counts.items())

        if records and records[-1].day == current_day:
            records[-1].words_written += additions
            records[-1].total_words = total
            records[-1].files = counts
            result = records[-1]
        else:
            result = ProgressRecord(current_day, additions, total, counts)
            records.append(result)

        content = "\n".join(json.dumps(record.to_dict(), ensure_ascii=False) for record in records) + "\n"
        self.log_path.write_text(content, encoding="utf-8")
        return result
