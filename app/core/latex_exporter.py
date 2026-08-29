from __future__ import annotations

import shutil
import subprocess
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.text_corpus import TEXTS_DIRNAME, iter_text_files


COMMANDS_FILENAME = "yuumi_commands.tex"
BUILD_DIRNAME = ".yuumi_latex"
IGNORED_LATEX_DIRECTORIES = {BUILD_DIRNAME.casefold(), "notes"}
YUUMI_INLINE_COMMANDS = ("rep", "scenechange", "chaptersubtitle")
OLD_REP_COMMAND = r"\newcommand{\rep}[1]{\par\noindent--- #1\par}"
INLINE_REP_COMMAND = r"\newcommand{\rep}[1]{--- #1}"
LANGUAGE_AWARE_REP_COMMAND = (
    r"\newcommand{\rep}[1]{\ifthenelse{\equal{\yuumilanguage}{en}}{``#1''}{--- #1}}"
)
OLD_SCENECHANGE_COMMAND = r"\newcommand{\scenechange}{\par\bigskip\begin{center}* * *\end{center}\bigskip\par}"
CENTERED_SCENECHANGE_COMMAND = r"\newcommand{\scenechange}{\par\bigskip\noindent\hfill * * *\hfill\null\par\bigskip}"


DEFAULT_COMMANDS = r"""% YuumiWriting language: use fr or en
\newcommand{\yuumilanguage}{fr}
\usepackage{ifthen}
\usepackage[english,french]{babel}
\AtBeginDocument{\ifthenelse{\equal{\yuumilanguage}{en}}{\selectlanguage{english}}{\selectlanguage{french}}}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage[
  paperwidth=5.06in,
  paperheight=7.81in,
  inner=16mm,
  outer=12mm,
  top=14mm,
  bottom=16mm
]{geometry}

% YuumiWriting pocket layout
\setstretch{1.04}
\setlength{\parindent}{1.15em}
\setlength{\parskip}{0pt}
\raggedbottom
\pagestyle{plain}

\titleformat{\chapter}[display]
  {\normalfont\huge\bfseries\centering}
  {}
  {0pt}
  {}

\newcommand{\rep}[1]{\ifthenelse{\equal{\yuumilanguage}{en}}{``#1''}{--- #1}}
\newcommand{\scenechange}{\par\bigskip\noindent\hfill * * *\hfill\null\par\bigskip}
\newcommand{\chaptersubtitle}[1]{\begin{center}\large\itshape #1\end{center}\medskip}
"""

LANGUAGE_CONFIG_MARKER = "% YuumiWriting language: use fr or en"
LANGUAGE_CONFIG_COMMANDS = r"""% YuumiWriting language: use fr or en
\newcommand{\yuumilanguage}{fr}
\usepackage{ifthen}
"""
LANGUAGE_SELECTION_COMMAND = (
    r"\AtBeginDocument{\ifthenelse{\equal{\yuumilanguage}{en}}"
    r"{\selectlanguage{english}}{\selectlanguage{french}}}"
)

POCKET_LAYOUT_MARKER = "% YuumiWriting pocket layout"
POCKET_LAYOUT_COMMANDS = r"""
% YuumiWriting pocket layout
\geometry{
  paperwidth=5.06in,
  paperheight=7.81in,
  inner=16mm,
  outer=12mm,
  top=14mm,
  bottom=16mm
}
\setstretch{1.04}
\setlength{\parindent}{1.15em}
\setlength{\parskip}{0pt}
\raggedbottom
\pagestyle{plain}
"""

UNICODE_COMMANDS_MARKER = "% YuumiWriting Unicode compatibility"
UNICODE_DECLARE_FALLBACK = r"\providecommand{\DeclareUnicodeCharacter}[2]{}"
UNICODE_COMMANDS = r"""
% YuumiWriting Unicode compatibility
\providecommand{\DeclareUnicodeCharacter}[2]{}
\DeclareUnicodeCharacter{00A0}{~}
\DeclareUnicodeCharacter{202F}{\,}
\DeclareUnicodeCharacter{2018}{'}
\DeclareUnicodeCharacter{2019}{'}
\DeclareUnicodeCharacter{201C}{``}
\DeclareUnicodeCharacter{201D}{''}
\DeclareUnicodeCharacter{2013}{--}
\DeclareUnicodeCharacter{2014}{---}
\DeclareUnicodeCharacter{2026}{\ldots}
"""

FRONTMATTER_COMMANDS_MARKER = "% YuumiWriting front matter commands"
FRONTMATTER_COMMANDS = r"""
% YuumiWriting front matter commands
\newcommand{\YuumiRomanTitle}{Titre du roman}
\newcommand{\YuumiRomanSubtitle}{}
\newcommand{\YuumiRomanAuthor}{}
\newcommand{\YuumiRomanDedication}{}
\newcommand{\YuumiRomanQuote}{}

\newcommand{\romantitle}[1]{\gdef\YuumiRomanTitle{#1}}
\newcommand{\romansubtitle}[1]{\gdef\YuumiRomanSubtitle{#1}}
\newcommand{\romanauthor}[1]{\gdef\YuumiRomanAuthor{#1}}
\newcommand{\romandedication}[1]{\gdef\YuumiRomanDedication{#1}}
\newcommand{\romanquote}[1]{\gdef\YuumiRomanQuote{#1}}

% A personnaliser pour le roman.
\romantitle{Titre du roman}
\romansubtitle{}
\romanauthor{}
\romandedication{}
\romanquote{}

\newcommand{\makeyuumititlepage}{%
  \begin{titlepage}
    \centering
    \thispagestyle{empty}
    \vspace*{0.18\textheight}
    {\Huge\bfseries \YuumiRomanTitle\par}
    \vspace{1.2em}
    {\Large\itshape \YuumiRomanSubtitle\par}
    \vfill
    {\large \YuumiRomanAuthor\par}
    \vspace*{0.12\textheight}
  \end{titlepage}
}

\newcommand{\makeyuumidedicationquotepage}{%
  \cleardoublepage
  \thispagestyle{empty}
  \vspace*{0.2\textheight}
  \begin{center}
    {\itshape \YuumiRomanDedication\par}
    \vspace{3em}
    \begin{minipage}{0.72\textwidth}
      \centering
      {\itshape \YuumiRomanQuote\par}
    \end{minipage}
  \end{center}
  \cleardoublepage
}
"""


@dataclass(slots=True)
class LatexExportResult:
    pdf_path: Path
    master_tex_path: Path
    log_path: Path
    source_count: int


class LatexExportError(RuntimeError):
    pass


def read_project_language(project_root: Path) -> str:
    """Lit la langue fr/en choisie dans yuumi_commands.tex."""
    commands_path = project_root.resolve() / COMMANDS_FILENAME
    if not commands_path.exists():
        return "fr"
    content = commands_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"\\(?:newcommand|renewcommand)\s*\{\\yuumilanguage\}\s*\{\s*(fr|en)\s*\}",
        content,
        flags=re.IGNORECASE,
    )
    return match.group(1).casefold() if match else "fr"


def ensure_project_latex_defaults(project_root: Path) -> Path:
    project_root = project_root.resolve()
    texts_dir = project_root / TEXTS_DIRNAME
    texts_dir.mkdir(parents=True, exist_ok=True)
    notes_dir = project_root / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    commands_path = project_root / COMMANDS_FILENAME
    if not commands_path.exists():
        commands_path.write_text(DEFAULT_COMMANDS + UNICODE_COMMANDS + FRONTMATTER_COMMANDS, encoding="utf-8")
    else:
        content = commands_path.read_text(encoding="utf-8")
        changed = False
        if OLD_REP_COMMAND in content:
            content = content.replace(OLD_REP_COMMAND, LANGUAGE_AWARE_REP_COMMAND)
            changed = True
        if INLINE_REP_COMMAND in content:
            content = content.replace(INLINE_REP_COMMAND, LANGUAGE_AWARE_REP_COMMAND)
            changed = True
        if LANGUAGE_CONFIG_MARKER not in content:
            content = LANGUAGE_CONFIG_COMMANDS + content.lstrip()
            changed = True
        if r"\usepackage[french]{babel}" in content:
            content = content.replace(
                r"\usepackage[french]{babel}",
                r"\usepackage[english,french]{babel}",
                1,
            )
            changed = True
        if LANGUAGE_SELECTION_COMMAND not in content:
            babel_command = r"\usepackage[english,french]{babel}"
            if babel_command in content:
                content = content.replace(
                    babel_command,
                    babel_command + "\n" + LANGUAGE_SELECTION_COMMAND,
                    1,
                )
                changed = True
        if OLD_SCENECHANGE_COMMAND in content:
            content = content.replace(OLD_SCENECHANGE_COMMAND, CENTERED_SCENECHANGE_COMMAND)
            changed = True
        if POCKET_LAYOUT_MARKER not in content:
            content = content.rstrip() + "\n" + POCKET_LAYOUT_COMMANDS
            changed = True
        if UNICODE_COMMANDS_MARKER not in content:
            content = content.rstrip() + "\n" + UNICODE_COMMANDS
            changed = True
        elif UNICODE_DECLARE_FALLBACK not in content:
            content = content.replace(
                UNICODE_COMMANDS_MARKER,
                f"{UNICODE_COMMANDS_MARKER}\n{UNICODE_DECLARE_FALLBACK}",
                1,
            )
            changed = True
        if FRONTMATTER_COMMANDS_MARKER not in content:
            content = content.rstrip() + "\n" + FRONTMATTER_COMMANDS
            changed = True
        if changed:
            commands_path.write_text(content, encoding="utf-8")
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
                f"Aucun fichier numerote trouve dans le dossier {TEXTS_DIRNAME} pour la compilation PDF. "
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
            r"\begin{document}",
            r"\frontmatter",
            r"\makeyuumititlepage",
            r"\makeyuumidedicationquotepage",
            r"\tableofcontents",
            r"\clearpage",
            r"\mainmatter",
            r"\pagestyle{plain}",
        ]
        for path in source_paths:
            relative_name = path.relative_to(self.project_root).as_posix()
            parts.extend(
                [
                    "",
                    rf"% YuumiWriting source: {relative_name}",
                    self._source_text(path),
                ]
            )
        parts.append(r"\end{document}")
        return "\n".join(parts) + "\n"

    def _source_text(self, path: Path) -> str:
        content = path.read_text(encoding="utf-8", errors="replace")
        return self._normalize_yuumi_commands(content)

    def _normalize_yuumi_commands(self, content: str) -> str:
        command_pattern = "|".join(re.escape(command) for command in YUUMI_INLINE_COMMANDS)
        return re.sub(rf"(^|[^\S\r\n])\\\\(?=({command_pattern})\b)", r"\1\\", content)

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
