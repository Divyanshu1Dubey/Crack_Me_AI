"""Text helpers shared by ingestion, chunking and retrieval of the reference store.

Tokenisation for the BM25 index is ``ai_engine.lexical_index`` (Greek folding, diacritics,
stopwords, conservative plural stemming), so the reference index and the legacy index
see the same tokens.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Iterator

from ai_engine import lexical_index as lx

_WS_RE = re.compile(r'[ \t  -​  　]+')
_MANY_NL_RE = re.compile(r'\n{3,}')
_WORD_RE = re.compile(r'\S+')
_NORM_RE = re.compile(r'[a-z0-9]+')

# A hyphen at a line end is kept (the newline is dropped) after these prefixes.
_KEEP_HYPHEN_PREFIXES = frozenset(
    'anti non self well co semi multi ex cross long short high low beta alpha gamma post pre sub inter intra '
    'extra over under half one two three four'.split())


def normalize_text(text: str) -> str:
    """NFKC (ligatures, full-width forms), unify spaces, strip control characters."""
    text = unicodedata.normalize('NFKC', text or '')
    text = ''.join(ch for ch in text if ch in '\n\t' or unicodedata.category(ch)[0] != 'C')
    text = _WS_RE.sub(' ', text)
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return _MANY_NL_RE.sub('\n\n', text).strip()


def join_lines(lines: list[str]) -> str:
    """Join the lines of one paragraph, undoing line-end hyphenation ("immuno-" + "globulin")."""
    out = ''
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not out:
            out = line
            continue
        m = re.search(r'([A-Za-z]+)-$', out)
        if m and line[:1].islower() and len(m.group(1)) >= 2:
            if m.group(1).lower() in _KEEP_HYPHEN_PREFIXES:
                out = out + line                    # "anti-" + "inflammatory" -> "anti-inflammatory"
            else:
                out = out[:-1] + line               # "immuno-" + "globulin" -> "immunoglobulin"
        else:
            out = out + '\n' + line
    return out


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ''))


def index_tokens(text: str) -> str:
    """The FTS5 body for a chunk: lexical_index tokens (folded, stopwords dropped, stemmed)."""
    return ' '.join(lx.tokenize(text or ''))


def norm_words(text: str) -> list[str]:
    """Folded alphanumeric words, stopwords kept (for phrase / n-gram comparison)."""
    return _NORM_RE.findall(lx.fold(text or ''))


def norm_phrase(text: str) -> str:
    return ' '.join(norm_words(text))


def text_quality(text: str) -> float | None:
    """Share of word-like tokens (letters with a vowel, or plain numbers): about 0.9 for clean
    prose, much lower for a garbled text layer or OCR noise. None for empty text."""
    tokens = _WORD_RE.findall(text or '')
    if not tokens:
        return None
    good = 0
    for tok in tokens:
        core = tok.strip('.,;:()[]{}"\'!?*%/')
        if not core:
            continue
        if core.isdigit() or re.fullmatch(r'\d+([.,]\d+)?', core):
            good += 1
        elif re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", core) and re.search('[aeiouyAEIOUY]', core) and len(core) >= 2:
            good += 1
        elif len(core) == 1 and core.lower() in 'ai':
            good += 1
    return round(good / len(tokens), 3)


# ─── sentences ─────────────────────────────────────────────────────────

_ABBREVIATIONS = frozenset("""
e.g i.e etc vs viz approx fig figs eq no nos vol ch sec dr mr mrs ms prof st sr jr inc ltd co dept
al resp max min mg mcg ml dl kg cm mm km hr hrs wk wks yr yrs mo mos ca cf ed eds pp pt pts
""".split())
_SENT_END_RE = re.compile(r'[.!?]["\')\]]*(?=\s)')
_TERMINAL_RE = re.compile(r'[.!?:]["\')\]]*$')
_BULLET_RE = re.compile(r'\n(?=\s*(?:[-*•●▪–—>]|\(?[0-9]{1,2}[.)]|\(?[a-z][.)])\s)')


def sentence_spans(text: str, start: int = 0, end: int | None = None) -> list[tuple[int, int, bool]]:
    """Split ``text[start:end]`` into sentence spans ``(s, e, ends_sentence)`` (offsets into text).

    Sentence ends: '.', '!' or '?' followed by whitespace and an upper-case letter, digit or
    bracket, unless the word before the period is an abbreviation, a single letter or a number;
    bullet / numbered list lines; blank lines. The last span ends a sentence only when it ends
    with terminal punctuation (otherwise it continues on the next page or segment).
    """
    end = len(text) if end is None else end
    cuts: dict[int, str] = {}
    for m in _SENT_END_RE.finditer(text, start, end):
        stop = m.end()
        nxt = text[stop:stop + 3].lstrip()
        if not nxt or not (nxt[0].isupper() or nxt[0].isdigit() or nxt[0] in '(["\''):
            continue
        before = text[max(start, m.start() - 12):m.start()]
        word = re.split(r'[\s(\[]', before)[-1].lower().rstrip('.')
        if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()) or re.fullmatch(r'\d+', word or 'x'):
            continue
        cuts[stop] = 'sentence'
    for m in _BULLET_RE.finditer(text, start, end):
        cuts.setdefault(m.start(), 'bullet')
    for m in re.finditer(r'\n\s*\n', text[start:end]):
        cuts.setdefault(start + m.start(), 'paragraph')
    spans, s = [], start
    for c in sorted(cuts):
        if c <= s or c >= end:
            continue
        piece = text[s:c]
        if piece.strip():
            ws = len(piece) - len(piece.lstrip())
            if cuts[c] == 'paragraph':
                # A paragraph break without terminal punctuation is usually a column / page break
                # inside a sentence; short pieces (titles, list items) still end there.
                ends = bool(_TERMINAL_RE.search(piece.rstrip())) or word_count(piece) < 12
            else:
                ends = True
            spans.append((s + ws, c, ends))
        s = c
    tail = text[s:end]
    if tail.strip():
        ws = len(tail) - len(tail.lstrip())
        stripped = tail.rstrip()
        spans.append((s + ws, s + len(stripped), bool(_TERMINAL_RE.search(stripped))))
    # Trim trailing whitespace inside spans.
    out = []
    for s0, e0, ends in spans:
        while e0 > s0 and text[e0 - 1].isspace():
            e0 -= 1
        if e0 > s0:
            out.append((s0, e0, ends))
    return out


# ─── question copies (independence filter) ─────────────────────────────

def distinctive_ngrams(text: str, n: int = 4) -> set[tuple[str, ...]]:
    """Word n-grams of a question stem that carry content: at least one non-stopword of 4+ letters."""
    words = norm_words(text)
    grams = set()
    for i in range(len(words) - n + 1):
        gram = tuple(words[i:i + n])
        if any(len(w) >= 4 and w not in lx.STOPWORDS for w in gram):
            grams.add(gram)
    return grams


def ngrams(words: list[str], n: int = 4) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def copy_share(stem_grams: set[tuple[str, ...]], chunk_text: str, n: int = 4) -> float:
    """Share of the stem's distinctive n-grams that occur in the chunk (0..1)."""
    if not stem_grams:
        return 0.0
    grams = ngrams(norm_words(chunk_text), n)
    return len(stem_grams & grams) / len(stem_grams)


_KEY_PATTERNS = (
    re.compile(r'\b(?:ans(?:wer)?|key|correct\s+(?:answer|option|choice)(?:\s+is)?)\s*[:.\-=]*\s*\(?\s*([a-d])\s*\)?(?![a-z])',
               re.IGNORECASE),
    re.compile(r'\bopt(?:ion)?\s*\(?([a-d])\)?\s+is\s+(?:the\s+)?correct', re.IGNORECASE),
)


def key_in_copy(text: str) -> str:
    """The answer letter a copy of a question states ('Ans. (b)', 'Answer: C'), or '' when none
    or several different letters are stated."""
    letters = set()
    for rx in _KEY_PATTERNS:
        for m in rx.finditer(text or ''):
            letters.add(m.group(1).upper())
    return letters.pop() if len(letters) == 1 else ''


def iter_nonempty(lines: Iterable[str]) -> Iterator[str]:
    for line in lines:
        if line and line.strip():
            yield line
