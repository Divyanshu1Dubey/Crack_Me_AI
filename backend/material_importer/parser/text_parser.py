"""Plain-text / Markdown fallback parser."""
from __future__ import annotations

import time
from pathlib import Path

from .dataclasses import ParsedDocument
from .docx_parser import ClassicMCQExtractor, TheoryExtractor
from .text_utils import clean_text


class TextParser:
    def parse(self, path: str) -> ParsedDocument:
        start = time.time()
        fn = Path(path).name
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ParsedDocument(
                source_filename=fn,
                file_format="txt" if path.endswith(".txt") else "md",
                detected_type="unknown",
                parser_used="text",
                errors=[f"Failed to read: {exc}"],
            )
        paragraphs = [clean_text(line) for line in text.splitlines() if line.strip()]
        questions = ClassicMCQExtractor().extract(paragraphs)
        theory = TheoryExtractor().extract(paragraphs, [])
        fmt = "txt" if path.endswith(".txt") else "md"
        detected = "mcq_classic" if questions else "theory"
        return ParsedDocument(
            source_filename=fn,
            file_format=fmt,
            detected_type=detected,
            parser_used="text",
            questions=questions,
            theory_blocks=theory,
            duration_ms=int((time.time() - start) * 1000),
        )
