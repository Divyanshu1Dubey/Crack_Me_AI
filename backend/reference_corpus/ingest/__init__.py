"""Source parsers for the reference store (PDF, DOCX, TXT/MD). OCR text only from the page cache."""
from __future__ import annotations

from typing import Optional

from .base import FigureRecord, IngestResult, PageRecord, Segment  # noqa: F401

PARSER_VERSIONS = {'.pdf': 'pdf-v1', '.docx': 'docx-v1', '.txt': 'text-v1', '.md': 'text-v1'}


def parser_version_for(extension: str) -> str:
    return PARSER_VERSIONS.get(extension.lower(), '')


def ingest_file(path: str, extension: str, *, ocr_text: Optional[dict[int, str]] = None,
                max_pages: Optional[int] = None, ocr_engine: str = '') -> IngestResult:
    extension = extension.lower()
    if extension == '.pdf':
        from .pdf import ingest_pdf
        return ingest_pdf(path, ocr_text=ocr_text, max_pages=max_pages, ocr_engine=ocr_engine)
    if extension == '.docx':
        from .docx import ingest_docx
        return ingest_docx(path, max_pages=max_pages)
    if extension in ('.txt', '.md'):
        from .text import ingest_text
        return ingest_text(path, max_pages=max_pages)
    return IngestResult(parser='none', parser_version='', error=f'unsupported file type {extension}')
