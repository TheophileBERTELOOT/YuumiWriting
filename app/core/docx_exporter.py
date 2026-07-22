from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from app.core.latex_exporter import LatexProjectExporter


@dataclass(slots=True)
class DocxExportResult:
    docx_path: Path
    source_count: int


class DocxExportError(RuntimeError):
    pass


class DocxProjectExporter:
    """Export the numbered manuscript sources as a minimal Word document."""

    def __init__(self, project_root: Path, extensions: tuple[str, ...]) -> None:
        self.project_root = project_root.resolve()
        self.extensions = extensions

    def source_paths(self) -> list[Path]:
        return LatexProjectExporter(self.project_root, self.extensions).source_paths()

    def export_docx(self, output_path: Path) -> DocxExportResult:
        paths = self.source_paths()
        if not paths:
            raise DocxExportError("Aucun chapitre numerote trouve pour l'export Word.")

        output_path = output_path.expanduser().resolve()
        if output_path.suffix.lower() != ".docx":
            output_path = output_path.with_suffix(".docx")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        paragraphs: list[tuple[str, str]] = []
        for index, path in enumerate(paths):
            if index:
                paragraphs.append(("pagebreak", ""))
            paragraphs.extend(self._paragraphs(path.read_text(encoding="utf-8", errors="replace")))

        try:
            self._write_docx(output_path, paragraphs)
        except OSError as exc:
            raise DocxExportError(f"Impossible d'ecrire le fichier Word : {exc}") from exc
        return DocxExportResult(output_path, len(paths))

    @classmethod
    def _paragraphs(cls, source: str) -> list[tuple[str, str]]:
        source = re.sub(r"(?m)%.*$", "", source)
        source = re.sub(r"\\scenechange\b", "\n\n[[SCENECHANGE]]* * *\n\n", source)
        source = re.sub(r"\\(?:chapter|chapter\*)\{([^{}]*)\}", r"\n\n[[HEADING]]\1\n\n", source)
        source = re.sub(r"\\chaptersubtitle\{([^{}]*)\}", r"\n\n[[SUBTITLE]]\1\n\n", source)
        source = re.sub(r"\\rep\{([^{}]*)\}", r"— \1", source)
        source = re.sub(r"\\(?:textit|emph)\{([^{}]*)\}", r"\1", source)
        source = re.sub(r"\\(?:textbf|textsc)\{([^{}]*)\}", r"\1", source)
        source = re.sub(r"\\(?:begin|end)\{[^{}]+\}", "", source)
        source = re.sub(r"\\(?:label|index|footnote)\{[^{}]*\}", "", source)
        source = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", "", source)
        source = source.replace("~", " ").replace("``", "“").replace("''", "”")
        source = source.replace(r"\&", "&").replace(r"\%", "%").replace(r"\_", "_")
        source = source.replace("{", "").replace("}", "")

        result: list[tuple[str, str]] = []
        for block in re.split(r"\n\s*\n", source):
            text = re.sub(r"\s+", " ", block).strip()
            if not text:
                continue
            if text.startswith("[[HEADING]]"):
                result.append(("heading", text.removeprefix("[[HEADING]]").strip()))
            elif text.startswith("[[SUBTITLE]]"):
                result.append(("subtitle", text.removeprefix("[[SUBTITLE]]").strip()))
            elif text.startswith("[[SCENECHANGE]]"):
                result.append(("scenechange", text.removeprefix("[[SCENECHANGE]]").strip()))
            else:
                result.append(("body", text))
        return result

    @staticmethod
    def _write_docx(path: Path, paragraphs: list[tuple[str, str]]) -> None:
        body = []
        for kind, text in paragraphs:
            if kind == "pagebreak":
                body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
                continue
            properties = {
                "heading": '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>',
                "subtitle": '<w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>',
                "scenechange": '<w:pPr><w:jc w:val="center"/></w:pPr>',
                "body": "",
            }[kind]
            body.append(f'<w:p>{properties}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')

        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{"".join(body)}<w:sectPr><w:pgSz w:w="7286" w:h="11246"/>'
            '<w:pgMar w:top="794" w:right="680" w:bottom="907" w:left="907"/></w:sectPr></w:body></w:document>'
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        )
        relationships = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'
        )
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", relationships)
            archive.writestr("word/document.xml", document)
