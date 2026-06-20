from __future__ import annotations

from collections import Counter
from typing import Any

from app.analysis.analyzer_base import Indicator, TextAnalyzer
from app.utils.text import SpacyUnavailableError, french_tokenizer_doc


class RepetitionAnalyzer(TextAnalyzer):
    INDICATOR_NAMES = ("Répétition de phrases", "Répétition de mots")

    @property
    def name(self) -> str:
        return "Répétitions"

    @property
    def indicator_names(self) -> tuple[str, ...]:
        return self.INDICATOR_NAMES

    def analyze(self, text: str) -> list[Indicator]:
        try:
            doc = french_tokenizer_doc(text)
        except SpacyUnavailableError as exc:
            return [
                Indicator(
                    name,
                    "spaCy indisponible",
                    str(exc),
                    "danger",
                )
                for name in self.INDICATOR_NAMES
            ]

        return [
            self._indicator(
                "phrase",
                "phrases",
                self._repeated_sentences(doc),
            ),
            self._indicator(
                "mot",
                "mots",
                self._repeated_words(doc),
            ),
        ]

    @staticmethod
    def _indicator(
        singular: str,
        plural: str,
        items: tuple[tuple[str, int], ...],
    ) -> Indicator:
        name = f"Répétition de {plural}"
        unique_count = len(items)
        extra_occurrences = sum(count - 1 for _, count in items)
        noun = singular if unique_count == 1 else plural
        adjective = (
            "répétée" if singular == "phrase" else "répété"
        ) + ("s" if unique_count != 1 else "")
        detail = (
            f"{extra_occurrences} occurrence"
            f"{'s' if extra_occurrences != 1 else ''} supplémentaire"
            f"{'s' if extra_occurrences != 1 else ''}."
        )
        return Indicator(
            name=name,
            value=f"{unique_count} {noun} {adjective}",
            detail=detail,
            severity="warning" if items else "success",
            report_items=items,
        )

    @staticmethod
    def _repeated_words(doc: Any) -> tuple[tuple[str, int], ...]:
        normalized_words = [
            token.text.casefold()
            for token in doc
            if len(token.text) >= 3 and not token.is_stop and token.is_alpha
        ]
        counts = Counter(normalized_words)
        repeated = [(word, count) for word, count in counts.items() if count > 1]
        return tuple(sorted(repeated, key=lambda item: (-item[1], item[0])))

    @staticmethod
    def _repeated_sentences(doc: Any) -> tuple[tuple[str, int], ...]:
        normalized_sentences: list[str] = []
        display_forms: dict[str, str] = {}

        for sentence in doc.sents:
            normalized = " ".join(
                token.text.casefold()
                for token in sentence
                if not token.is_space and not token.is_punct
            )
            if not normalized:
                continue
            normalized_sentences.append(normalized)
            display_forms.setdefault(normalized, sentence.text.strip())

        counts = Counter(normalized_sentences)
        repeated = [
            (display_forms[sentence], count)
            for sentence, count in counts.items()
            if count > 1
        ]
        return tuple(sorted(repeated, key=lambda item: (-item[1], item[0].casefold())))
