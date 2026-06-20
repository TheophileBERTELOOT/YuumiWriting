from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from app.analysis.analyzer_base import Indicator
from app.analysis.registry import AnalyzerRegistry
from app.ui.indicators_panel import IndicatorsPanel


IGNORED_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", "node_modules"}


class FolderReportSignals(QObject):
    status = Signal(str)
    finished = Signal(object, int)
    failed = Signal(str)


class FolderReportWorker(QRunnable):
    def __init__(
        self,
        root: Path,
        extensions: tuple[str, ...],
        analyzers: AnalyzerRegistry,
    ) -> None:
        super().__init__()
        self.root = root
        self.extensions = extensions
        self.analyzers = analyzers
        self.signals = FolderReportSignals()

    def run(self) -> None:
        try:
            paths = sorted(
                path
                for path in self.root.rglob("*")
                if path.is_file()
                and path.suffix.lower() in self.extensions
                and not any(part in IGNORED_DIRECTORIES for part in path.parts)
            )
            self.signals.status.emit(f"Lecture de {len(paths)} fichier(s)…")
            texts = [path.read_text(encoding="utf-8", errors="replace") for path in paths]

            if not texts:
                self.signals.finished.emit([], 0)
                return

            self.signals.status.emit("Analyse du corpus complet…")
            names = set(self.analyzers.available_indicator_names())
            # Garantit une frontière de phrase entre deux fichiers sans créer
            # une phrase vide lorsque le chapitre est déjà ponctué.
            bounded_texts = [
                content
                if not content.strip()
                or content.rstrip().endswith((".", "!", "?", "…"))
                else f"{content.rstrip()}."
                for content in texts
            ]
            corpus = "\n\n".join(bounded_texts)
            indicators = self.analyzers.analyze_selected(corpus, names)
            self.signals.finished.emit(indicators, len(paths))
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class FolderReportWindow(QMainWindow):
    def __init__(
        self,
        root: Path,
        extensions: tuple[str, ...],
        analyzers: AnalyzerRegistry,
        stylesheet: str = "",
    ) -> None:
        super().__init__()
        self.root = root
        self.setWindowTitle(f"Rapport du dossier — {root.name}")
        self.resize(760, 900)
        if stylesheet:
            self.setStyleSheet(stylesheet)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel(f"<h2>Rapport complet — {root.name}</h2>")
        self.status = QLabel("Préparation du rapport…")
        self.status.setWordWrap(True)
        self.panel = IndicatorsPanel()

        layout.addWidget(title)
        layout.addWidget(self.status)
        layout.addWidget(self.panel, 1)
        self.setCentralWidget(central)

        self.worker = FolderReportWorker(root, extensions, analyzers)
        self.worker.signals.status.connect(self.status.setText)
        self.worker.signals.finished.connect(self._show_report)
        self.worker.signals.failed.connect(self._show_error)
        QThreadPool.globalInstance().start(self.worker)

    def _show_report(self, indicators: object, file_count: int) -> None:
        report = indicators if isinstance(indicators, list) else []
        if file_count == 0:
            self.status.setText("Aucun fichier compatible trouvé dans ce dossier.")
            return
        self.status.setText(
            f"{file_count} fichier{'s' if file_count != 1 else ''} analysé"
            f"{'s' if file_count != 1 else ''}."
        )
        self.panel.set_indicators(report)

    def _show_error(self, message: str) -> None:
        self.status.setText(f"Impossible de produire le rapport : {message}")
