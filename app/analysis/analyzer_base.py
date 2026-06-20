from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class Indicator:
    name: str
    value: str
    detail: str = ""
    severity: str = "info"  # info | warning | danger | success
    distribution: tuple[tuple[str, int], ...] = ()
    report_items: tuple[tuple[str, int], ...] = ()
    report_sections: tuple[
        tuple[str, int, tuple[tuple[str, int], ...]], ...
    ] = ()


class TextAnalyzer(ABC):
    """Interface commune pour tous les analyseurs.

    Ajoute un nouveau fichier dans app/analysis/, hérite de TextAnalyzer,
    puis enregistre ton analyseur dans registry.py.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    def indicator_names(self) -> tuple[str, ...]:
        demo_text = "Ceci est une phrase de test."
        return tuple(indicator.name for indicator in self.analyze(demo_text))

    @abstractmethod
    def analyze(self, text: str) -> list[Indicator]:
        raise NotImplementedError
