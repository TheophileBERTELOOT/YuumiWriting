from __future__ import annotations

from PySide6.QtGui import QFont, QTextOption
from PySide6.QtWidgets import QTextEdit


class TextEditor(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptRichText(True)
        self.setPlaceholderText("Écris ton chapitre ici…")
        self.setLineWrapMode(QTextEdit.WidgetWidth)

        font = QFont("DejaVu Serif")
        font.setPointSize(13)
        self.setFont(font)

        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(text_option)

    def text(self) -> str:
        return self.toPlainText()

    def set_text(self, text: str) -> None:
        self.setPlainText(text)
