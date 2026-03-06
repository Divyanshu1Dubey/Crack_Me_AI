"""
PDF Processing utilities for extracting text and images from PDFs.
Handles PYQ papers, textbooks, and handwritten notes.
"""
import os
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports - pdfplumber and fitz are heavy; only load when actually needed
pdfplumber = None
fitz = None

def _ensure_pdf_libs():
    global pdfplumber, fitz
    if pdfplumber is None:
        import pdfplumber as _pdfplumber
        pdfplumber = _pdfplumber
    if fitz is None:
        import fitz as _fitz
        fitz = _fitz


class DocumentProcessor:
    """Extract text and images from PDF, TXT, and MD files."""

    @staticmethod
    def extract_text(file_path: str, start_page: int = 0, end_page: Optional[int] = None) -> list[dict]:
        """
        Extract text from file.
        Returns list of {page_num, text} dicts. For text/md files, whole file is "page 1".
        """
        ext = Path(file_path).suffix.lower()
        if ext in ['.txt', '.md']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                return [{
                    "page_num": 1,
                    "text": text.strip(),
                    "width": 0,
                    "height": 0,
                }]
            except Exception as e:
                logger.error(f"Failed to read text file {file_path}: {e}")
                return []
                
        # PDF parsing — process in batches to avoid memory explosion
        _ensure_pdf_libs()
        pages = []
        try:
            with pdfplumber.open(file_path) as pdf:
                total = len(pdf.pages)
                end = min(end_page or total, total)
                for i in range(start_page, end):
                    try:
                        page = pdf.pages[i]
                        text = page.extract_text() or ""
                        if text.strip():
                            pages.append({
                                "page_num": i + 1,
                                "text": text.strip(),
                                "width": float(page.width),
                                "height": float(page.height),
                            })
                        # Flush page resources to free memory
                        page.flush_cache()
                    except Exception as page_err:
                        logger.warning(f"Failed to extract page {i+1} from {Path(file_path).name}: {page_err}")
                        continue
            logger.info(f"Extracted {len(pages)} pages from {Path(file_path).name}")
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
        return pages

    @staticmethod
    def extract_page_image(pdf_path: str, page_num: int, output_dir: str,
                           dpi: int = 200) -> Optional[str]:
        """
        Extract a specific page as a PNG image (for textbook screenshots).
        page_num is 0-indexed.
        Returns the output image path or None.
        """
        try:
            _ensure_pdf_libs()
            os.makedirs(output_dir, exist_ok=True)
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                return None
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            filename = f"{Path(pdf_path).stem}_page_{page_num + 1}.png"
            output_path = os.path.join(output_dir, filename)
            pix.save(output_path)
            doc.close()
            logger.info(f"Saved page image: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to extract page image: {e}")
            return None

    @staticmethod
    def get_pdf_metadata(pdf_path: str) -> dict:
        """Get PDF metadata (pages, title, etc.)."""
        try:
            _ensure_pdf_libs()
            doc = fitz.open(pdf_path)
            meta = {
                "path": pdf_path,
                "filename": Path(pdf_path).name,
                "pages": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "file_size_mb": round(os.path.getsize(pdf_path) / 1048576, 1),
            }
            doc.close()
            return meta
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {"path": pdf_path, "error": str(e)}

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """
        Split text into overlapping chunks for embedding.
        Handles both prose (sentence boundaries) and markdown (headers, bullets, tables).
        """
        # For markdown-heavy content, split on paragraph/section boundaries first,
        # then fall back to sentence splitting within large blocks.
        # Split on: double newlines, markdown headers, or single newlines before bullets/tables
        blocks = re.split(r'\n{2,}|(?=\n#{1,6}\s)|(?=\n[-*]\s)|(?=\n\|)', text)
        # Further split large blocks on sentence boundaries
        segments = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            words = block.split()
            if len(words) > chunk_size:
                # Split further on sentence boundaries
                sents = re.split(r'(?<=[.!?:;])\s+|\n', block)
                segments.extend(s.strip() for s in sents if s.strip())
            else:
                segments.append(block)

        chunks = []
        current_chunk = []
        current_len = 0

        for segment in segments:
            words = segment.split()
            segment_len = len(words)

            if current_len + segment_len > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Keep overlap
                overlap_words = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    s_words = s.split()
                    if overlap_len + len(s_words) > overlap:
                        break
                    overlap_words.insert(0, s)
                    overlap_len += len(s_words)
                current_chunk = overlap_words
                current_len = overlap_len

            current_chunk.append(segment)
            current_len += segment_len

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks


class PYQPDFParser:
    """
    Parse UPSC CMS PYQ PDFs and extract individual MCQ questions.
    Handles various PYQ formats across years (2018-2024).
    """

    # Common patterns for question detection in CMS PYQs
    QUESTION_PATTERNS = [
        # "1." or "Q1." or "Q.1" or "1)" format
        r'(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,3})[.)]\s*(.+?)(?=(?:\n\s*(?:Q\.?\s*)?\d{1,3}[.)]|\Z))',
        # "Question 1:" format
        r'(?:^|\n)\s*Question\s+(\d{1,3})\s*[:.]\s*(.+?)(?=(?:\n\s*Question\s+\d{1,3}|\Z))',
    ]

    OPTION_PATTERNS = [
        # "(a)" or "(A)" or "a)" or "A." format
        r'\(?\s*([a-dA-D])\s*[.)]\s*(.+?)(?=\(?\s*[a-dA-D]\s*[.)]|\Z)',
        # "a." or "A." format
        r'(?:^|\n)\s*([a-dA-D])\s*[.)]\s*(.+?)(?=(?:\n\s*[a-dA-D]\s*[.)]|\Z))',
    ]

    @staticmethod
    def parse_pyq_pdf(pdf_path: str) -> list[dict]:
        """
        Extract questions from a UPSC CMS PYQ PDF.
        Returns list of raw question dicts with text and options.
        """
        processor = DocumentProcessor()
        pages = processor.extract_text(pdf_path)
        if not pages:
            return []

        # Combine all pages
        full_text = "\n".join(p["text"] for p in pages)

        # Extract year and paper from filename
        filename = Path(pdf_path).stem
        year_match = re.search(r'(20\d{2})', filename)
        paper_match = re.search(r'Paper\s*(\d)', filename, re.IGNORECASE)
        year = int(year_match.group(1)) if year_match else 0
        paper = int(paper_match.group(1)) if paper_match else 0

        logger.info(f"Parsing PYQ: {filename} (Year: {year}, Paper: {paper})")

        return {
            "year": year,
            "paper": paper,
            "filename": filename,
            "full_text": full_text,
            "page_count": len(pages),
            "pages": pages,
        }

    @staticmethod
    def detect_questions_with_regex(text: str) -> list[dict]:
        """
        Attempt to parse questions using regex patterns.
        Falls back to AI extraction if patterns don't match well.
        """
        questions = []

        # Try multiple patterns
        for pattern in PYQPDFParser.QUESTION_PATTERNS:
            matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
            if len(matches) > 10:  # Likely a good match
                for q_num, q_text in matches:
                    q_text = q_text.strip()
                    # Try to extract options
                    options = PYQPDFParser._extract_options(q_text)
                    if options:
                        question_text = q_text
                        for opt_letter, opt_text in options.items():
                            question_text = question_text.replace(opt_text, "").strip()
                        questions.append({
                            "number": int(q_num),
                            "text": question_text.strip(),
                            "options": options,
                        })
                if questions:
                    break

        return questions

    @staticmethod
    def _extract_options(text: str) -> dict:
        """Extract options A-D from question text."""
        options = {}
        for pattern in PYQPDFParser.OPTION_PATTERNS:
            matches = re.findall(pattern, text, re.DOTALL)
            if len(matches) >= 4:
                for letter, opt_text in matches[:4]:
                    options[letter.upper()] = opt_text.strip()
                break
        return options




