from __future__ import annotations

import statistics

from app.analysis.analyzer_base import Indicator, TextAnalyzer
from app.utils.text import (
    SpacyUnavailableError,
    french_tokenizer_doc,
    lexical_tokens,
    paragraphs,
)


class BasicStatsAnalyzer(TextAnalyzer):
    INDICATOR_NAMES = (
        "Mots",
        "Phrases",
        "Paragraphes",
        "Longueur des phrases",
        "Variation des phrases",
    )

    @property
    def name(self) -> str:
        return "Statistiques de base"

    @property
    def indicator_names(self) -> tuple[str, ...]:
        return self.INDICATOR_NAMES

    def analyze(self, text: str) -> list[Indicator]:
        try:
            doc = french_tokenizer_doc(text)
        except SpacyUnavailableError as exc:
            return [
                Indicator(name, "spaCy indisponible", str(exc), "danger")
                for name in self.INDICATOR_NAMES
            ]

        word_list = lexical_tokens(doc)
        sentence_list = list(doc.sents)
        paragraph_list = paragraphs(text)

        sentence_lengths = [len(lexical_tokens(sentence)) for sentence in sentence_list]
        stdev_sentence_len = statistics.pstdev(sentence_lengths) if len(sentence_lengths) > 1 else 0

        return [
            Indicator("Mots", str(len(word_list)), "Nombre total de mots."),
            Indicator("Phrases", str(len(sentence_list)), "Nombre total de phrases."),
            Indicator("Paragraphes", str(len(paragraph_list)), "Nombre total de paragraphes."),
            Indicator(
                "Longueur des phrases",
                "",
                "Distribution du nombre de mots par phrase.",
                "info",
                self._sentence_length_distribution(sentence_lengths),
            ),
            Indicator(
                "Variation des phrases",
                f"σ = {stdev_sentence_len:.1f}",
                "Plus l'écart-type est élevé, plus tes phrases varient en longueur.",
                "success" if stdev_sentence_len >= 7 else "warning",
            ),
        ]

    @staticmethod
    def _sentence_length_distribution(
        sentence_lengths: list[int],
    ) -> tuple[tuple[str, int], ...]:
        bins = (
            ("1–5", 1, 5),
            ("6–10", 6, 10),
            ("11–15", 11, 15),
            ("16–20", 16, 20),
            ("21–25", 21, 25),
            ("26–34", 26, 34),
            ("35+", 35, None),
        )
        return tuple(
            (
                label,
                sum(
                    1
                    for length in sentence_lengths
                    if length >= minimum
                    and (maximum is None or length <= maximum)
                ),
            )
            for label, minimum, maximum in bins
        )
