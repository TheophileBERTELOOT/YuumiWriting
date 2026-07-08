from __future__ import annotations

import shutil
import subprocess
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.text_corpus import iter_text_files


COMMANDS_FILENAME = "yuumi_commands.tex"
BUILD_DIRNAME = ".yuumi_latex"
IGNORED_LATEX_DIRECTORIES = {BUILD_DIRNAME.casefold(), "notes"}


DEFAULT_COMMANDS = r"""\usepackage[french]{babel}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage[a5paper,margin=18mm]{geometry}

\setstretch{1.12}
\setlength{\parindent}{1.2em}
\setlength{\parskip}{0.15em}

\titleformat{\chapter}[display]
  {\normalfont\huge\bfseries\centering}
  {}
  {0pt}
  {}

\newcommand{\rep}[1]{\par\noindent--- #1\par}
\newcommand{\scenechange}{\par\bigskip\begin{center}* * *\end{center}\bigskip\par}
\newcommand{\chaptersubtitle}[1]{\begin{center}\large\itshape #1\end{center}\medskip}
"""


@dataclass(slots=True)
class LatexExportResult:
    pdf_path: Path
    master_tex_path: Path
    log_path: Path
    source_count: int


class LatexExportError(RuntimeError):
    pass


def ensure_project_latex_defaults(project_root: Path) -> Path:
    project_root = project_root.resolve()
    notes_dir = project_root / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    commands_path = project_root / COMMANDS_FILENAME
    if not commands_path.exists():
        commands_path.write_text(DEFAULT_COMMANDS, encoding="utf-8")
    return commands_path


class LatexProjectExporter:
    def __init__(self, project_root: Path, extensions: tuple[str, ...]) -> None:
        self.project_root = project_root.resolve()
        self.extensions = extensions

    def export_pdf(self, output_path: Path) -> LatexExportResult:
        commands_path = ensure_project_latex_defaults(self.project_root)
        output_path = output_path.expanduser().resolve()
        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        source_paths = self.source_paths()
        if not source_paths:
            raise LatexExportError(
                "Aucun fichier numerote trouve pour la compilation PDF. "
                "Renomme les chapitres avec un chiffre, par exemple chapitre 1.tex, chapitre 2.tex."
            )

        compiler = self._find_compiler()
        if compiler is None:
            raise LatexExportError(
                "Aucun compilateur LaTeX trouve. Installe MiKTeX ou TeX Live, "
                "puis assure-toi que latexmk, xelatex ou pdflatex est disponible dans le PATH."
            )

        build_dir = self.project_root / BUILD_DIRNAME
        build_dir.mkdir(parents=True, exist_ok=True)
        master_tex_path = build_dir / "yuumi_manuscript.tex"
        master_tex_path.write_text(
            self._master_document(commands_path, source_paths),
            encoding="utf-8",
        )

        self._run_compiler(compiler, master_tex_path, build_dir)
        built_pdf = master_tex_path.with_suffix(".pdf")
        if not built_pdf.exists():
            raise LatexExportError("La compilation LaTeX s'est terminee sans produire de PDF.")

        shutil.copyfile(built_pdf, output_path)
        return LatexExportResult(
            pdf_path=output_path,
            master_tex_path=master_tex_path,
            log_path=master_tex_path.with_suffix(".log"),
            source_count=len(source_paths),
        )

    def source_paths(self) -> list[Path]:
        ignored_filenames = {COMMANDS_FILENAME.casefold()}
        paths = [
            path
            for path in iter_text_files(self.project_root, self.extensions)
            if path.name.casefold() not in ignored_filenames
            and not self._has_ignored_directory(path)
            and self._filename_numbers(path)
        ]
        return sorted(paths, key=self._numeric_path_key)

    def _source_paths(self) -> list[Path]:
        return self.source_paths()

    def _has_ignored_directory(self, path: Path) -> bool:
        relative_parts = path.relative_to(self.project_root).parts[:-1]
        return any(part.casefold() in IGNORED_LATEX_DIRECTORIES for part in relative_parts)

    def _numeric_path_key(self, path: Path) -> tuple[tuple[int, ...], str]:
        return (self._filename_numbers(path), path.relative_to(self.project_root).as_posix().casefold())

    def _filename_numbers(self, path: Path) -> tuple[int, ...]:
        return tuple(int(match) for match in re.findall(r"\d+", path.stem))

    def _master_document(self, commands_path: Path, source_paths: list[Path]) -> str:
        parts = [
            r"\documentclass[11pt,openany]{book}",
            rf"\input{{{self._tex_path(commands_path)}}}",
            rf"\title{{{self._escape_text(self.project_root.name)}}}",
            r"\author{}",
            r"\date{}",
            r"\begin{document}",
            r"\maketitle",
            r"\tableofcontents",
            r"\clearpage",
        ]
        for path in source_paths:
            relative_name = path.relative_to(self.project_root).as_posix()
            parts.extend(
                [
                    "",
                    rf"% YuumiWriting source: {relative_name}",
                    path.read_text(encoding="utf-8", errors="replace"),
                ]
            )
        parts.append(r"\end{document}")
        return "\n".join(parts) + "\n"

    def _run_compiler(self, compiler: str, master_tex_path: Path, build_dir: Path) -> None:
        if Path(compiler).name.lower().startswith("latexmk"):
            command = [
                compiler,
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                master_tex_path.name,
            ]
        else:
            command = [
                compiler,
                "-interaction=nonstopmode",
                "-halt-on-error",
                master_tex_path.name,
            ]
        try:
            first = subprocess.run(
                command,
                cwd=build_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            second = subprocess.run(
                command,
                cwd=build_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LatexExportError("La compilation LaTeX a depasse 120 secondes.") from exc
        except OSError as exc:
            raise LatexExportError(f"Impossible de lancer LaTeX : {exc}") from exc

        if first.returncode != 0 or second.returncode != 0:
            output = (second.stdout + "\n" + second.stderr).strip()
            raise LatexExportError(self._format_latex_error(output, master_tex_path))

    def _format_latex_error(self, output: str, master_tex_path: Path) -> str:
        lines = [line for line in output.splitlines() if line.strip()]
        tail = "\n".join(lines[-18:])
        if not tail:
            tail = "Consulte le fichier log pour le detail de l'erreur."
        return (
            "LaTeX n'a pas pu compiler le manuscrit.\n\n"
            f"Fichier maitre : {master_tex_path}\n\n"
            f"{tail}"
        )

    def _find_compiler(self) -> str | None:
        for candidate in ("xelatex", "pdflatex", "latexmk"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def _tex_path(self, path: Path) -> str:
        return path.resolve().as_posix()

    def _escape_text(self, value: str) -> str:
        replacements = {
            "\\": r"\textbackslash{}",
            "{": r"\{",
            "}": r"\}",
            "$": r"\$",
            "&": r"\&",
            "#": r"\#",
            "_": r"\_",
            "%": r"\%",
        }
        return "".join(replacements.get(char, char) for char in value)
