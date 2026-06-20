from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMAnalysisDefinition:
    key: str
    name: str
    instruction: str


DEFAULT_LLM_ANALYSES: tuple[LLMAnalysisDefinition, ...] = (
    LLMAnalysisDefinition(
        "sentence_opening_repetition",
        "Répétitions de débuts de phrase",
        "Examine les un à trois premiers mots significatifs de chaque phrase ET leur structure "
        "syntaxique. Compte et signale les séries rapprochées de pronoms identiques ou alternés "
        "(par exemple Il/Elle/Il), de noms propres, d'articles ou de constructions semblables. "
        "Une alternance de pronoms ne constitue pas à elle seule une vraie variété.",
    ),
    LLMAnalysisDefinition(
        "awkward_words",
        "Mots maladroits",
        "Repère les mots imprécis, faibles, inutilement compliqués, peu naturels ou mal "
        "adaptés au registre et au contexte.",
    ),
    LLMAnalysisDefinition(
        "awkward_sentences",
        "Phrases maladroites",
        "Évalue la clarté et le naturel des phrases. Repère les formulations bancales, "
        "ambiguës, lourdes ou difficiles à comprendre.",
    ),
    LLMAnalysisDefinition(
        "passive_voice",
        "Phrases passives",
        "Évalue la maîtrise de la voix passive. Signale les passifs inutiles qui affaiblissent "
        "l'action, sans pénaliser ceux qui sont justifiés par le contexte.",
    ),
    LLMAnalysisDefinition(
        "adverb_usage",
        "Utilisation d’adverbes",
        "Évalue si les adverbes sont précis et utiles. Repère leur accumulation, les adverbes "
        "redondants et ceux qui remplacent un verbe ou une description plus forte.",
    ),
    LLMAnalysisDefinition(
        "readability",
        "Lisibilité",
        "Évalue la facilité de lecture, la clarté des enchaînements et l'effort demandé au "
        "lecteur, en tenant compte d'un texte littéraire destiné à des adultes.",
    ),
    LLMAnalysisDefinition(
        "length_variation",
        "Variation de longueur",
        "Évalue la variété intentionnelle de longueur et de structure des phrases. Repère une "
        "succession trop uniforme ou, au contraire, des variations désordonnées.",
    ),
    LLMAnalysisDefinition(
        "glue_words",
        "Glue words",
        "Évalue l'excès de mots-outils et de liaisons qui collent artificiellement les idées "
        "(prépositions, conjonctions et formulations de remplissage) et diluent le propos.",
    ),
    LLMAnalysisDefinition(
        "complex_paragraphs",
        "Paragraphes complexes",
        "Évalue la structure des paragraphes. Repère ceux qui cumulent trop d'idées, manquent "
        "de fil directeur ou gagneraient à être divisés.",
    ),
    LLMAnalysisDefinition(
        "slow_pacing",
        "Rythme lent",
        "Évalue la maîtrise du rythme et repère les passages qui stagnent à cause de "
        "répétitions, d'explications, de descriptions ou d'actions sans progression.",
    ),
    LLMAnalysisDefinition(
        "emotions",
        "Émotions",
        "Évalue la force, la précision et la crédibilité émotionnelles du texte, notamment le "
        "rapport entre émotions montrées, ressenties et simplement nommées.",
    ),
    LLMAnalysisDefinition(
        "sensory_detail",
        "Sensoriel",
        "Évalue la présence, la variété et la pertinence des détails sensoriels, sans exiger "
        "artificiellement les cinq sens dans chaque passage.",
    ),
)


class LLMAnalysisRegistry:
    """Catalogue séparé des analyses distantes.

    Les définitions seront ajoutées ici plus tard. Une requête distante demande
    toujours toutes les définitions en une fois; les cases cochées contrôlent
    uniquement le déclenchement et l'affichage.
    """

    def __init__(self) -> None:
        self._definitions = DEFAULT_LLM_ANALYSES

    @property
    def definitions(self) -> tuple[LLMAnalysisDefinition, ...]:
        return self._definitions

    def register(self, definition: LLMAnalysisDefinition) -> None:
        if any(item.key == definition.key for item in self._definitions):
            raise ValueError(f"Clé d'analyse LLM déjà utilisée : {definition.key}")
        self._definitions = (*self._definitions, definition)

    def names(self) -> list[str]:
        return [definition.name for definition in self._definitions]

    def by_name(self, name: str) -> LLMAnalysisDefinition | None:
        return next((item for item in self._definitions if item.name == name), None)
