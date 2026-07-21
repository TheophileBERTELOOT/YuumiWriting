import unittest
from unittest.mock import patch

from app.utils.synonyms import find_api_synonyms, find_synonyms


class SynonymsTest(unittest.TestCase):
    def test_finds_synonyms_for_known_words(self) -> None:
        self.assertIn("joli", find_synonyms("beau"))
        self.assertIn("magnifique", find_synonyms("beau"))

    def test_is_case_insensitive(self) -> None:
        self.assertIn("joli", find_synonyms("BEAU"))
        self.assertIn("vaste", find_synonyms("grand"))

    @patch("app.utils.synonyms._wiktionary_request")
    def test_api_reads_only_french_synonym_sections(self, request) -> None:
        find_api_synonyms.cache_clear()
        request.side_effect = [
            {
                "parse": {
                    "sections": [
                        {"level": "2", "line": "Français", "index": "1"},
                        {"level": "4", "line": "Synonymes", "index": "3"},
                        {"level": "2", "line": "Anglais", "index": "4"},
                        {"level": "4", "line": "Synonymes", "index": "6"},
                    ]
                }
            },
            {
                "parse": {
                    "text": {
                        "*": '<ul><li><a href="/wiki/jolie">jolie</a></li>'
                        '<li><a href="/wiki/magnifique">magnifique</a></li></ul>'
                    }
                }
            },
        ]

        suggestions, error = find_api_synonyms("belle")

        self.assertEqual("", error)
        self.assertEqual(["jolie", "magnifique"], suggestions)
        self.assertEqual(2, request.call_count)

    @patch("app.utils.synonyms._wiktionary_request", side_effect=OSError("offline"))
    def test_api_reports_connection_errors(self, _request) -> None:
        find_api_synonyms.cache_clear()
        suggestions, error = find_api_synonyms("beau")

        self.assertEqual([], suggestions)
        self.assertIn("Connexion", error)


if __name__ == "__main__":
    unittest.main()
