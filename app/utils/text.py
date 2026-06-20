from __future__ import annotations

import re
from threading import RLock
from typing import Any


class SpacyUnavailableError(RuntimeError):
    pass


_TOKENIZER: Any = None
_LEMMA_PIPELINE: Any = None
_TOKENIZER_LOCK = RLock()
_LEMMA_LOCK = RLock()


def french_tokenizer_doc(text: str) -> Any:
    """Tokenise le français et segmente les phrases sans charger un gros modèle."""
    global _TOKENIZER

    with _TOKENIZER_LOCK:
        if _TOKENIZER is None:
            try:
                from spacy.lang.fr import French
            except ImportError as exc:
                raise SpacyUnavailableError(
                    "Installe spaCy avec `pip install -r requirements.txt`."
                ) from exc
            _TOKENIZER = French()
            _TOKENIZER.add_pipe("sentencizer")
        return _TOKENIZER(text)


def french_lemma_doc(text: str) -> Any:
    """Analyse le texte avec le modèle français spaCy et produit les lemmes."""
    global _LEMMA_PIPELINE

    with _LEMMA_LOCK:
        if _LEMMA_PIPELINE is None:
            try:
                import spacy

                _LEMMA_PIPELINE = spacy.load(
                    "fr_core_news_sm",
                    disable=["ner", "parser"],
                )
            except ImportError as exc:
                raise SpacyUnavailableError(
                    "Installe spaCy avec `pip install -r requirements.txt`."
                ) from exc
            except OSError as exc:
                raise SpacyUnavailableError(
                    "Le modèle fr_core_news_sm est absent. Relance "
                    "`pip install -r requirements.txt`."
                ) from exc
        return _LEMMA_PIPELINE(text)


def lexical_tokens(doc: Any) -> list[Any]:
    return [token for token in doc if token.is_alpha or token.like_num]


def words(text: str) -> list[str]:
    return [token.text for token in lexical_tokens(french_tokenizer_doc(text))]


def sentences(text: str) -> list[str]:
    return [sentence.text.strip() for sentence in french_tokenizer_doc(text).sents]


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
