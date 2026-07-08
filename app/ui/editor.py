from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextOption
from PySide6.QtWidgets import QTextEdit


class TextEditor(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptRichText(False)
        self.setPlaceholderText(r"Ecris ton chapitre en LaTeX ici... Ex.: \chapter{Titre}")
        self.setLineWrapMode(QTextEdit.WidgetWidth)

        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(12)
        self.setFont(font)

        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(text_option)
        self._apply_plain_black_text_format()

    def text(self) -> str:
        return self.toPlainText()

    def set_text(self, text: str) -> None:
        self.setPlainText(text)
        self._apply_plain_black_text_format()

    def insertFromMimeData(self, source) -> None:  # Qt MIME data
        self.insertPlainText(source.text())
        self._apply_plain_black_text_format()

    def _apply_plain_black_text_format(self) -> None:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor("#000000"))
        text_format.setBackground(Qt.GlobalColor.transparent)
        self.setCurrentCharFormat(text_format)
        self.mergeCurrentCharFormat(text_format)
