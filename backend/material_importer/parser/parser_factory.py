"""ParserFactory — pick the right file parser by extension.

Adding a new format = subclassing `BaseParser`. Everything else (ingest
pipeline, admin UI, REST API) automatically gets support.
"""
from __future__ import annotations

from pathlib import Path
from typing import Type

from .dataclasses import ParsedDocument

from .docx_parser import DOCXParser


class BaseParser:
    extensions: tuple[str, ...] = ()

    def parse(self, path: str) -> ParsedDocument:  # pragma: no cover - subclass
        raise NotImplementedError


class _DocxParserAdapter(BaseParser):
    extensions = (".docx",)

    def __init__(self) -> None:
        self._impl = DOCXParser()

    def parse(self, path: str) -> ParsedDocument:
        return self._impl.parse(path)


class _PdfParserAdapter(BaseParser):
    extensions = (".pdf",)

    def parse(self, path: str) -> ParsedDocument:
        # PDFParser is lazily imported — `pypdf`/`pdfplumber` is optional.
        try:
            from .pdf_parser import PDFParser
            return PDFParser().parse(path)
        except ImportError:
            return ParsedDocument(
                source_filename=Path(path).name,
                file_format="pdf",
                detected_type="unknown",
                parser_used="pdf",
                errors=["PDF parser not available (pypdf/pdfplumber missing)."],
            )


class _PptxParserAdapter(BaseParser):
    extensions = (".pptx",)

    def parse(self, path: str) -> ParsedDocument:
        try:
            from .pptx_parser import PPTXParser
            return PPTXParser().parse(path)
        except ImportError:
            return ParsedDocument(
                source_filename=Path(path).name,
                file_format="pptx",
                detected_type="unknown",
                parser_used="pptx",
                errors=["PPTX parser not available (python-pptx missing)."],
            )


class _TextParserAdapter(BaseParser):
    extensions = (".txt", ".md")

    def parse(self, path: str) -> ParsedDocument:
        try:
            from .text_parser import TextParser
            return TextParser().parse(path)
        except ImportError:
            return ParsedDocument(
                source_filename=Path(path).name,
                file_format="txt" if path.endswith(".txt") else "md",
                detected_type="unknown",
                parser_used="text",
                errors=["Text parser not available."],
            )


_REGISTRY: list[Type[BaseParser]] = [
    _DocxParserAdapter,
    _PdfParserAdapter,
    _PptxParserAdapter,
    _TextParserAdapter,
]


class ParserFactory:
    """File-extension → parser dispatcher."""

    def __init__(self) -> None:
        self._by_ext: dict[str, BaseParser] = {}
        for cls in _REGISTRY:
            instance = cls()
            for ext in cls.extensions:
                self._by_ext[ext.lower()] = instance

    def parser_for(self, path: str) -> BaseParser | None:
        ext = Path(path).suffix.lower()
        return self._by_ext.get(ext)

    def parse(self, path: str) -> ParsedDocument:
        parser = self.parser_for(path)
        if parser is None:
            return ParsedDocument(
                source_filename=Path(path).name,
                file_format="unknown",
                detected_type="unknown",
                parser_used="none",
                errors=[f"No parser registered for extension {Path(path).suffix}"],
            )
        return parser.parse(path)

    def supported_extensions(self) -> tuple[str, ...]:
        return tuple(self._by_ext.keys())
