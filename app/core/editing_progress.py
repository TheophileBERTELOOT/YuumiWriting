from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.latex_exporter import LatexProjectExporter


EDITING_PROGRESS_FILENAME = "edition_progress.json"

DEFAULT_EDITING_STAGES = [
    "Non relu",
    "Diagnostic effectué",
    "Révision structurelle",
    "Révision des scènes",
    "Révision stylistique",
    "Correction linguistique",
    "Vérification de continuité",
    "Lecture finale",
    "Verrouillé",
]

DEFAULT_PHASE_WEIGHTS = {
    "Diagnostic effectué": 10,
    "Révision structurelle": 25,
    "Révision des scènes": 20,
    "Révision stylistique": 20,
    "Correction linguistique": 10,
    "Vérification de continuité": 10,
    "Lecture finale": 5,
}


@dataclass(slots=True)
class ChapterEditingState:
    path: str
    status: str
    completion: int


@dataclass(slots=True)
class EditingPhaseSummary:
    name: str
    weight: int
    average_completion: float
    chapter_count: int


@dataclass(slots=True)
class EditingSummary:
    chapter_count: int
    overall_completion: float
    phase_summaries: list[EditingPhaseSummary]
    status_counts: dict[str, int]


class EditingProgressTracker:
    def __init__(self, project_root: Path, extensions: tuple[str, ...]) -> None:
        self.project_root = project_root.resolve()
        self.extensions = extensions
        self.progress_dir = self.project_root / "Progression"
        self.path = self.progress_dir / EDITING_PROGRESS_FILENAME

    def load_data(self) -> dict:
        if not self.path.exists():
            return self._default_data()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self.path.name} n'est pas un JSON valide.") from exc
        return self._normalized_data(raw)

    def save_data(self, data: dict) -> None:
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        normalized = self._normalized_data(data)
        self.path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def chapter_paths(self) -> list[Path]:
        return LatexProjectExporter(self.project_root, self.extensions).source_paths()

    def chapter_states(self) -> list[ChapterEditingState]:
        data = self.load_data()
        chapters = data["chapters"]
        stages = list(data["stages"])
        states: list[ChapterEditingState] = []
        changed = False
        for path in self.chapter_paths():
            relative = path.relative_to(self.project_root).as_posix()
            chapter = chapters.get(relative)
            if chapter is None:
                chapter = {"status": DEFAULT_EDITING_STAGES[0], "completion": 0}
                chapters[relative] = chapter
                changed = True
            states.append(
                ChapterEditingState(
                    relative,
                    self._valid_status(str(chapter.get("status", stages[0])), stages),
                    self._bounded_completion(chapter.get("completion", 0)),
                )
            )
        if changed:
            self.save_data(data)
        return states

    def update_chapter(self, relative_path: str, status: str, completion: int) -> None:
        data = self.load_data()
        data["chapters"][relative_path] = {
            "status": self._valid_status(status, list(data["stages"])),
            "completion": self._bounded_completion(completion),
        }
        self.save_data(data)

    def remap_chapter_paths(self, path_mapping: dict[Path, Path]) -> None:
        if not path_mapping:
            return
        data = self.load_data()
        chapters = data["chapters"]
        remapped: dict[str, dict] = {}
        relative_mapping = {
            old.resolve().relative_to(self.project_root).as_posix(): new.resolve().relative_to(self.project_root).as_posix()
            for old, new in path_mapping.items()
            if old.resolve().is_relative_to(self.project_root)
            and new.resolve().is_relative_to(self.project_root)
        }
        for path, value in chapters.items():
            remapped[relative_mapping.get(path, path)] = value
        data["chapters"] = remapped
        self.save_data(data)

    def summary(self) -> EditingSummary:
        data = self.load_data()
        stages = list(data["stages"])
        phase_weights = dict(data["phase_weights"])
        states = self.chapter_states()
        status_counts = {stage: 0 for stage in stages}
        for state in states:
            status_counts[state.status] = status_counts.get(state.status, 0) + 1

        phase_summaries: list[EditingPhaseSummary] = []
        weighted_total = 0.0
        total_weight = sum(max(int(weight), 0) for weight in phase_weights.values())

        for phase_name, weight in phase_weights.items():
            weight = max(int(weight), 0)
            if not states:
                average = 0.0
            else:
                values = [self._phase_completion_for_state(state, phase_name, stages) for state in states]
                average = sum(values) / len(values)
            weighted_total += average * weight
            phase_summaries.append(
                EditingPhaseSummary(
                    phase_name,
                    weight,
                    average,
                    len(states),
                )
            )

        overall = weighted_total / total_weight if total_weight else 0.0
        return EditingSummary(
            len(states),
            overall,
            phase_summaries,
            status_counts,
        )

    def _default_data(self) -> dict:
        return {
            "version": 1,
            "stages": list(DEFAULT_EDITING_STAGES),
            "phase_weights": dict(DEFAULT_PHASE_WEIGHTS),
            "chapters": {},
        }

    def _normalized_data(self, raw: dict) -> dict:
        if not isinstance(raw, dict):
            raw = {}
        stages = raw.get("stages")
        if not isinstance(stages, list) or not stages:
            stages = list(DEFAULT_EDITING_STAGES)
        stages = [str(stage) for stage in stages if str(stage).strip()]
        if not stages:
            stages = list(DEFAULT_EDITING_STAGES)

        phase_weights = raw.get("phase_weights")
        if not isinstance(phase_weights, dict):
            phase_weights = dict(DEFAULT_PHASE_WEIGHTS)
        phase_weights = {
            str(name): max(int(weight), 0)
            for name, weight in phase_weights.items()
            if str(name) in stages
        }
        if not phase_weights:
            phase_weights = dict(DEFAULT_PHASE_WEIGHTS)

        chapters = raw.get("chapters")
        if not isinstance(chapters, dict):
            chapters = {}

        return {
            "version": int(raw.get("version", 1) or 1),
            "stages": stages,
            "phase_weights": phase_weights,
            "chapters": {
                str(path): {
                    "status": self._valid_status(str(value.get("status", stages[0])), stages),
                    "completion": self._bounded_completion(value.get("completion", 0)),
                }
                for path, value in chapters.items()
                if isinstance(value, dict)
            },
        }

    def _phase_completion_for_state(
        self,
        state: ChapterEditingState,
        phase_name: str,
        stages: list[str],
    ) -> float:
        if phase_name not in stages or state.status not in stages:
            return 0.0
        current_index = stages.index(state.status)
        phase_index = stages.index(phase_name)
        locked_index = stages.index("Verrouillé") if "Verrouillé" in stages else len(stages)
        if current_index > phase_index or current_index >= locked_index:
            return 100.0
        if current_index == phase_index:
            return float(state.completion)
        return 0.0

    def _valid_status(self, status: str, stages: list[str] | None = None) -> str:
        stages = stages or DEFAULT_EDITING_STAGES
        return status if status in stages else stages[0]

    def _bounded_completion(self, value) -> int:
        try:
            return min(max(int(value), 0), 100)
        except (TypeError, ValueError):
            return 0
