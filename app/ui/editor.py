from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class FindReplaceDialog(QDialog):
    def __init__(self, editor: "TextEditor") -> None:
        super().__init__(editor.window())
        self.editor = editor
        self.setModal(False)
        self.setWindowTitle("Rechercher et remplacer")
        self.setMinimumWidth(420)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Mot à rechercher")
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Remplacer par")
        replace_one = QPushButton("Remplacer")
        replace_all = QPushButton("Tout remplacer")

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Rechercher"))
        form_layout.addWidget(self.search_edit)
        form_layout.addWidget(QLabel("Remplacer par"))
        form_layout.addWidget(self.replace_edit)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(replace_one)
        button_layout.addWidget(replace_all)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)

        self.search_edit.textChanged.connect(self.editor.highlight_search)
        replace_one.clicked.connect(self._replace_current)
        replace_all.clicked.connect(self._replace_all)

    def set_search_text(self, text: str) -> None:
        self.search_edit.setText(text)
        self.search_edit.selectAll()

    def focus_search(self) -> None:
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def closeEvent(self, event) -> None:  # Qt close event
        self.editor.clear_search_highlights()
        super().closeEvent(event)

    def _replace_current(self) -> None:
        self.editor.replace_current_match(
            self.search_edit.text(),
            self.replace_edit.text(),
        )

    def _replace_all(self) -> None:
        self.editor.replace_all_matches(
            self.search_edit.text(),
            self.replace_edit.text(),
        )


class TextEditor(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self._find_dialog: FindReplaceDialog | None = None
        self._highlighted_search_text = ""
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setBackground(QColor("#f2d45c"))
        self._highlight_format.setForeground(QColor("#000000"))
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
        self.textChanged.connect(self._refresh_search_highlights)

    def text(self) -> str:
        return self.toPlainText()

    def set_text(self, text: str) -> None:
        self.setPlainText(text)
        self._apply_plain_black_text_format()

    def insertFromMimeData(self, source) -> None:  # Qt MIME data
        self.insertPlainText(source.text())
        self._apply_plain_black_text_format()

    def open_find_replace(self) -> None:
        if self._find_dialog is None:
            self._find_dialog = FindReplaceDialog(self)

        selected_text = self.textCursor().selectedText().replace("\u2029", "\n").strip()
        if selected_text:
            self._find_dialog.set_search_text(selected_text)
        else:
            self.highlight_search(self._find_dialog.search_edit.text())

        self._find_dialog.show()
        self._find_dialog.raise_()
        self._find_dialog.activateWindow()
        self._find_dialog.focus_search()

    def highlight_search(self, search_text: str) -> None:
        self._highlighted_search_text = search_text
        self._refresh_search_highlights()

    def clear_search_highlights(self) -> None:
        self._highlighted_search_text = ""
        self.setExtraSelections([])

    def replace_current_match(self, search_text: str, replacement: str) -> None:
        if not search_text:
            return
        cursor = self.textCursor()
        if not self._cursor_matches(cursor, search_text):
            cursor = self.document().find(search_text, cursor)
            if cursor.isNull():
                cursor = self.document().find(search_text, QTextCursor(self.document()))
        if cursor.isNull():
            return
        cursor.insertText(replacement)
        self.setTextCursor(cursor)
        self.highlight_search(search_text)

    def replace_all_matches(self, search_text: str, replacement: str) -> None:
        if not search_text:
            return
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        match = self.document().find(search_text, cursor)
        while not match.isNull():
            match.insertText(replacement)
            match = self.document().find(search_text, match)
        cursor.endEditBlock()
        self.highlight_search(search_text)

    def _apply_plain_black_text_format(self) -> None:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor("#000000"))
        text_format.setBackground(Qt.GlobalColor.transparent)
        self.setCurrentCharFormat(text_format)
        self.mergeCurrentCharFormat(text_format)

    def _refresh_search_highlights(self) -> None:
        search_text = self._highlighted_search_text
        if not search_text:
            self.setExtraSelections([])
            return

        selections: list[QTextEdit.ExtraSelection] = []
        cursor = QTextCursor(self.document())
        while True:
            cursor = self.document().find(search_text, cursor)
            if cursor.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(cursor)
            selection.format = self._highlight_format
            selections.append(selection)
        self.setExtraSelections(selections)

    def _cursor_matches(self, cursor: QTextCursor, search_text: str) -> bool:
        if not cursor.hasSelection():
            return False
        selected = cursor.selectedText().replace("\u2029", "\n")
        return selected.casefold() == search_text.casefold()
