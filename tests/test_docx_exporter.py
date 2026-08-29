import tempfile
import unittest
import zipfile
from pathlib import Path

from app.core.docx_exporter import DocxProjectExporter
from app.core.latex_exporter import COMMANDS_FILENAME


class DocxExporterTest(unittest.TestCase):
    def test_exports_numbered_latex_chapters_as_valid_docx(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            texts = root / "Textes"
            texts.mkdir()
            (texts / "chapitre 1.tex").write_text(
                "\\chapter{Le début}\n\nBonjour \\rep{Yuumi}.\n\n\\scenechange",
                encoding="utf-8",
            )
            output = root / "roman.docx"

            result = DocxProjectExporter(root, (".tex",)).export_docx(output)

            self.assertEqual(1, result.source_count)
            with zipfile.ZipFile(output) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("Le début", document)
            self.assertIn("Bonjour — Yuumi.", document)
            self.assertIn("* * *", document)
            self.assertIn('<w:jc w:val="center"/>', document)

    def test_uses_english_quotes_for_dialogue_in_english_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            texts = root / "Textes"
            texts.mkdir()
            (root / COMMANDS_FILENAME).write_text(
                "% YuumiWriting language: use fr or en\n"
                r"\newcommand{\yuumilanguage}{en}" "\n"
                r"\usepackage{ifthen}" "\n"
                r"\usepackage[english,french]{babel}" "\n"
                r"\newcommand{\rep}[1]{\ifthenelse{\equal{\yuumilanguage}{en}}{``#1''}{--- #1}}",
                encoding="utf-8",
            )
            (texts / "chapter 1.tex").write_text(
                r"\chapter{Beginning}" "\n\n" r"\rep{Hello there.}",
                encoding="utf-8",
            )
            output = root / "novel.docx"

            DocxProjectExporter(root, (".tex",)).export_docx(output)

            with zipfile.ZipFile(output) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("“Hello there.”", document)
            self.assertNotIn("— Hello there.", document)


if __name__ == "__main__":
    unittest.main()
