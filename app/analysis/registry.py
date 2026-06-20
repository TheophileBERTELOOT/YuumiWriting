from __future__ import annotations

from app.analysis.basic_stats import BasicStatsAnalyzer
from app.analysis.analyzer_base import TextAnalyzer, Indicator
from app.analysis.repetitions import RepetitionAnalyzer
from app.analysis.word_nature import WordNatureAnalyzer


class AnalyzerRegistry:
    def __init__(self) -> None:
        self._analyzers: list[TextAnalyzer] = [
            BasicStatsAnalyzer(),
            RepetitionAnalyzer(),
            WordNatureAnalyzer(),
        ]

    def register(self, analyzer: TextAnalyzer) -> None:
        self._analyzers.append(analyzer)

    def available_indicator_names(self) -> list[str]:
        """Retourne les noms possibles des indicateurs.

        On analyse une phrase factice pour obtenir la liste stable des cartes
        produites par les analyseurs enregistrés.
        """
        return [
            indicator_name
            for analyzer in self._analyzers
            for indicator_name in analyzer.indicator_names
        ]

    def analyze_selected(self, text: str, names: set[str]) -> list[Indicator]:
        indicators: list[Indicator] = []
        for analyzer in self._analyzers:
            if names.intersection(analyzer.indicator_names):
                indicators.extend(analyzer.analyze(text))
        return [indicator for indicator in indicators if indicator.name in names]

    def analyze_all(self, text: str) -> list[Indicator]:
        indicators: list[Indicator] = []
        for analyzer in self._analyzers:
            indicators.extend(analyzer.analyze(text))
        return indicators
