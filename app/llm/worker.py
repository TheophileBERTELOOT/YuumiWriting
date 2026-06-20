from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from app.llm.config import OpenAIConfig
from app.llm.registry import LLMAnalysisDefinition
from app.llm.service import LLMAnalysisService
from app.llm.storage import LLMAnalysisStorage


class LLMAnalysisSignals(QObject):
    finished = Signal(object, object)
    failed = Signal(object, str)


class LLMAnalysisWorker(QRunnable):
    def __init__(
        self,
        storage: LLMAnalysisStorage,
        source_path: Path,
        text: str,
        definitions: tuple[LLMAnalysisDefinition, ...],
    ) -> None:
        super().__init__()
        self.storage = storage
        self.source_path = source_path
        self.text = text
        self.definitions = definitions
        self.signals = LLMAnalysisSignals()

    def run(self) -> None:
        try:
            config = OpenAIConfig.load(self.storage.project_root)
            service = LLMAnalysisService(config)
            analyses = service.analyze(self.text, self.definitions)
            self.storage.save(
                self.source_path,
                self.text,
                service.model,
                analyses,
                service.prompt_version,
            )
            self.signals.finished.emit(self.source_path, analyses)
        except Exception as exc:
            self.signals.failed.emit(self.source_path, str(exc))
