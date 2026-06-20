from __future__ import annotations

from collections import Counter
from threading import RLock
from typing import Any

from app.analysis.analyzer_base import Indicator, TextAnalyzer
from app.utils.text import french_lemma_doc


MODEL_NAME = "qanastek/pos-french-camembert"
CATEGORY_NAMES = ("Sujets", "Verbes", "Adverbes", "Adjectifs", "Autres")

SUBJECT_LABELS = {
    "NOUN",
    "NMS",
    "NMP",
    "NFS",
    "NFP",
    "PROPN",
    "XFAMIL",
    "PRON",
    "PPER1S",
    "PPER2S",
    "PPER3MS",
    "PPER3MP",
    "PPER3FS",
    "PPER3FP",
}
VERB_LABELS = {"VERB", "AUX", "VPPRE", "VPPMS", "VPPMP", "VPPFS", "VPPFP"}
ADJECTIVE_LABELS = {
    "ADJ",
    "ADJMS",
    "ADJMP",
    "ADJFS",
    "ADJFP",
    "NUM",
    "DINTMS",
    "DINTFS",
}


class WordNatureAnalyzer(TextAnalyzer):
    def __init__(self) -> None:
        self._tokenizer: Any = None
        self._model: Any = None
        self._analysis_lock = RLock()

    @property
    def name(self) -> str:
        return "Nature grammaticale"

    @property
    def indicator_names(self) -> tuple[str, ...]:
        return ("Nature",)

    def analyze(self, text: str) -> list[Indicator]:
        if not text.strip():
            return [self._indicator(self._empty_categories())]

        try:
            with self._analysis_lock:
                categories = self._predict(text)
        except (ImportError, OSError, RuntimeError) as exc:
            return [self._error_indicator(exc)]
        return [self._indicator(categories)]

    def _predict(self, text: str) -> dict[str, Counter[str]]:
        self._load_model()
        import torch

        categories = self._empty_categories()
        for chunk in self._text_chunks(text):
            prepared_text, lemmas = self._prepare_for_pos(chunk)
            if not prepared_text:
                continue
            encoded = self._tokenizer(
                prepared_text,
                return_offsets_mapping=True,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )
            offsets = encoded.pop("offset_mapping")[0].tolist()
            with torch.inference_mode():
                label_ids = self._model(**encoded).logits.argmax(dim=-1)[0].tolist()

            predictions = [
                (start, end, self._model.config.id2label[label_id])
                for (start, end), label_id in zip(offsets, label_ids)
                if end > start
            ]
            for lemma, start, end in lemmas:
                label = self._label_for_span(
                    start,
                    end,
                    predictions,
                )
                categories[self._category_for_label(label)][lemma] += 1
        return categories

    @staticmethod
    def _prepare_for_pos(chunk: str) -> tuple[str, list[tuple[str, int, int]]]:
        lemmas = [
            (token.lemma_ or token.text).casefold().strip()
            for token in french_lemma_doc(chunk)
            if not token.is_stop and token.is_alpha
        ]
        lemmas = [lemma for lemma in lemmas if lemma]

        prepared_parts: list[str] = []
        spans: list[tuple[str, int, int]] = []
        cursor = 0
        for lemma in lemmas:
            if prepared_parts:
                cursor += 1
            start = cursor
            prepared_parts.append(lemma)
            cursor += len(lemma)
            spans.append((lemma, start, cursor))
        return " ".join(prepared_parts), spans

    def _load_model(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
        self._model = AutoModelForTokenClassification.from_pretrained(MODEL_NAME)
        self._model.eval()

    @staticmethod
    def _label_for_span(
        word_start: int,
        word_end: int,
        predictions: list[tuple[int, int, str]],
    ) -> str:
        for token_start, token_end, label in predictions:
            if token_start < word_end and token_end > word_start:
                return label
        return "X"

    @staticmethod
    def _category_for_label(label: str) -> str:
        if label in SUBJECT_LABELS:
            return "Sujets"
        if label in VERB_LABELS:
            return "Verbes"
        if label == "ADV":
            return "Adverbes"
        if label in ADJECTIVE_LABELS:
            return "Adjectifs"
        return "Autres"

    @staticmethod
    def _text_chunks(text: str, maximum_length: int = 1400) -> list[str]:
        chunks: list[str] = []
        remaining = text
        while len(remaining) > maximum_length:
            cut = remaining.rfind(" ", 0, maximum_length)
            if cut < maximum_length // 2:
                cut = maximum_length
            chunks.append(remaining[:cut])
            remaining = remaining[cut:]
        if remaining:
            chunks.append(remaining)
        return chunks

    @staticmethod
    def _empty_categories() -> dict[str, Counter[str]]:
        return {name: Counter() for name in CATEGORY_NAMES}

    @staticmethod
    def _indicator(categories: dict[str, Counter[str]]) -> Indicator:
        sections = tuple(
            (
                category,
                sum(counts.values()),
                tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
            )
            for category, counts in categories.items()
        )
        total = sum(section_total for _, section_total, _ in sections)
        return Indicator(
            name="Nature",
            value=f"{total} mot{'s' if total != 1 else ''} classé{'s' if total != 1 else ''}",
            detail=(
                "Texte tokenisé, lemmatisé et nettoyé des stop words avec spaCy, "
                "puis classé par qanastek/pos-french-camembert. La section "
                "Sujets regroupe les noms, noms propres et pronoms sujets potentiels."
            ),
            severity="info",
            report_sections=sections,
        )

    @staticmethod
    def _error_indicator(exc: Exception) -> Indicator:
        sections = tuple((name, 0, ()) for name in CATEGORY_NAMES)
        return Indicator(
            name="Nature",
            value="Modèle indisponible",
            detail=f"Impossible de charger {MODEL_NAME} : {exc}",
            severity="danger",
            report_sections=sections,
        )
