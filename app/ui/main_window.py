from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from app.analysis.registry import AnalyzerRegistry
from app.analysis.analyzer_base import Indicator
from app.core.document_manager import DocumentManager
from app.core.progression import ProgressTracker
from app.core.settings import AppSettings
from app.llm.registry import LLMAnalysisRegistry
from app.llm.storage import LLMAnalysisStorage
from app.llm.worker import LLMAnalysisWorker
from app.ui.editor import TextEditor
from app.ui.file_tree import FileTree
from app.ui.folder_report import FolderReportWindow
from app.ui.graph_window import GraphWindow
from app.ui.indicators_panel import IndicatorsPanel
from app.ui.timeline_window import TimelineWindow
from app.ui.progression_window import ProgressionWindow


class NatureAnalysisSignals(QObject):
    finished = Signal(int, str, object)


class NatureAnalysisWorker(QRunnable):
    def __init__(
        self,
        generation: int,
        text: str,
        analyzers: AnalyzerRegistry,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.text = text
        self.analyzers = analyzers
        self.signals = NatureAnalysisSignals()

    def run(self) -> None:
        try:
            indicators = self.analyzers.analyze_selected(self.text, {"Nature"})
        except Exception as exc:
            indicators = [
                Indicator(
                    "Nature",
                    "Erreur d'analyse",
                    str(exc),
                    "danger",
                )
            ]
        self.signals.finished.emit(self.generation, self.text, indicators)


class MainWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.settings = AppSettings(default_project_root=project_root)
        self.document_manager = DocumentManager()
        self.analyzers = AnalyzerRegistry()
        self.llm_registry = LLMAnalysisRegistry()
        self.llm_storage = LLMAnalysisStorage(project_root)
        self.progress_tracker = ProgressTracker(
            project_root,
            self.settings.accepted_extensions,
        )

        # Indicateurs visibles dans la barre de droite.
        # Au départ tout est désactivé : l'utilisateur coche ce qu'il veut voir.
        self.enabled_indicator_names: set[str] = set()
        self.indicator_actions: dict[str, QAction] = {}
        self.enabled_llm_indicator_names: set[str] = set()
        self.llm_indicator_actions: dict[str, QAction] = {}
        self.analysis_group_actions: dict[str, list[QAction]] = {}
        self.analysis_group_selectors: dict[str, QAction] = {}
        self.analysis_pool = QThreadPool.globalInstance()
        self.llm_pool = QThreadPool(self)
        self.llm_pool.setMaxThreadCount(1)
        self._nature_generation = 0
        self._nature_worker_running = False
        self._pending_nature_request: tuple[int, str] | None = None
        self._nature_cache: tuple[str, list[Indicator]] | None = None
        self._llm_worker_running = False
        self._active_llm_worker: LLMAnalysisWorker | None = None
        self._active_llm_source_path: Path | None = None
        self._active_llm_fingerprint: tuple[str, str, int] | None = None
        self._pending_llm_request: tuple[LLMAnalysisStorage, Path, str] | None = None
        self.folder_report_window: FolderReportWindow | None = None
        self.graph_window: GraphWindow | None = None
        self.timeline_window: TimelineWindow | None = None
        self.progression_window: ProgressionWindow | None = None

        self.setWindowTitle("YuumiWriting")

        self.file_tree = FileTree(project_root, self.settings.accepted_extensions)
        self.editor = TextEditor()
        self.indicators_panel = IndicatorsPanel()
        self.status_label = QLabel("Prêt")

        self._build_menus()
        self._build_layout()
        self._connect_signals()
        self._apply_styles()

        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(350)
        self.analysis_timer.timeout.connect(self.refresh_indicators)

        self.statusBar().addPermanentWidget(self.status_label)
        self.refresh_indicators()

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Fichier")

        self.new_action = QAction("Nouveau", self)
        self.new_action.setShortcut(QKeySequence.New)

        self.open_action = QAction("Ouvrir un fichier...", self)
        self.open_action.setShortcut(QKeySequence.Open)

        self.open_folder_action = QAction("Ouvrir un dossier...", self)
        self.open_folder_action.setShortcut("Ctrl+Shift+O")

        self.save_action = QAction("Sauvegarder", self)
        self.save_action.setShortcut(QKeySequence.Save)

        self.save_as_action = QAction("Sauvegarder sous...", self)
        self.save_as_action.setShortcut(QKeySequence.SaveAs)

        self.quit_action = QAction("Quitter", self)
        self.quit_action.setShortcut(QKeySequence.Quit)

        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.open_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        self._add_menu_separator(menu_bar)

        syntax_menu = menu_bar.addMenu("Syntaxe")

        self.analyze_action = QAction("Rafraîchir l'analyse", self)
        self.analyze_action.setShortcut("Ctrl+R")
        syntax_menu.addAction(self.analyze_action)
        syntax_menu.addSeparator()
        self._add_group_selector(syntax_menu, "syntax")

        repetition_menu = menu_bar.addMenu("Répétition")
        self._add_group_selector(repetition_menu, "repetition")
        repetition_indicators = {
            "Répétition de phrases",
            "Répétition de mots",
        }
        grammar_menu = menu_bar.addMenu("Grammaire")
        self._add_group_selector(grammar_menu, "grammar")
        grammar_indicators = {"Nature"}

        for indicator_name in self.analyzers.available_indicator_names():
            if indicator_name in repetition_indicators:
                target_menu = repetition_menu
                group_name = "repetition"
            elif indicator_name in grammar_indicators:
                target_menu = grammar_menu
                group_name = "grammar"
            else:
                target_menu = syntax_menu
                group_name = "syntax"
            action = QAction(indicator_name, self)
            action.setCheckable(True)
            action.setChecked(False)
            action.toggled.connect(
                lambda checked, name=indicator_name, group=group_name: self._toggle_indicator(
                    name,
                    checked,
                    group,
                )
            )
            self.indicator_actions[indicator_name] = action
            self.analysis_group_actions[group_name].append(action)
            target_menu.addAction(action)

        llm_menu = menu_bar.addMenu("Analyses IA")
        self._add_group_selector(llm_menu, "llm")
        if not self.llm_registry.definitions:
            empty_llm_action = QAction("Aucune analyse configurée", self)
            empty_llm_action.setEnabled(False)
            llm_menu.addAction(empty_llm_action)
        for definition in self.llm_registry.definitions:
            action = QAction(definition.name, self)
            action.setCheckable(True)
            action.toggled.connect(
                lambda checked, name=definition.name: self._toggle_llm_indicator(
                    name,
                    checked,
                    "llm",
                )
            )
            self.llm_indicator_actions[definition.name] = action
            self.analysis_group_actions["llm"].append(action)
            llm_menu.addAction(action)

        self._add_menu_separator(menu_bar)
        self.folder_report_action = QAction("Rapport du dossier", self)
        menu_bar.addAction(self.folder_report_action)
        self.graph_action = QAction("Graphe", self)
        menu_bar.addAction(self.graph_action)
        self.timeline_action = QAction("Timeline", self)
        menu_bar.addAction(self.timeline_action)
        self.progression_action = QAction("Progression", self)
        menu_bar.addAction(self.progression_action)

    def _add_group_selector(self, menu, group_name: str) -> None:
        selector = QAction("Tout sélectionner", self)
        selector.setCheckable(True)
        selector.toggled.connect(
            lambda checked, group=group_name: self._toggle_analysis_group(
                group,
                checked,
            )
        )
        self.analysis_group_selectors[group_name] = selector
        self.analysis_group_actions[group_name] = []
        menu.addAction(selector)
        menu.addSeparator()

    def _add_menu_separator(self, menu_bar) -> None:
        """Ajoute un séparateur que QMenuBar dessine comme un élément natif."""
        separator = QAction("│", menu_bar)
        separator.setToolTip("")
        menu_bar.addAction(separator)

    def _build_layout(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.file_tree)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.indicators_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([260, 850, 290])

        self.setCentralWidget(splitter)

    def _connect_signals(self) -> None:
        self.file_tree.file_selected.connect(self.open_path)
        self.editor.textChanged.connect(self._on_text_changed)

        self.new_action.triggered.connect(self.new_document)
        self.open_action.triggered.connect(self.open_file_dialog)
        self.open_folder_action.triggered.connect(self.open_folder_dialog)
        self.save_action.triggered.connect(self.save_document)
        self.save_as_action.triggered.connect(self.save_as_dialog)
        self.quit_action.triggered.connect(self.close)
        self.analyze_action.triggered.connect(self.refresh_indicators)
        self.folder_report_action.triggered.connect(self.open_folder_report)
        self.graph_action.triggered.connect(self.open_graph)
        self.timeline_action.triggered.connect(self.open_timeline)
        self.progression_action.triggered.connect(self.open_progression)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #202124;
            }
            QMenuBar {
                background: #2d2e33;
                color: white;
                padding: 3px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 12px;
            }
            QMenuBar::item:selected {
                background: #44464d;
                border-radius: 4px;
            }
            QMenuBar::separator {
                width: 1px;
                background: #5b5d66;
                margin: 5px 7px;
            }
            QMenu {
                background: #2d2e33;
                color: white;
                border: 1px solid #44464d;
            }
            QMenu::item {
                padding: 7px 28px 7px 24px;
            }
            QMenu::item:selected {
                background: #555862;
            }
            QTextEdit {
                background: #fbf7ef;
                color: #1f1a17;
                padding: 22px;
                border: none;
                selection-background-color: #d9c7a3;
            }
            QTreeView {
                background: #26272b;
                color: #eeeeee;
                border: none;
                padding: 4px;
            }
            QScrollArea {
                background: #26272b;
                border: none;
            }
            QWidget#indicatorCard {
                background: #33343a;
                border-radius: 8px;
                color: #eeeeee;
            }
            QWidget#indicatorCard QLabel,
            QWidget#indicatorCard QToolButton {
                color: #eeeeee;
            }
            QWidget#indicatorCard[severity="success"] {
                border-left: 5px solid #76b37a;
            }
            QWidget#indicatorCard[severity="warning"] {
                border-left: 5px solid #d6aa4c;
            }
            QWidget#indicatorCard[severity="danger"] {
                border-left: 5px solid #d46a6a;
            }
            QWidget#indicatorCard[severity="info"] {
                border-left: 5px solid #7ca6d9;
            }
            QStatusBar {
                background: #2d2e33;
                color: white;
            }
            """
        )

    def _toggle_indicator(
        self,
        indicator_name: str,
        checked: bool,
        group_name: str,
    ) -> None:
        if checked:
            self.enabled_indicator_names.add(indicator_name)
        else:
            self.enabled_indicator_names.discard(indicator_name)
        self._sync_group_selector(group_name)
        self.refresh_indicators()

    def _toggle_analysis_group(self, group_name: str, checked: bool) -> None:
        actions = self.analysis_group_actions.get(group_name, [])
        for action in actions:
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)
            if group_name == "llm":
                if checked:
                    self.enabled_llm_indicator_names.add(action.text())
                else:
                    self.enabled_llm_indicator_names.discard(action.text())
            elif checked:
                self.enabled_indicator_names.add(action.text())
            else:
                self.enabled_indicator_names.discard(action.text())
        self.refresh_indicators()

    def _sync_group_selector(self, group_name: str) -> None:
        selector = self.analysis_group_selectors.get(group_name)
        actions = self.analysis_group_actions.get(group_name, [])
        if selector is None:
            return
        all_checked = bool(actions) and all(action.isChecked() for action in actions)
        selector.blockSignals(True)
        selector.setChecked(all_checked)
        selector.blockSignals(False)

    def _on_text_changed(self) -> None:
        self.document_manager.mark_dirty()
        self._update_window_title()
        self.analysis_timer.start()

    def _maybe_discard_changes(self) -> bool:
        if not self.document_manager.is_dirty:
            return True

        answer = QMessageBox.question(
            self,
            "Modifications non sauvegardées",
            "Le document courant a des modifications non sauvegardées. Continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def new_document(self) -> None:
        if not self._maybe_discard_changes():
            return
        self.document_manager.new_document()
        self.editor.set_text("")
        self.document_manager.is_dirty = False
        self._update_window_title()
        self.refresh_indicators()

    def open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Ouvrir un dossier de roman",
            str(self.settings.default_project_root),
        )
        if not folder:
            return

        project_root = Path(folder)
        self.settings.default_project_root = project_root
        self.file_tree.set_project_root(project_root)
        self.progress_tracker = ProgressTracker(
            project_root,
            self.settings.accepted_extensions,
        )
        self.llm_storage = LLMAnalysisStorage(project_root)
        self.status_label.setText(f"Dossier ouvert : {project_root.name}")

    def open_file_dialog(self) -> None:
        if not self._maybe_discard_changes():
            return

        filter_text = "Textes (*.txt *.md *.tex);;Tous les fichiers (*)"
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un fichier",
            str(self.settings.default_project_root),
            filter_text,
        )
        if filename:
            self.open_path(Path(filename))

    def open_path(self, path: Path) -> None:
        if not self._maybe_discard_changes():
            return
        try:
            content = self.document_manager.open_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'ouverture", str(exc))
            return

        self.editor.blockSignals(True)
        self.editor.set_text(content)
        self.editor.blockSignals(False)
        self.document_manager.is_dirty = False
        self._update_window_title()
        self.refresh_indicators()
        self.status_label.setText(f"Ouvert : {path.name}")

    def save_document(self) -> None:
        if self.document_manager.current_path is None:
            self.save_as_dialog()
            return
        try:
            path = self.document_manager.save(self.editor.text())
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de sauvegarde", str(exc))
            return
        self._update_window_title()
        self._record_progress()
        self.status_label.setText(f"Sauvegardé : {path.name}")
        self._request_llm_analysis(path, self.editor.text())

    def save_as_dialog(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Sauvegarder sous",
            str(self.settings.default_project_root / "nouveau_chapitre.txt"),
            "Textes (*.txt *.md *.tex);;Tous les fichiers (*)",
        )
        if not filename:
            return
        try:
            path = self.document_manager.save_as(Path(filename), self.editor.text())
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de sauvegarde", str(exc))
            return
        self._update_window_title()
        self._record_progress()
        self.status_label.setText(f"Sauvegardé : {path.name}")
        self._request_llm_analysis(path, self.editor.text())

    def open_folder_report(self) -> None:
        self.folder_report_window = FolderReportWindow(
            self.file_tree.project_root,
            self.settings.accepted_extensions,
            self.analyzers,
            self.styleSheet(),
        )
        self.folder_report_window.show()
        self.folder_report_window.raise_()
        self.folder_report_window.activateWindow()

    def open_graph(self) -> None:
        self.graph_window = GraphWindow(
            self.file_tree.project_root,
            self.styleSheet(),
        )
        self.graph_window.show()
        self.graph_window.raise_()
        self.graph_window.activateWindow()

    def open_timeline(self) -> None:
        self.timeline_window = TimelineWindow(
            self.file_tree.project_root,
            self.styleSheet(),
        )
        self.timeline_window.show()
        self.timeline_window.raise_()
        self.timeline_window.activateWindow()

    def open_progression(self) -> None:
        self.progression_window = ProgressionWindow(
            self.file_tree.project_root,
            self.settings.accepted_extensions,
            self.styleSheet(),
        )
        self.progression_window.show()
        self.progression_window.raise_()
        self.progression_window.activateWindow()

    def _record_progress(self) -> None:
        try:
            self.progress_tracker.record_save()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Suivi de progression",
                "Le document a été sauvegardé, mais le journal de progression "
                f"n’a pas pu être mis à jour : {exc}",
            )

    def _toggle_llm_indicator(
        self,
        indicator_name: str,
        checked: bool,
        group_name: str,
    ) -> None:
        if checked:
            self.enabled_llm_indicator_names.add(indicator_name)
        else:
            self.enabled_llm_indicator_names.discard(indicator_name)
        self._sync_group_selector(group_name)
        self.refresh_indicators()

    def _cached_llm_indicators(self) -> list[Indicator]:
        selected_names = self._selected_llm_indicator_names()
        if not selected_names:
            return []
        source_path = self.document_manager.current_path
        if source_path is None:
            return []
        indicators: list[Indicator] = []
        if (
            self._llm_worker_running
            and self._active_llm_source_path is not None
            and self._active_llm_source_path.resolve() == source_path.resolve()
        ):
            indicators.append(
                Indicator(
                    "Analyses IA",
                    "Analyse en cours…",
                    "Une seule requête OpenAI traite toutes les analyses IA.",
                    "info",
                )
            )
        try:
            cached = self.llm_storage.load(source_path)
        except Exception as exc:
            indicators.append(
                Indicator(
                    "Analyses IA",
                    "Cache illisible",
                    str(exc),
                    "danger",
                )
            )
            return indicators

        for name in selected_names:
            definition = self.llm_registry.by_name(name)
            if definition is None:
                continue
            result = cached["analyses"].get(definition.key) if cached else None
            if not isinstance(result, dict):
                indicators.append(
                    Indicator(
                        name,
                        "En attente d’une sauvegarde",
                        "Utilisez Ctrl+S pour lancer la prochaine analyse IA.",
                        "info",
                    )
                )
                continue
            if "score" in result:
                try:
                    score = min(max(float(result["score"]), 0.0), 1.0)
                except (TypeError, ValueError):
                    score = 0.0
                analysis = str(result.get("analysis", ""))
                examples = result.get("examples", [])
                if isinstance(examples, list) and examples:
                    example_text = "\n".join(
                        f"• « {example} »" for example in examples
                    )
                    detail = f"{analysis}\n\nExemples :\n{example_text}"
                else:
                    detail = analysis
                severity = (
                    "success"
                    if score >= 0.8
                    else "info"
                    if score >= 0.55
                    else "warning"
                    if score >= 0.3
                    else "danger"
                )
                indicators.append(
                    Indicator(
                        name,
                        f"Score : {score:.2f} / 1",
                        detail,
                        severity,
                    )
                )
                continue
            indicators.append(
                Indicator(
                    name,
                    str(result.get("value", "")),
                    str(result.get("detail", "")),
                    str(result.get("severity", "info")),
                )
            )
        return indicators

    def _selected_llm_indicator_names(self) -> set[str]:
        """Prend les cases visibles comme source de vérité pour l'affichage."""
        return {
            name
            for name, action in self.llm_indicator_actions.items()
            if action.isChecked()
        }

    def _request_llm_analysis(self, source_path: Path, text: str) -> None:
        definitions = self.llm_registry.definitions
        if not self._selected_llm_indicator_names() or not definitions:
            return
        from app.llm.service import LLMAnalysisService

        prompt_version = LLMAnalysisService.PROMPT_VERSION
        expected_keys = {definition.key for definition in definitions}
        fingerprint = (
            str(self.llm_storage.cache_path(source_path)),
            self.llm_storage.content_hash(text),
            prompt_version,
        )
        if fingerprint == self._active_llm_fingerprint:
            return
        try:
            if self.llm_storage.is_current(
                source_path,
                text,
                expected_keys,
                prompt_version,
            ):
                self.refresh_indicators()
                return
        except Exception:
            pass
        request = (self.llm_storage, source_path, text)
        if self._llm_worker_running:
            self._pending_llm_request = request
            return
        self._start_llm_analysis(*request)

    def _start_llm_analysis(
        self,
        storage: LLMAnalysisStorage,
        source_path: Path,
        text: str,
    ) -> None:
        self._llm_worker_running = True
        self._active_llm_source_path = source_path
        from app.llm.service import LLMAnalysisService

        self._active_llm_fingerprint = (
            str(storage.cache_path(source_path)),
            storage.content_hash(text),
            LLMAnalysisService.PROMPT_VERSION,
        )
        self.status_label.setText(f"Analyse IA en cours : {source_path.name}…")
        worker = LLMAnalysisWorker(
            storage,
            source_path,
            text,
            self.llm_registry.definitions,
        )
        worker.signals.finished.connect(self._on_llm_analysis_finished)
        worker.signals.failed.connect(self._on_llm_analysis_failed)
        self._active_llm_worker = worker
        self.refresh_indicators()
        self.llm_pool.start(worker)

    def _on_llm_analysis_finished(self, source_path: object, analyses: object) -> None:
        self._llm_worker_running = False
        self._active_llm_worker = None
        self._active_llm_source_path = None
        self._active_llm_fingerprint = None
        try:
            path = Path(source_path) if source_path is not None else None
        except TypeError:
            path = None
        if path is not None:
            self.status_label.setText(f"Analyse IA sauvegardée : {path.name}")
        # Recharge toujours le cache du document actuellement affiché. Cela
        # reste correct même si l'utilisateur a changé d'onglet entre-temps.
        self.refresh_indicators()
        self._start_pending_llm_request()

    def _on_llm_analysis_failed(self, source_path: object, message: str) -> None:
        self._llm_worker_running = False
        self._active_llm_worker = None
        self._active_llm_source_path = None
        self._active_llm_fingerprint = None
        try:
            name = Path(source_path).name if source_path is not None else "le document"
        except TypeError:
            name = "le document"
        QMessageBox.warning(
            self,
            "Analyse IA impossible",
            f"L’analyse de {name} a échoué : {message}",
        )
        self._start_pending_llm_request()

    def _start_pending_llm_request(self) -> None:
        if self._pending_llm_request is None:
            return
        pending = self._pending_llm_request
        self._pending_llm_request = None
        self._start_llm_analysis(*pending)

    def refresh_indicators(self) -> None:
        text = self.editor.text()
        regular_names = self.enabled_indicator_names - {"Nature"}
        visible_indicators = self.analyzers.analyze_selected(
            text,
            regular_names,
        )
        visible_indicators.extend(self._cached_llm_indicators())

        if "Nature" not in self.enabled_indicator_names:
            self._nature_generation += 1
            self._pending_nature_request = None
            self.indicators_panel.set_indicators(visible_indicators)
            return

        if self._nature_cache is not None and self._nature_cache[0] == text:
            visible_indicators.extend(self._nature_cache[1])
            self.indicators_panel.set_indicators(visible_indicators)
            return

        visible_indicators.append(
            Indicator(
                "Nature",
                "Analyse en cours…",
                "Chargement et analyse avec qanastek/pos-french-camembert.",
                "info",
            )
        )
        self.indicators_panel.set_indicators(visible_indicators)

        self._nature_generation += 1
        request = (self._nature_generation, text)
        if self._nature_worker_running:
            self._pending_nature_request = request
        else:
            self._start_nature_analysis(*request)

    def _start_nature_analysis(self, generation: int, text: str) -> None:
        self._nature_worker_running = True
        worker = NatureAnalysisWorker(
            generation,
            text,
            self.analyzers,
        )
        worker.signals.finished.connect(self._on_nature_analysis_finished)
        self.analysis_pool.start(worker)

    def _on_nature_analysis_finished(
        self,
        generation: int,
        text: str,
        indicators: object,
    ) -> None:
        self._nature_worker_running = False
        result = indicators if isinstance(indicators, list) else []

        if generation == self._nature_generation and "Nature" in self.enabled_indicator_names:
            self._nature_cache = (text, result)
            self.refresh_indicators()

        if self._pending_nature_request is not None:
            pending = self._pending_nature_request
            self._pending_nature_request = None
            if "Nature" in self.enabled_indicator_names:
                self._start_nature_analysis(*pending)

    def _update_window_title(self) -> None:
        path = self.document_manager.current_path
        dirty = "*" if self.document_manager.is_dirty else ""
        name = path.name if path else "Sans titre"
        self.setWindowTitle(f"{dirty}{name} — AuthorTool")
