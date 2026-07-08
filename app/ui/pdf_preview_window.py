from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
except ImportError:  # pragma: no cover - depends on the local PySide6 build.
    QPdfDocument = None
    QPdfView = None


class PdfPreviewWindow(QMainWindow):
    def __init__(self, pdf_path: Path, stylesheet: str = "") -> None:
        super().__init__()
        self.pdf_path = pdf_path.resolve()
        self.pdf_document = None

        self.setWindowTitle(f"Preview PDF - {self.pdf_path.name}")
        if stylesheet:
            self.setStyleSheet(stylesheet)

        if QPdfDocument is not None and QPdfView is not None:
            self._build_pdf_view()
        else:
            self._build_fallback_view()

    def _build_pdf_view(self) -> None:
        self.pdf_document = QPdfDocument(self)
        self.pdf_document.load(str(self.pdf_path))

        view = QPdfView(self)
        view.setDocument(self.pdf_document)
        view.setPageMode(QPdfView.PageMode.MultiPage)
        view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.setCentralWidget(view)
        self.resize(920, 1100)

    def _build_fallback_view(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        label = QLabel(
            "La preview integree n'est pas disponible dans cette installation de PySide6.\n"
            "Le PDF a ete ouvert avec l'application par defaut."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setCentralWidget(central)
        self.resize(520, 180)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pdf_path)))
