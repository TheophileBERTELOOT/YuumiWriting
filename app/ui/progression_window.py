from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.editing_progress import EditingProgressTracker
from app.core.progression import ProgressRecord, ProgressTracker


class ChartWidget(QWidget):
    def _frame(self, painter: QPainter, title: str) -> QRectF:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#292a2f"))
        painter.setPen(QColor("#eeeeee"))
        font = QFont(painter.font())
        font.setBold(True)
        font.setPointSize(11)
        painter.setFont(font)
        painter.drawText(18, 27, title)
        return QRectF(68, 48, max(self.width() - 178, 10), max(self.height() - 88, 10))

    @staticmethod
    def _empty(painter: QPainter, area: QRectF) -> None:
        painter.setPen(QColor("#aaaaaa"))
        painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "Pas encore assez de données")


class ProjectionChart(ChartWidget):
    def __init__(self, records: list[ProgressRecord], parent=None) -> None:
        super().__init__(parent)
        self.records = records
        self.setMinimumHeight(340)

    def _series(self) -> tuple[list[date], list[float], list[float]]:
        if not self.records:
            return [], [], []
        by_day = {date.fromisoformat(record.day): float(record.words_written) for record in self.records}
        first, last = min(by_day), max(max(by_day), date.today())
        days, daily_values, cumulative_values = [], [], []
        cumulative = 0.0
        current = first
        while current <= last:
            days.append(current)
            daily_value = by_day.get(current, 0.0)
            daily_values.append(daily_value)
            cumulative += daily_value
            cumulative_values.append(cumulative)
            current += timedelta(days=1)
        return days, cumulative_values, daily_values

    @staticmethod
    def _forecast(daily_values: list[float], current_total: float) -> tuple[list[float], list[float], list[float]]:
        sample = daily_values[-min(len(daily_values), 14):]
        count = len(sample)
        if count == 1:
            predicted_daily = [sample[0]] * 7
            uncertainty = max(sample[0] * 0.35, 1.0)
        else:
            mean_x = (count - 1) / 2
            mean_y = sum(sample) / count
            denominator = sum((index - mean_x) ** 2 for index in range(count))
            slope = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(sample)) / denominator if denominator else 0
            intercept = mean_y - slope * mean_x
            predicted_daily = [max(intercept + slope * (count + step), 0.0) for step in range(7)]
            residuals = [value - (intercept + slope * index) for index, value in enumerate(sample)]
            uncertainty = max((sum(value * value for value in residuals) / max(count - 2, 1)) ** 0.5 * 1.96, 1.0)

        projected, lower, upper = [], [], []
        projected_total = lower_total = upper_total = current_total
        for step, daily_value in enumerate(predicted_daily, 1):
            spread = uncertainty * math.sqrt(1 + step / 7)
            projected_total += daily_value
            lower_total += max(daily_value - spread, 0.0)
            upper_total += daily_value + spread
            projected.append(projected_total)
            lower.append(lower_total)
            upper.append(upper_total)
        return projected, lower, upper

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        area = self._frame(painter, "Mots écrits cumulés par jour et projection sur 7 jours")
        days, cumulative_values, daily_values = self._series()
        if not cumulative_values:
            self._empty(painter, area)
            return
        forecast, lower, upper = self._forecast(daily_values, cumulative_values[-1])
        all_values = cumulative_values + upper
        maximum = max(max(all_values), 10.0) * 1.1
        total_points = len(cumulative_values) + 7

        def point(index: int, value: float) -> QPointF:
            x = area.left() + (index / max(total_points - 1, 1)) * area.width()
            y = area.bottom() - (value / maximum) * area.height()
            return QPointF(x, y)

        painter.setFont(QFont(painter.font().family(), 8))
        for step in range(5):
            value = maximum * step / 4
            y = point(0, value).y()
            painter.setPen(QPen(QColor("#44464d"), 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QColor("#bcbcbc"))
            painter.drawText(QRectF(0, y - 8, 52, 16), Qt.AlignmentFlag.AlignRight, str(int(value)))

        boundary = len(cumulative_values) - 1
        polygon = QPolygonF()
        for step, value in enumerate(upper, 1):
            polygon.append(point(boundary + step, value))
        for step in range(7, 0, -1):
            polygon.append(point(boundary + step, lower[step - 1]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(124, 166, 217, 55))
        painter.drawPolygon(polygon)

        actual_path = QPainterPath(point(0, cumulative_values[0]))
        for index, value in enumerate(cumulative_values[1:], 1):
            actual_path.lineTo(point(index, value))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#76b37a"), 3))
        painter.drawPath(actual_path)

        projection_path = QPainterPath(point(boundary, cumulative_values[-1]))
        for step, value in enumerate(forecast, 1):
            projection_path.lineTo(point(boundary + step, value))
        painter.setPen(QPen(QColor("#7ca6d9"), 3, Qt.PenStyle.DashLine))
        painter.drawPath(projection_path)
        painter.setPen(QPen(QColor("#d6aa4c"), 1, Qt.PenStyle.DashLine))
        boundary_x = point(boundary, 0).x()
        painter.drawLine(QPointF(boundary_x, area.top()), QPointF(boundary_x, area.bottom()))

        labels = days + [days[-1] + timedelta(days=step) for step in range(1, 8)]
        for index in sorted({0, boundary, total_points - 1}):
            x = point(index, 0).x()
            painter.setPen(QColor("#cccccc"))
            painter.drawText(QRectF(x - 38, area.bottom() + 7, 76, 18), Qt.AlignmentFlag.AlignCenter, labels[index].strftime("%d/%m"))


class WeeklyProgressChart(ChartWidget):
    def __init__(self, records: list[ProgressRecord], parent=None) -> None:
        super().__init__(parent)
        self.records = records
        self.setMinimumHeight(380)

    def _series(self) -> list[tuple[str, int, int]]:
        weeks: defaultdict[tuple[int, int], int] = defaultdict(int)
        for record in self.records:
            day = date.fromisoformat(record.day)
            iso_year, iso_week, _ = day.isocalendar()
            weeks[(iso_year, iso_week)] += record.words_written

        cumulative = 0
        entries: list[tuple[str, int, int]] = []
        for year, week in sorted(weeks):
            weekly_words = weeks[(year, week)]
            cumulative += weekly_words
            entries.append((f"S{week:02d} {year}", weekly_words, cumulative))
        return entries[-16:]

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        area = self._frame(painter, "Mots écrits par semaine et cumul total")
        entries = self._series()
        if not entries:
            self._empty(painter, area)
            return

        weekly_max = max(max(value for _, value, _ in entries), 1) * 1.18
        cumulative_max = max(max(value for _, _, value in entries), 1) * 1.12
        bar_width = area.width() / max(len(entries), 1)

        painter.setFont(QFont(painter.font().family(), 8))
        for step in range(5):
            weekly_value = weekly_max * step / 4
            y = area.bottom() - (weekly_value / weekly_max) * area.height()
            painter.setPen(QPen(QColor("#44464d"), 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QColor("#bcbcbc"))
            painter.drawText(QRectF(0, y - 8, 52, 16), Qt.AlignmentFlag.AlignRight, str(int(weekly_value)))

            cumulative_value = cumulative_max * step / 4
            painter.setPen(QColor("#76b37a"))
            painter.drawText(
                QRectF(area.right() + 6, y - 8, 74, 16),
                Qt.AlignmentFlag.AlignLeft,
                str(int(cumulative_value)),
            )

        painter.setPen(QColor("#bcbcbc"))
        painter.drawText(QRectF(4, area.top() - 22, 150, 18), Qt.AlignmentFlag.AlignLeft, "semaine")
        painter.setPen(QColor("#76b37a"))
        painter.drawText(QRectF(area.right() - 105, area.top() - 22, 170, 18), Qt.AlignmentFlag.AlignRight, "cumul")

        line_path: QPainterPath | None = None
        for index, (label, weekly_words, cumulative_words) in enumerate(entries):
            x = area.left() + index * bar_width
            bar_height = area.height() * weekly_words / weekly_max
            rect = QRectF(
                x + max(bar_width * 0.16, 3),
                area.bottom() - bar_height,
                max(bar_width * 0.68, 4),
                bar_height,
            )
            painter.fillRect(rect, QColor("#4f86c6"))
            painter.setPen(QColor("#eeeeee"))
            painter.drawText(
                QRectF(x, rect.top() - 18, bar_width, 16),
                Qt.AlignmentFlag.AlignCenter,
                str(weekly_words),
            )

            point = QPointF(
                x + bar_width / 2,
                area.bottom() - (cumulative_words / cumulative_max) * area.height(),
            )
            if line_path is None:
                line_path = QPainterPath(point)
            else:
                line_path.lineTo(point)

            painter.save()
            painter.translate(x + bar_width / 2, area.bottom() + 8)
            painter.rotate(-35)
            painter.drawText(QRectF(-55, 0, 110, 18), Qt.AlignmentFlag.AlignCenter, label)
            painter.restore()

        if line_path is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#76b37a"), 3))
            painter.drawPath(line_path)
            painter.setBrush(QColor("#f4f1ea"))
            painter.setPen(QPen(QColor("#76b37a"), 2))
            for index, (_, _, cumulative_words) in enumerate(entries):
                x = area.left() + index * bar_width + bar_width / 2
                y = area.bottom() - (cumulative_words / cumulative_max) * area.height()
                painter.drawEllipse(QPointF(x, y), 4, 4)


class BarChart(ChartWidget):
    def __init__(self, title: str, entries: list[tuple[str, int]], horizontal: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.entries = entries
        self.horizontal = horizontal
        self.setMinimumHeight(max(280, len(entries) * 30 + 80) if horizontal else 300)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        area = self._frame(painter, self.title)
        if not self.entries:
            self._empty(painter, area)
            return
        maximum = max(max(value for _, value in self.entries), 1)
        painter.setFont(QFont(painter.font().family(), 8))
        if self.horizontal:
            label_width = min(max((len(label) for label, _ in self.entries), default=10) * 7, 230)
            area.setLeft(max(area.left(), label_width + 20))
            row_height = area.height() / len(self.entries)
            for index, (label, value) in enumerate(self.entries):
                y = area.top() + index * row_height + 4
                width = area.width() * value / maximum
                painter.fillRect(QRectF(area.left(), y, width, max(row_height - 8, 5)), QColor("#7f6bb3"))
                painter.setPen(QColor("#dddddd"))
                painter.drawText(QRectF(8, y, label_width, row_height - 8), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)
                painter.drawText(QRectF(area.left() + width + 6, y, 70, row_height - 8), Qt.AlignmentFlag.AlignVCenter, str(value))
        else:
            bar_width = area.width() / max(len(self.entries), 1)
            for index, (label, value) in enumerate(self.entries):
                height = area.height() * value / maximum
                x = area.left() + index * bar_width + 4
                painter.fillRect(QRectF(x, area.bottom() - height, max(bar_width - 8, 3), height), QColor("#4f86c6"))
                painter.setPen(QColor("#eeeeee"))
                painter.drawText(QRectF(x, area.bottom() - height - 20, max(bar_width - 8, 30), 18), Qt.AlignmentFlag.AlignCenter, str(value))
                painter.save()
                painter.translate(x + bar_width / 2, area.bottom() + 8)
                painter.rotate(-35)
                painter.drawText(QRectF(-55, 0, 110, 18), Qt.AlignmentFlag.AlignCenter, label)
                painter.restore()


class CollapsibleSection(QWidget):
    def __init__(self, title: str, expanded: bool = True) -> None:
        super().__init__()
        self.setObjectName("collapsibleSection")
        self.toggle = QToolButton()
        self.toggle.setObjectName("sectionToggle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.toggle.toggled.connect(self._set_expanded)

        self.content = QWidget()
        self.content.setObjectName("sectionContent")
        self.content.setVisible(expanded)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 0, 0, 12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.content)

    def _set_expanded(self, expanded: bool) -> None:
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.content.setVisible(expanded)


class ProgressionWindow(QMainWindow):
    def __init__(self, project_root: Path, extensions: tuple[str, ...], stylesheet: str = "") -> None:
        super().__init__()
        self.tracker = ProgressTracker(project_root, extensions)
        self.editing_tracker = EditingProgressTracker(project_root, extensions)
        self.setWindowTitle(f"Progression — {project_root.name}")
        self.resize(1320, 900)
        self.setMinimumWidth(1180)
        self.setStyleSheet(
            (stylesheet or "")
            + """
            QMainWindow {
                background: #202124;
            }
            QWidget#progressionRoot,
            QWidget#chartContainer {
                background: #202124;
            }
            QToolButton#sectionToggle {
                background: #343741;
                color: #f4f1ea;
                border: 1px solid #4a4e5a;
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 15px;
                font-weight: 800;
                text-align: left;
            }
            QToolButton#sectionToggle:hover {
                background: #404452;
                border-color: #7ca6d9;
            }
            QWidget#sectionContent {
                background: #26272d;
                border-left: 3px solid #7ca6d9;
                border-radius: 4px;
            }
            QPushButton {
                background: #76b37a;
                color: #111318;
                border: none;
                border-radius: 5px;
                padding: 7px 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #8bc58e;
            }
            QProgressBar {
                background: #1f2025;
                color: #f4f1ea;
                border: 1px solid #3d414b;
                border-radius: 6px;
                text-align: center;
                font-weight: 700;
            }
            QProgressBar::chunk {
                background: #7ca6d9;
                border-radius: 5px;
            }
            """
        )

        central = QWidget()
        central.setObjectName("progressionRoot")
        self.layout = QVBoxLayout(central)
        header = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #f2f2f2;")
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh_report)
        header.addWidget(self.summary, 1)
        header.addWidget(refresh)
        self.chart_container = QWidget()
        self.chart_container.setObjectName("chartContainer")
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.writing_section = CollapsibleSection("Écriture", True)
        self.editing_section = CollapsibleSection("Édition", True)
        self.chart_layout.addWidget(self.writing_section)
        self.chart_layout.addWidget(self.editing_section)
        self.chart_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.chart_container)
        self.layout.addLayout(header)
        self.layout.addWidget(scroll, 1)
        self.setCentralWidget(central)
        self.refresh_report()

    @staticmethod
    def _aggregates(
        records: list[ProgressRecord],
        field_name: str,
    ) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
        weeks: defaultdict[tuple[int, int], int] = defaultdict(int)
        months: defaultdict[tuple[int, int], int] = defaultdict(int)
        for record in records:
            day = date.fromisoformat(record.day)
            iso_year, iso_week, _ = day.isocalendar()
            value = int(getattr(record, field_name, 0))
            weeks[(iso_year, iso_week)] += value
            months[(day.year, day.month)] += value
        weekly = [(f"S{week:02d} {year}", value) for (year, week), value in sorted(weeks.items())]
        monthly = [(f"{month:02d}/{year}", value) for (year, month), value in sorted(months.items())]
        return weekly, monthly

    @staticmethod
    def _placeholder_records() -> list[ProgressRecord]:
        """Produit une démonstration visuelle sans modifier le journal réel."""
        records: list[ProgressRecord] = []
        total = 18_400
        last_files = {
            "chapitres/chapitre_01.txt": 4_850,
            "chapitres/chapitre_02.txt": 5_620,
            "chapitres/chapitre_03.txt": 4_130,
            "notes/personnages.md": 1_480,
            "notes/univers.md": 2_320,
        }
        start = date.today() - timedelta(days=34)
        for index in range(35):
            current = start + timedelta(days=index)
            if current.weekday() >= 5:
                written = (0, 180, 260, 90)[index % 4]
            else:
                written = 310 + (index * 83) % 620
                if index % 9 == 0:
                    written = 0
            total += written
            records.append(
                ProgressRecord(
                    current.isoformat(),
                    written,
                    written + ((index * 41) % 280),
                    total,
                    dict(last_files),
                )
            )
        records[-1].files = last_files
        records[-1].total_words = sum(last_files.values())
        return records

    def refresh_report(self) -> None:
        try:
            records = self.tracker.load_records()
        except Exception as exc:
            QMessageBox.critical(self, "Journal invalide", str(exc))
            records = []
        showing_placeholders = not records
        if showing_placeholders:
            records = self._placeholder_records()
        self._clear_layout(self.writing_section.content_layout)
        self._clear_layout(self.editing_section.content_layout)
        total_written = sum(record.words_written for record in records)
        total_changed = sum(record.words_changed for record in records)
        current_total = records[-1].total_words if records else 0
        days_active = sum(record.words_written > 0 or record.words_changed > 0 for record in records)
        placeholder_notice = (
            "<p style='color:#d6aa4c'><b>Données d’exemple</b> — "
            "elles disparaîtront dès la première sauvegarde réelle.</p>"
            if showing_placeholders
            else ""
        )
        self.summary.setText(
            f"<h2>Progression du roman</h2>{placeholder_notice}"
            f"Total actuel : <b>{current_total:,}</b> mots · "
            f"Ajouts suivis : <b>{total_written:,}</b> mots · "
            f"Mots remaniés : <b>{total_changed:,}</b> · "
            f"Jours actifs : <b>{days_active}</b>"
        )
        _, monthly = self._aggregates(records, "words_written")
        changed_weekly, changed_monthly = self._aggregates(records, "words_changed")
        files = sorted((records[-1].files.items() if records else []), key=lambda item: item[1], reverse=True)
        self.writing_section.content_layout.addWidget(WeeklyProgressChart(records))
        self.writing_section.content_layout.addWidget(BarChart("Mots écrits par mois", monthly[-12:]))
        self.writing_section.content_layout.addWidget(BarChart("Mots remaniés par semaine", changed_weekly[-16:]))
        self.writing_section.content_layout.addWidget(BarChart("Mots remaniés par mois", changed_monthly[-12:]))
        self.writing_section.content_layout.addWidget(BarChart("Nombre de mots par fichier", files, horizontal=True))
        self._populate_editing_section()

    def _populate_editing_section(self) -> None:
        try:
            summary = self.editing_tracker.summary()
        except Exception as exc:
            QMessageBox.critical(self, "Suivi d'édition invalide", str(exc))
            return

        if summary.chapter_count == 0:
            label = QLabel("Aucun chapitre numéroté trouvé pour le suivi d'édition.")
            label.setStyleSheet("color: #d6aa4c;")
            self.editing_section.content_layout.addWidget(label)
            return

        overview = QLabel(
            f"<h3>Complétion de l'édition complète du roman : "
            f"{summary.overall_completion:.0f}%</h3>"
            f"<p>{summary.chapter_count} chapitre(s) suivis.</p>"
        )
        overview.setStyleSheet("color: #eeeeee;")
        self.editing_section.content_layout.addWidget(overview)
        self.editing_section.content_layout.addWidget(self._progress_bar(summary.overall_completion))

        for phase in summary.phase_summaries:
            label = QLabel(
                f"{phase.name} - {phase.average_completion:.0f}% "
                f"(pondération {phase.weight}%)"
            )
            label.setStyleSheet("color: #eeeeee;")
            self.editing_section.content_layout.addWidget(label)
            self.editing_section.content_layout.addWidget(self._progress_bar(phase.average_completion))

        status_entries = [(name, count) for name, count in summary.status_counts.items() if count]
        self.editing_section.content_layout.addWidget(
            BarChart("Chapitres par statut d'édition", status_entries, horizontal=True)
        )

    def _progress_bar(self, value: float) -> QProgressBar:
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(round(value))
        bar.setTextVisible(True)
        bar.setFormat("%p%")
        bar.setMinimumHeight(22)
        return bar

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
