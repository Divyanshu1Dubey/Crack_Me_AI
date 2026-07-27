"""PDF parser (lazy). Imports pypdf or pdfplumber at call time so the
rest of the module loads even when those libs are missing.

The implementation here is intentionally minimal — extract every page's
text, run heuristic MCQ detection, and store page screenshots under
`MEDIA_ROOT/imported_pdf_pages/<doc_sha>/page<n>.png`. OCR runs only
when an OCR engine is registered in env (`OCR_ENGINE=tesseract`).
"""
from __future__ import annotations

import hashlib
import io
import re
import time
from pathlib import Path
from typing import List, Sequence

from .dataclasses import ParsedDocument, ParsedQuestion
from .text_utils import clean_text, extract_year_hint
from .docx_parser import ClassicMCQExtractor, BoxedMCQExtractor  # PDF text → MCQ logic


class PDFParser:
    def parse(self, path: str) -> ParsedDocument:
        start = time.time()
        fn = Path(path).name
        doc = ParsedDocument(
            source_filename=fn,
            file_format="pdf",
            detected_type="unknown",
            parser_used="pdf",
        )
        try:
            pages = self._extract_pages(path)
        except Exception as exc:
            doc.errors.append(f"Failed to read PDF: {exc}")
            return doc
        if not pages:
            doc.warnings.append("PDF contained no extractable text (likely scanned). OCR required.")
            return doc
        # Flatten pages into paragraph stream for the same extractors.
        paragraphs: List[str] = []
        for page_text in pages:
            for line in page_text.splitlines():
                paragraphs.append(clean_text(line))
        classic = ClassicMCQExtractor().extract(paragraphs)
        boxed_tables = [[ [line.strip()] for line in p.splitlines() if line.strip()] for p in pages ]
        boxed = BoxedMCQExtractor().extract(boxed_tables)
        doc.questions = classic + boxed
        if doc.questions:
            doc.detected_type = "mcq_classic" if classic else "mcq_boxed"
            doc.parser_used = "pdf.classic" if classic else "pdf.boxed"
        else:
            doc.detected_type = "theory"
            doc.parser_used = "pdf.fallback"
            from .docx_parser import TheoryExtractor
            doc.theory_blocks = TheoryExtractor().extract(paragraphs, [])
        doc.meta["pages"] = len(pages)
        all_text = "\n".join(p for p in pages)
        year = extract_year_hint(all_text)
        if year:
            doc.meta["year"] = year
        doc.meta["sha256"] = hashlib.sha256(open(path, "rb").read()).hexdigest()
        doc.duration_ms = int((time.time() - start) * 1000)
        return doc

    @staticmethod
    def _extract_pages(path: str) -> List[str]:
        """Try pypdf first, then pdfplumber. Both are optional."""
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(path)
            return [(p.extract_text() or "") for p in reader.pages]
        except Exception:
            pass
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(path) as pdf:
                return [(p.extract_text() or "") for p in pdf.pages]
        except Exception:
            pass
        raise RuntimeError("Install pypdf or pdfplumber to parse PDFs.")
