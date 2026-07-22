"""Question / option / answer / explanation parser.

Pure-regex + heuristic parser. Designed for the rough recall PDF layout:
- "Q.45  A 23-year-old male presents with..."
- Options "A. ..." / "B. ..."
- Answer "Ans: B" / "Answer: (b)" / "Key: B,D"
- Explanation "Exp: ..."
- Assertion-Reason format

LLM fallback exposed via parse_with_llm() (stub).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .models import ParsedOption, ParsedQuestion

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------- regex ----

QUESTION_PREFIX = re.compile(
    r"(?:^|\n)\s*(?:"
    r"Q\.?\s*(\d+)"           # Q.45 / Q45
    r"|Question\s+(\d+)"       # Question 45
    r"|(\d+)\s*[\.\)]\s+"     # 45. or 45)
    r")\s*",
    re.IGNORECASE,
)

OPTION_PREFIX = re.compile(
    r"^\s*([A-Fa-f])[\.\)]\s+(.+?)\s*$",
    re.MULTILINE,
)

ANSWER_LINE = re.compile(
    r"(?:Answer|Ans|Correct\s*answer|Key)\s*[:\-]?\s*"
    r"([A-Fa-f](?:\s*[,/&+\s]\s*[A-Fa-f])*)",
    re.IGNORECASE,
)

EXPLANATION_LINE = re.compile(
    r"(?:Explanation|Explain|Exp|Explanation\s*with\s*reference)\s*[:\-]\s*"
    r"(.+?)(?=\n\s*(?:Q\s*\.?|Question\s+\d+|\d+\s*[\.\)]|$))",
    re.IGNORECASE | re.DOTALL,
)

ASSERTION_REASON = re.compile(
    r"^Assertion\s*[:\-].*?Reason\s*[:\-]",
    re.IGNORECASE | re.DOTALL,
)

IMAGE_REF = re.compile(
    r"\[(?:image|fig|figure|see\s+image|see\s+fig|refer\s+to\s+(?:image|fig))\s*(\d+)?\]",
    re.IGNORECASE,
)


# ----------------------------------------------------------------- data --

@dataclass
class ParseStats:
    pages_parsed: int = 0
    questions_found: int = 0
    options_found: int = 0
    answers_found: int = 0
    explanations_found: int = 0
    image_refs_found: int = 0
    assertion_reason_found: int = 0


# ----------------------------------------------------------------- helpers

def _strip_image_refs(text: str) -> str:
    return IMAGE_REF.sub("", text).strip()


def _normalise_option_label(label: str) -> str:
    return label.upper()


def _parse_options(chunk: str) -> list[ParsedOption]:
    """Parse A/B/C/D options out of a question chunk."""
    options: list[ParsedOption] = []
    matches = list(OPTION_PREFIX.finditer(chunk))
    if not matches:
        return options

    for i, m in enumerate(matches):
        label = _normalise_option_label(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(chunk)
        text = chunk[start:end].strip()
        # Drop trailing answer/explanation fragments within the option text.
        text = re.split(r"\b(?:Ans|Answer|Explanation|Exp)\s*[:\-]", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        options.append(ParsedOption(label=label, text=text))
    return options


def _detect_question_type(stem: str, options: list[ParsedOption]) -> str:
    if ASSERTION_REASON.search(stem):
        return "assertion_reason"
    if not options:
        if IMAGE_REF.search(stem):
            return "image_based"
        return "numerical"
    if any(o.text.strip().lower().startswith("all of the above") for o in options):
        return "multiple_correct"
    return "single_best"


def _extract_answer_labels(chunk: str) -> list[str]:
    m = ANSWER_LINE.search(chunk)
    if not m:
        return []
    raw = m.group(1)
    return sorted({_normalise_option_label(c) for c in re.findall(r"[A-Fa-f]", raw)})


def _extract_explanation(chunk: str) -> Optional[str]:
    m = EXPLANATION_LINE.search(chunk)
    if not m:
        return None
    text = m.group(1).strip()
    return text or None


def _split_into_chunks(text: str) -> list[tuple[int, str]]:
    """Return list of (question_number, chunk)."""
    chunks: list[tuple[int, str]] = []
    matches = list(QUESTION_PREFIX.finditer(text))
    if not matches:
        return chunks
    for i, m in enumerate(matches):
        n = m.group(1) or m.group(2) or m.group(3)
        try:
            n = int(n) if n else None
        except ValueError:
            n = None
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunks.append((n, text[start:end]))
    return chunks


# ----------------------------------------------------------------- main ---

def parse_page(
    page_text: str,
    page_number: int,
    source_sha16: str,
    *,
    llm_fallback: Optional[Callable[[str, int], list[ParsedQuestion]]] = None,
    import_job_id: Optional[str] = None,
) -> tuple[list[ParsedQuestion], ParseStats]:
    """Parse one page of text into questions. Returns (questions, stats).

    When the regex parser finds zero questions AND `llm_fallback` is set,
    we delegate to the LLM. The LLM caller is responsible for raising
    NotImplementedError until wired to a provider.
    """
    stats = ParseStats(pages_parsed=1)
    chunks = _split_into_chunks(page_text)
    if not chunks:
        if llm_fallback is not None:
            try:
                llm_questions = llm_fallback(page_text, page_number)
                for q in llm_questions:
                    q.source_sha16 = source_sha16
                    q.page_number = page_number
                    if import_job_id:
                        q.import_job_id = import_job_id
                stats.questions_found = len(llm_questions)
                return llm_questions, stats
            except NotImplementedError:
                LOG.debug("LLM fallback not implemented for page %s", page_number)
        return [], stats

    out: list[ParsedQuestion] = []
    for q_no, chunk in chunks:
        # Strip image refs from stem but count them.
        img_refs = IMAGE_REF.findall(chunk)
        stats.image_refs_found += len(img_refs)

        options = _parse_options(chunk)
        stats.options_found += len(options)

        ans = _extract_answer_labels(chunk)
        if ans:
            stats.answers_found += 1
        else:
            # try the whole page as fallback for inline answers
            ans = _extract_answer_labels(page_text)

        explanation = _extract_explanation(chunk)
        if explanation:
            stats.explanations_found += 1

        stem_raw = chunk
        stem = _strip_image_refs(chunk.split("\n", 1)[0] if "\n" in chunk else chunk).strip()
        # If stem is just the option prefix section, take the full chunk minus options.
        if options and stem and stem.endswith(options[0].text):
            stem = ""

        qtype = _detect_question_type(stem or chunk, options)

        # Confidence components.
        opt_score = 1.0 if len(options) == 4 else (0.75 if len(options) == 3 else (0.5 if len(options) >= 2 else 0.0))
        ans_score = 1.0 if ans else 0.0
        exp_score = 1.0 if explanation else 0.0
        parse_confidence = 0.5 * opt_score + 0.3 * ans_score + 0.2 * exp_score

        if qtype == "assertion_reason":
            stats.assertion_reason_found += 1

        question = ParsedQuestion(
            source_sha16=source_sha16,
            page_number=page_number,
            question_number_in_pdf=q_no,
            stem=stem or chunk,
            stem_raw=stem_raw,
            options=options,
            answer_labels=ans,
            answer_text=" ".join(ans) if ans else None,
            explanation=explanation,
            question_type=qtype,
            is_image_based=bool(img_refs) and not options,
            raw=chunk,
            extraction_confidence=parse_confidence,
            confidence_score=parse_confidence,
            import_job_id=import_job_id,
        )

        # Mark correct options from answer_labels.
        ans_set = set(ans)
        for o in question.options:
            o.is_correct = o.label in ans_set

        out.append(question)
        stats.questions_found += 1

    return out, stats


# ----------------------------------------------------------------- LLM stub

LLM_PROMPT = """You are parsing a NEET PG recall-based question page into JSON.

Return a JSON array of objects with this schema:
{
  "question_number": int | null,
  "stem": "...",
  "options": [{"label": "A", "text": "..."}],
  "answer": ["B"],
  "explanation": "...",
  "image_refs": ["figure 1"]
}
Only JSON — no commentary. If a field is missing, omit it.
"""


def parse_with_llm(page_text: str, page_number: int) -> list[ParsedQuestion]:  # pragma: no cover - stub
    """Stub. Wire to ai_engine.services.ai_complete() once configured."""
    raise NotImplementedError(
        "Wire to ai_engine.services.ai_complete() — pass LLM_PROMPT and the page text."
    )


__all__ = [
    "QUESTION_PREFIX",
    "OPTION_PREFIX",
    "ANSWER_LINE",
    "EXPLANATION_LINE",
    "ASSERTION_REASON",
    "IMAGE_REF",
    "LLM_PROMPT",
    "ParseStats",
    "parse_page",
    "parse_with_llm",
]