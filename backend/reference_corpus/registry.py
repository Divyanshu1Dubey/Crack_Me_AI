"""Source registry: which files make up the reference corpus and what is known about them.

The registry (``settings.REFERENCE_REGISTRY_PATH``, written by
``python -m ai_eval.build_reference_corpus registry``) classifies each file from its name only.
Title, edition and year are kept exactly as the registry states them: a missing edition or
year stays empty, nothing is inferred here.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ai_engine import lexical_index as lx

from .store import SOURCE_KINDS

# Not evidence: an indexed web note claiming "exact chapter and page numbers" for an edition
# that is not in the corpus, and documents about competitors.
EXTRA_EXCLUDED_PATTERNS = (r'page[\s_-]*map', r'competitor')
_EXTRA_EXCLUDED_RE = re.compile('|'.join(EXTRA_EXCLUDED_PATTERNS), re.IGNORECASE)

# What students may see from a source (evidence.EvidenceSource.student_display). Snippets are
# capped at EVIDENCE_SNIPPET_MAX_CHARS by the serving code; page images are always admin-only.
STUDENT_DISPLAY_BY_TIER = {1: 'snippet', 2: 'snippet', 3: 'snippet', 4: 'snippet', 5: 'citation'}

SUPPORTED_EXTENSIONS = ('.pdf', '.docx', '.txt', '.md')


@dataclass
class SourceSpec:
    sha256: str
    title: str
    file_name: str
    path: str
    tier: int
    kind: str
    licence: str
    edition: Optional[str] = None
    year: Optional[int] = None
    subject: Optional[str] = None
    pages: Optional[int] = None
    scanned: bool = False
    is_excerpt: bool = False
    student_display: str = 'citation'
    excluded_reason: str = ''
    extra: dict = field(default_factory=dict)

    @property
    def extension(self) -> str:
        return os.path.splitext(self.file_name)[1].lower()


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def spec_from_row(row: dict) -> SourceSpec:
    sha = (row.get('sha256') or '').strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', sha):
        raise ValueError('registry row without a valid sha256')
    title = _clean(row.get('title'))
    if not title:
        raise ValueError(f'registry row {sha[:12]} has no title')
    try:
        tier = int(row.get('tier'))
    except (TypeError, ValueError):
        raise ValueError(f'registry row {sha[:12]} has no tier')
    if not 1 <= tier <= 5:
        raise ValueError(f'registry row {sha[:12]}: tier {tier} outside 1-5')
    kind = (row.get('kind') or 'other').strip().lower()
    if kind not in SOURCE_KINDS:
        kind = 'other'
    year = row.get('year')
    try:
        year = int(year) if year not in (None, '') else None
    except (TypeError, ValueError):
        year = None
    path = row.get('path') or ''
    file_name = row.get('file_name') or os.path.basename(path)
    spec = SourceSpec(
        sha256=sha, title=title, file_name=file_name, path=path, tier=tier, kind=kind,
        licence=_clean(row.get('licence')) or 'unknown - internal use only',
        edition=_clean(row.get('edition')), year=year, subject=_clean(row.get('subject')),
        pages=row.get('pages') if isinstance(row.get('pages'), int) else None,
        scanned=bool(row.get('scanned')),
        is_excerpt='(excerpt)' in title.lower() or bool(row.get('is_excerpt')),
        student_display=STUDENT_DISPLAY_BY_TIER[tier],
    )
    spec.excluded_reason = exclusion_reason(spec)
    return spec


def exclusion_reason(spec: SourceSpec) -> str:
    if lx.is_excluded_document(spec.title, spec.file_name):
        return 'not study material (lexical_index.EXCLUDED_DOCUMENT_PATTERNS)'
    if _EXTRA_EXCLUDED_RE.search(f'{spec.title} {spec.file_name}'.replace('_', ' ')):
        return 'not evidence (page map / competitor document)'
    if spec.extension not in SUPPORTED_EXTENSIONS:
        return f'unsupported file type {spec.extension or "(none)"}'
    return ''


def load_registry(path: str) -> list[SourceSpec]:
    """Registry rows as SourceSpecs (first row wins for a repeated sha256)."""
    with open(path, encoding='utf-8') as fh:
        rows = json.load(fh)
    if not isinstance(rows, list):
        raise ValueError('registry must be a JSON list')
    specs, seen = [], set()
    for row in rows:
        spec = spec_from_row(row)
        if spec.sha256 in seen:
            continue
        seen.add(spec.sha256)
        specs.append(spec)
    return specs


def select(specs: Iterable[SourceSpec], prefixes: Optional[Iterable[str]]) -> list[SourceSpec]:
    """Only the specs whose sha256 starts with one of ``prefixes`` (all when None/empty)."""
    prefixes = [p.strip().lower() for p in (prefixes or []) if p and p.strip()]
    specs = list(specs)
    if not prefixes:
        return specs
    return [s for s in specs if any(s.sha256.startswith(p) for p in prefixes)]
