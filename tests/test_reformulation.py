import unittest
from pathlib import Path
from unittest.mock import patch

from app.utils.reformulation import generate_reformulations


class ReformulationTest(unittest.TestCase):
    def test_requires_openai_project_root(self) -> None:
        suggestions, error = generate_reformulations("La ville sombrait dans la nuit.")

        self.assertEqual([], suggestions)
        self.assertIn("OpenAI", error)

    def test_uses_openai_reformulations(self) -> None:
        with patch(
            "app.utils.reformulation._openai_reformulations",
            return_value=[
                "Le cri monta, de plus en plus aigu, jusqu'à saturer l'air autour des vitrines.",
                "Peu à peu, le sifflement envahit la rue et vrilla les tempes des passants.",
                "La plainte sonore enfla dans tout l'espace, clouant clients et promeneurs de douleur.",
            ],
        ) as openai_reformulations:
            suggestions, error = generate_reformulations(
                "Le sifflement strident prit de l'ampleur.",
                project_root=Path("/tmp/roman"),
            )

        self.assertEqual("", error)
        self.assertEqual(3, len(suggestions))
        openai_reformulations.assert_called_once()

    def test_filters_tiny_variations(self) -> None:
        with patch(
            "app.utils.reformulation._openai_reformulations",
            return_value=[
                "La ville sombrait dans la nuit.",
                "La ville sombre dans la nuit.",
                "La cité se laissait lentement avaler par l'obscurité.",
            ],
        ):
            suggestions, error = generate_reformulations(
                "La ville sombrait dans la nuit.",
                project_root=Path("/tmp/roman"),
            )

        self.assertEqual(["La cité se laissait lentement avaler par l'obscurité."], suggestions)
        self.assertEqual("", error)

    def test_parses_numbered_fallback_output(self) -> None:
        with patch(
            "app.utils.reformulation._openai_reformulations",
            return_value=[
                "La nuit descendait doucement sur la ville.",
                "Un calme nocturne enveloppait peu à peu la ville.",
                "Le soir déposait sa douceur sur les rues.",
            ],
        ):
            suggestions, error = generate_reformulations(
                "La ville sombrait dans la nuit.",
                project_root=Path("/tmp/roman"),
            )

        self.assertEqual("", error)
        self.assertEqual(3, len(suggestions))

    def test_rejects_empty_selection(self) -> None:
        suggestions, error = generate_reformulations("   ", project_root=Path("/tmp/roman"))

        self.assertEqual([], suggestions)
        self.assertIn("Sélection vide", error)


if __name__ == "__main__":
    unittest.main()
