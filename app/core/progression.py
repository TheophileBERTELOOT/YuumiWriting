from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
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
    words_changed: int
    total_words: int
    files: dict[str, int]

    @classmethod
    def from_dict(cls, value: dict) -> "ProgressRecord":
        return cls(
            str(value["date"]),
            max(int(value.get("words_written", 0)), 0),
            max(int(value.get("words_changed", 0)), 0),
            max(int(value.get("total_words", 0)), 0),
            {str(path): max(int(count), 0) for path, count in value.get("files", {}).items()},
        )

    def to_dict(self) -> dict:
        return {
            "date": self.day,
            "words_written": self.words_written,
            "words_changed": self.words_changed,
            "total_words": self.total_words,
            "files": self.files,
        }


class ProgressTracker:
    def __init__(self, project_root: Path, extensions: tuple[str, ...]) -> None:
        self.project_root = project_root.resolve()
        self.extensions = extensions
        self.progress_dir = self.project_root / "Progression"
        self.log_path = self.progress_dir / "progression.jsonl"
        self.state_path = self.progress_dir / "progression_state.json"

    def _file_snapshots(self) -> dict[str, list[str]]:
        snapshots: dict[str, list[str]] = {}
        for path in sorted(self.project_root.rglob("*")):
            if (
                path.is_file()
                and path.suffix.lower() in self.extensions
                and not any(part.casefold() in IGNORED_DIRECTORIES for part in path.parts)
            ):
                relative = path.relative_to(self.project_root).as_posix()
                content = path.read_text(encoding="utf-8", errors="replace")
                snapshots[relative] = WORD_RE.findall(content)
        return snapshots

    def _file_counts(self, snapshots: dict[str, list[str]]) -> dict[str, int]:
        return {path: len(words) for path, words in snapshots.items()}

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
        snapshots = self._file_snapshots()
        counts = self._file_counts(snapshots)
        total = sum(counts.values())
        records = self.load_records()
        previous_counts = records[-1].files if records else counts
        previous_snapshots = self._load_state()
        additions = sum(max(count - previous_counts.get(path, 0), 0) for path, count in counts.items())
        changed_words = self._changed_words(previous_snapshots, snapshots) if previous_snapshots else 0

        if records and records[-1].day == current_day:
            records[-1].words_written += additions
            records[-1].words_changed += changed_words
            records[-1].total_words = total
            records[-1].files = counts
            result = records[-1]
        else:
            result = ProgressRecord(current_day, additions, changed_words, total, counts)
            records.append(result)

        content = "\n".join(json.dumps(record.to_dict(), ensure_ascii=False) for record in records) + "\n"
        self.log_path.write_text(content, encoding="utf-8")
        self._save_state(snapshots)
        return result

    def remap_paths(self, path_mapping: dict[Path, Path]) -> None:
        if not path_mapping:
            return
        relative_mapping = {
            old.resolve().relative_to(self.project_root).as_posix(): new.resolve().relative_to(self.project_root).as_posix()
            for old, new in path_mapping.items()
            if old.resolve().is_relative_to(self.project_root)
            and new.resolve().is_relative_to(self.project_root)
        }
        if not relative_mapping:
            return

        records = self.load_records()
        for record in records:
            record.files = {
                relative_mapping.get(path, path): count
                for path, count in record.files.items()
            }
        if records:
            content = "\n".join(json.dumps(record.to_dict(), ensure_ascii=False) for record in records) + "\n"
            self.log_path.write_text(content, encoding="utf-8")

        state = self._load_state()
        if state:
            self._save_state(
                {
                    relative_mapping.get(path, path): words
                    for path, words in state.items()
                }
            )

    def _load_state(self) -> dict[str, list[str]]:
        if not self.state_path.exists():
            return {}
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        files = raw.get("files", {}) if isinstance(raw, dict) else {}
        if not isinstance(files, dict):
            return {}
        return {
            str(path): [str(word) for word in words]
            for path, words in files.items()
            if isinstance(words, list)
        }

    def _save_state(self, snapshots: dict[str, list[str]]) -> None:
        self.state_path.write_text(
            json.dumps({"version": 1, "files": snapshots}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _changed_words(
        self,
        previous: dict[str, list[str]],
        current: dict[str, list[str]],
    ) -> int:
        total = 0
        for path in sorted(set(previous) | set(current)):
            old_words = previous.get(path, [])
            new_words = current.get(path, [])
            if not old_words:
                total += len(new_words)
                continue
            if not new_words:
                total += len(old_words)
                continue
            matcher = SequenceMatcher(None, old_words, new_words, autojunk=False)
            for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
                if tag == "equal":
                    continue
                total += max(old_end - old_start, new_end - new_start)
        return total
