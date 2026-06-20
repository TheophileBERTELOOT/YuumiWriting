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
from app.core.settings import AppSettings
from app.ui.editor import TextEditor
from app.ui.file_tree import FileTree
from app.ui.folder_report import FolderReportWindow
from app.ui.indicators_panel import IndicatorsPanel


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

        # Indicateurs visibles dans la barre de droite.
        # Au départ tout est désactivé : l'utilisateur coche ce qu'il veut voir.
        self.enabled_indicator_names: set[str] = set()
        self.indicator_actions: dict[str, QAction] = {}
        self.analysis_pool = QThreadPool.globalInstance()
        self._nature_generation = 0
        self._nature_worker_running = False
        self._pending_nature_request: tuple[int, str] | None = None
        self._nature_cache: tuple[str, list[Indicator]] | None = None
        self.folder_report_window: FolderReportWindow | None = None

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

        syntax_menu = menu_bar.addMenu("Syntaxe")

        self.analyze_action = QAction("Rafraîchir l'analyse", self)
        self.analyze_action.setShortcut("Ctrl+R")
        syntax_menu.addAction(self.analyze_action)
        syntax_menu.addSeparator()

        repetition_menu = menu_bar.addMenu("Répétition")
        repetition_indicators = {
            "Répétition de phrases",
            "Répétition de mots",
        }
        grammar_menu = menu_bar.addMenu("Grammaire")
        grammar_indicators = {"Nature"}

        for indicator_name in self.analyzers.available_indicator_names():
            action = QAction(indicator_name, self)
            action.setCheckable(True)
            action.setChecked(False)
            action.toggled.connect(
                lambda checked, name=indicator_name: self._toggle_indicator(name, checked)
            )
            self.indicator_actions[indicator_name] = action
            if indicator_name in repetition_indicators:
                target_menu = repetition_menu
            elif indicator_name in grammar_indicators:
                target_menu = grammar_menu
            else:
                target_menu = syntax_menu
            target_menu.addAction(action)

        menu_bar.addSeparator()
        self.folder_report_action = QAction("Rapport du dossier", self)
        menu_bar.addAction(self.folder_report_action)

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

    def _toggle_indicator(self, indicator_name: str, checked: bool) -> None:
        if checked:
            self.enabled_indicator_names.add(indicator_name)
        else:
            self.enabled_indicator_names.discard(indicator_name)
        self.refresh_indicators()

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
        self.status_label.setText(f"Sauvegardé : {path.name}")

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
        self.status_label.setText(f"Sauvegardé : {path.name}")

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

    def refresh_indicators(self) -> None:
        text = self.editor.text()
        regular_names = self.enabled_indicator_names - {"Nature"}
        visible_indicators = self.analyzers.analyze_selected(
            text,
            regular_names,
        )

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
