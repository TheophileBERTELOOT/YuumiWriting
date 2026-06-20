from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.analysis.analyzer_base import Indicator


class IndicatorCard(QWidget):
    def __init__(self, indicator: Indicator) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        title = QLabel(f"<b>{indicator.name}</b>")
        value = QLabel(indicator.value)
        detail = QLabel(indicator.detail)
        title.setWordWrap(True)
        value.setWordWrap(True)
        detail.setWordWrap(True)

        layout.addWidget(title)
        if indicator.value:
            layout.addWidget(value)
        if indicator.distribution:
            layout.addWidget(SentenceLengthHistogram(indicator.distribution))
        if indicator.detail:
            layout.addWidget(detail)
        if indicator.report_items:
            layout.addWidget(CollapsibleReport(indicator.report_items))
        for section_name, total, items in indicator.report_sections:
            layout.addWidget(
                CollapsibleReport(items, title=f"{section_name} — {total}")
            )

        self.setObjectName("indicatorCard")
        self.setProperty("severity", indicator.severity)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )


class SentenceLengthHistogram(QWidget):
    def __init__(self, distribution: tuple[tuple[str, int], ...]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)
        maximum = max((count for _, count in distribution), default=0)

        for label, count in distribution:
            row = QHBoxLayout()
            row.setSpacing(6)

            range_label = QLabel(label)
            range_label.setFixedWidth(38)
            range_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            bar = QProgressBar()
            bar.setRange(0, maximum or 1)
            bar.setValue(count)
            bar.setTextVisible(False)
            bar.setFixedHeight(9)
            bar.setStyleSheet(
                "QProgressBar { background: #25262a; border: none; border-radius: 4px; }"
                "QProgressBar::chunk { background: #7ca6d9; border-radius: 4px; }"
            )

            count_label = QLabel(str(count))
            count_label.setFixedWidth(24)
            count_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            row.addWidget(range_label)
            row.addWidget(bar, 1)
            row.addWidget(count_label)
            layout.addLayout(row)


class CollapsibleReport(QWidget):
    def __init__(
        self,
        items: tuple[tuple[str, int], ...],
        title: str = "Détails",
    ) -> None:
        super().__init__()
        self.title = title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(5)

        self.toggle = QToolButton()
        self.toggle.setText(self.title)
        self.toggle.setCheckable(True)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.toggled.connect(self._set_expanded)
        layout.addWidget(self.toggle)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(6, 0, 0, 0)
        content_layout.setSpacing(5)

        for text, count in items:
            row = QHBoxLayout()
            item_label = QLabel(text)
            item_label.setTextFormat(Qt.TextFormat.PlainText)
            item_label.setWordWrap(True)
            count_label = QLabel(f"× {count}")
            count_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            )
            count_label.setMinimumWidth(30)
            row.addWidget(item_label, 1)
            row.addWidget(count_label)
            content_layout.addLayout(row)

        if not items:
            empty_label = QLabel("Aucun mot")
            empty_label.setProperty("muted", True)
            content_layout.addWidget(empty_label)

        self.content.setVisible(False)
        layout.addWidget(self.content)

    def _set_expanded(self, expanded: bool) -> None:
        self.content.setVisible(expanded)
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.toggle.setText(self.title)


class IndicatorsPanel(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setStyleSheet("background: #26272b;")

        self.container = QWidget()
        self.container.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)
        self.layout.addStretch(1)

        self.setWidget(self.container)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Certains QLabel avec retour à la ligne produisent une largeur idéale
        # supérieure au panneau. Sans cette contrainte, Qt décale le contenu
        # hors de la zone visible malgré setWidgetResizable(True).
        self.container.setFixedWidth(self.viewport().width())

    def set_indicators(self, indicators: list[Indicator]) -> None:
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for indicator in indicators:
            self.layout.insertWidget(self.layout.count() - 1, IndicatorCard(indicator))
