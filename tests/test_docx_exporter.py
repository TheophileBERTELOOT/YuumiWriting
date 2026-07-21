import tempfile
import unittest
import zipfile
from pathlib import Path

from app.core.docx_exporter import DocxProjectExporter


class DocxExporterTest(unittest.TestCase):
    def test_exports_numbered_latex_chapters_as_valid_docx(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            texts = root / "Textes"
            texts.mkdir()
            (texts / "chapitre 1.tex").write_text(
                "\\chapter{Le début}\n\nBonjour \\emph{Yuumi}.\n\n\\scenechange",
                encoding="utf-8",
            )
            output = root / "roman.docx"

            result = DocxProjectExporter(root, (".tex",)).export_docx(output)

            self.assertEqual(1, result.source_count)
            with zipfile.ZipFile(output) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("Le début", document)
            self.assertIn("Bonjour Yuumi.", document)
            self.assertIn("* * *", document)


if __name__ == "__main__":
    unittest.main()
