import tempfile
import unittest
from pathlib import Path

from app.core.latex_exporter import COMMANDS_FILENAME, ensure_project_latex_defaults

INLINE_SCENECHANGE = r"\newcommand{\scenechange}{\par\bigskip\noindent\hfill * * *\hfill\null\par\bigskip}"
OLD_SCENECHANGE = r"\newcommand{\scenechange}{\par\bigskip\begin{center}* * *\end{center}\bigskip\par}"


class LatexExporterTest(unittest.TestCase):
    def test_rep_command_defaults_to_inline_dash_for_pdf_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            ensure_project_latex_defaults(root)

            commands = (root / COMMANDS_FILENAME).read_text(encoding="utf-8")
            self.assertIn(r"\newcommand{\rep}[1]{--- #1}", commands)
            self.assertNotIn(r"\newcommand{\rep}[1]{\par\noindent--- #1\par}", commands)
            self.assertIn(INLINE_SCENECHANGE, commands)
            self.assertNotIn(OLD_SCENECHANGE, commands)

    def test_rep_command_migrates_old_paragraph_definition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / COMMANDS_FILENAME).write_text(
                r"\newcommand{\rep}[1]{\par\noindent--- #1\par}",
                encoding="utf-8",
            )

            ensure_project_latex_defaults(root)

            commands = (root / COMMANDS_FILENAME).read_text(encoding="utf-8")
            self.assertIn(r"\newcommand{\rep}[1]{--- #1}", commands)
            self.assertNotIn(r"\newcommand{\rep}[1]{\par\noindent--- #1\par}", commands)

    def test_scenechange_command_migrates_to_centered_definition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / COMMANDS_FILENAME).write_text(OLD_SCENECHANGE, encoding="utf-8")

            ensure_project_latex_defaults(root)

            commands = (root / COMMANDS_FILENAME).read_text(encoding="utf-8")
            self.assertIn(INLINE_SCENECHANGE, commands)
            self.assertNotIn(OLD_SCENECHANGE, commands)


if __name__ == "__main__":
    unittest.main()
