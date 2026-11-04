"""What a question's figures are, who may see them, and what a model knows about them (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md (images / evidence group). One place for:

* ``runtime_role(question, img)`` -- the role an image plays in this question, from where its
  ``[[img:N]]`` token appears. A token in the stem or in an option is a stem-side reference: the
  image is never an explanation figure then (a stored 'explanation' becomes 'illustration', or
  'option' for an option field). A token only in the explanation / concept explanation /
  mnemonic makes it an explanation figure. Otherwise the stored role stands.
  ``questions.serializers.resolve_runtime_image_role`` and the image serve view follow this rule.
* ``image_context(question, draft=None)`` -- does the question depend on a figure, and is there
  usable context for a model (``{required, available, missing_reason, ...}``). When the image is
  required and nothing describes it, AI paths abstain with ``image_context_missing`` instead of
  guessing, and the answer-key audit records IMAGE CONTEXT MISSING.
* ``prompt_text`` / ``prompt_fields`` -- question text for prompts with tokens replaced by
  neutral figure descriptions ('[Figure 1: X-ray, chest radiograph PA view]'); for retrieval
  queries the tokens are removed.
* ``figure_bytes(img)`` -- the figure's pixels for a vision model, from local storage only (the
  image file, MEDIA_ROOT or the Supabase storage mirror; never a network fetch), transparent
  backgrounds composited onto white.
* ``serialize_image_for_student(img, revealed=...)`` -- the image dict of the question payloads:
  alt text always, the caption only after the reveal (``caption_reveals_answer``), the proxy URL
  with a signed token for explanation figures shown to an entitled viewer.

Captions, OCR text and AI descriptions are never evidence: a model's description of a figure is a
review signal and is not stored as a caption students see.
"""
from __future__ import annotations

import io
import logging
import os
import re
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r'\[\[img:(\d+)\]\]')
STEM_FIELD = 'question_text'
OPTION_FIELDS = ('option_a', 'option_b', 'option_c', 'option_d')
OPTION_LETTER_BY_FIELD = dict(zip(OPTION_FIELDS, ('A', 'B', 'C', 'D')))
# A token from these fields (and not from the stem / an option) makes an image an explanation
# figure. Mirrored in SQL by questions.recall_search._visible_images.
EXPLANATION_FIELDS = ('explanation', 'concept_explanation', 'mnemonic')
STEM_SIDE_FIELDS = (STEM_FIELD,) + OPTION_FIELDS

MISSING_NO_IMAGE = 'no_image_attached'
MISSING_UNRESOLVED_TOKENS = 'unresolved_tokens'
MISSING_NO_CONTEXT = 'no_figure_context'
ABSTAIN_REASON = 'image_context_missing'

# "The stem mentions a figure": demonstratives / display verbs next to a figure word. Bare
# modality words ("characteristic X-ray finding of scurvy", "ECG changes of hyperkalaemia") are
# text questions and do not match; neither does "shown to reduce mortality".
_FIGURE_WORDS = (
    r'images?|pictures?|photo(?:graph)?s?|photomicrographs?|radiographs?|x[\s-]?rays?|xrays?|skiagrams?|'
    r'figures?|fig\.?|diagrams?|illustrations?|e[ck]gs?|eegs?|ctg|ct(?:\s+scan)?s?|cect|ncct|hrct|mri|'
    r'scans?|films?|slides?|specimens?|smears?|fundus|fundoscopy|instruments?|devices?|charts?|graphs?|'
    r'curves?|tracings?|histology|histopathology|biopsy|angiograms?|ultrasound|usg|sonograms?|'
    r'endoscopy|spirometry|audiograms?|tympanograms?|karyotypes?|pedigrees?|partographs?'
)
_MENTION_PATTERNS = (
    # "this X-ray", "the following ECG", "the given chest radiograph", "below image" -- but not
    # "the following ECG findings / changes" (a text question about findings)
    rf'\b(?:this|these|the\s+following|following|given|accompanying|attached|adjoining|adjacent|above|below)'
    rf'\s+(?:[a-z]+\s+)?(?:{_FIGURE_WORDS})\b'
    r'(?!\s+(?:scans?\s+)?(?:findings?|changes?|features?|signs?|criteria|patterns?|abnormalit(?:y|ies)|'
    r'appearances?|reports?))',
    # "the X-ray shown", "image given below", "lesion depicted", "instrument shown is"
    rf'\b(?:{_FIGURE_WORDS}|lesions?|structures?|organisms?|signs?|appearances?|instruments?|bones?)'
    r'\s+(?:is\s+|are\s+)?(?:shown|given|depicted|displayed|provided|presented|seen\s+(?:here|below|above))\b',
    # "shown in the image", "marked by the arrow", "depicted in the figure" (not "seen on CT")
    rf'\b(?:shown|depicted|displayed|marked|labell?ed|indicated)\s+(?:in|on|by|with)\s+(?:the\s+|an?\s+)?'
    rf'(?:{_FIGURE_WORDS}|arrows?|arrowheads?|asterisks?)\b',
    # "identify the lesion shown", "name the structure marked" (not "name the drug indicated in")
    r'\b(?:identify|name|recogni[sz]e|spot)\s+the\s+(?:[a-z-]+\s+){0,2}?'
    r'(?:shown|marked|labell?ed|depicted|pointed)\b',
    r'\b(?:arrows?|arrowheads?|asterisks?)\s+(?:shows?|indicates?|points?|marks?|marked|in\s+the)\b',
    r'\b(?:see|refer\s+to|look\s+at|observe|study|examine)\s+the\s+(?:[a-z]+\s+)?(?:%s)\b' % _FIGURE_WORDS,
    r'\b(?:image|picture|figure|photo|spotter)[\s-]based\b',
    r'[\[(]\s*(?:image|figure|picture|photo|fig\.?)\s*(?:\d+\s*)?[\])]',
)
IMAGE_MENTION_RE = re.compile('|'.join(f'(?:{p})' for p in _MENTION_PATTERNS), re.IGNORECASE)


def mentions_image(text) -> bool:
    """True when ``text`` (a stem) refers to a figure the reader must look at."""
    if not isinstance(text, str) or not text:
        return False
    return bool(IMAGE_MENTION_RE.search(TOKEN_RE.sub(' ', text)))


def token_ids(text) -> list[int]:
    """Image ids of the ``[[img:N]]`` tokens in ``text``, in order, without duplicates."""
    if not isinstance(text, str) or not text:
        return []
    return list(dict.fromkeys(int(m) for m in TOKEN_RE.findall(text)))


class _QuestionView:
    """A question with unsaved editor values (``draft``) laid over its stored fields."""

    __slots__ = ('_question', '_draft')

    def __init__(self, question, draft):
        self._question = question
        self._draft = draft or {}

    def __getattr__(self, name):
        draft = object.__getattribute__(self, '_draft')
        if name in draft:
            return draft[name]
        return getattr(object.__getattribute__(self, '_question'), name)


def _with_draft(question, draft):
    return _QuestionView(question, draft) if draft else question


def _text(question, field) -> str:
    value = getattr(question, field, '')
    return value if isinstance(value, str) else ''


def runtime_role(question, img, memo: Optional[dict] = None) -> str:
    """The role ``img`` plays in ``question`` (see the module docstring).

    ``memo`` (a dict) caches per (question id, image id) for one response; never share it
    across requests.
    """
    qid = getattr(question, 'pk', None)
    per_q = memo.setdefault(qid, {}) if memo is not None else None
    if per_q is not None and img.id in per_q:
        return per_q[img.id]
    token = f'[[img:{img.id}]]'
    stored = img.role or 'illustration'
    if token in _text(question, STEM_FIELD):
        role = 'illustration' if stored == 'explanation' else stored
    elif any(token in _text(question, field) for field in OPTION_FIELDS):
        role = 'option' if stored == 'explanation' else stored
    elif any(token in _text(question, field) for field in EXPLANATION_FIELDS):
        role = 'explanation'
    else:
        role = stored
    if per_q is not None:
        per_q[img.id] = role
    return role


def active_images(question) -> list:
    """The question's active images in display order (uses a ``images`` prefetch when present)."""
    try:
        rows = list(question.images.all())
    except (AttributeError, ValueError):
        return []
    rows = [img for img in rows if getattr(img, 'is_active', True)]
    rows.sort(key=lambda img: (img.page_number or 0, img.image_index_in_page or 0, img.id or 0))
    return rows


def stem_figures(question, images: Optional[Iterable] = None, memo: Optional[dict] = None, draft=None) -> list:
    """Active images that belong to the question side (runtime role not 'explanation')."""
    view = _with_draft(question, draft)
    rows = list(images) if images is not None else active_images(question)
    return [img for img in rows if runtime_role(view, img, memo) != 'explanation']


def option_letter_for(question, img) -> str:
    """'A'-'D' when the image's token is in an option (or the stored option_label), else ''."""
    token = f'[[img:{img.id}]]'
    for field, letter in OPTION_LETTER_BY_FIELD.items():
        if token in _text(question, field):
            return letter
    label = (getattr(img, 'option_label', '') or '').strip().upper()[:1]
    return label if label in ('A', 'B', 'C', 'D') else ''


def _image_has_text_context(img) -> bool:
    """Neutral text a model may read about the figure: alt text, OCR, a non-revealing caption."""
    if (getattr(img, 'alt_text', '') or '').strip() or (getattr(img, 'ocr_text', '') or '').strip():
        return True
    return bool((getattr(img, 'caption', '') or '').strip() and not getattr(img, 'caption_reveals_answer', True))


def _vision_available() -> bool:
    try:
        from ai_engine.vision import vision_available
    except Exception:  # noqa: BLE001 - optional dependency path
        return False
    try:
        return bool(vision_available())
    except Exception:  # noqa: BLE001
        return False


def image_context(question, draft=None, *, images: Optional[Iterable] = None, check_files: bool = True) -> dict:
    """Does ``question`` depend on a figure, and is there context a model can use?

    Returns ``{required, available, missing_reason, dependency, mentions_image, figures,
    unresolved_token_ids, vision_available}``:

    * ``required``: flagged image-based, ``question_type='image_based'``, a stem that mentions a
      figure, or a ``[[img:N]]`` token in the stem / an option.
    * ``available``: False when a stem / option token points at no active image of this question
      (``missing_reason='unresolved_tokens'``), when a required figure is not attached
      (``'no_image_attached'``), or when the attached figures carry no alt text / OCR /
      non-revealing caption and no vision model can look at them (``'no_figure_context'``).
    * ``dependency``: 'none' | 'present' | 'missing' | 'unresolved_tokens'.

    ``draft`` overlays unsaved editor values (question_text, option_a..d, explanation fields,
    is_image_based, question_type).
    """
    view = _with_draft(question, draft)
    rows = list(images) if images is not None else active_images(question)
    by_id = {img.id: img for img in rows}
    memo: dict = {}
    stem_side_ids = []
    for field in STEM_SIDE_FIELDS:
        stem_side_ids.extend(token_ids(_text(view, field)))
    stem_side_ids = list(dict.fromkeys(stem_side_ids))
    unresolved = [tid for tid in stem_side_ids if tid not in by_id]
    figures = [img for img in rows if runtime_role(view, img, memo) != 'explanation']
    stem = _text(view, STEM_FIELD)
    mention = mentions_image(stem)
    flagged = bool(getattr(view, 'is_image_based', False)) or getattr(view, 'question_type', '') == 'image_based'
    required = bool(flagged or mention or stem_side_ids)
    vision = _vision_available() if (required and figures) else False

    figure_info = []
    for img in figures:
        figure_info.append({
            'id': img.id,
            'role': runtime_role(view, img, memo),
            'modality': img.modality,
            'option_label': option_letter_for(view, img),
            'has_text_context': _image_has_text_context(img),
            'has_local_file': has_local_file(img) if check_files else None,
        })

    if unresolved:
        available, reason = False, MISSING_UNRESOLVED_TOKENS
    elif required and not figures:
        available, reason = False, MISSING_NO_IMAGE
    elif required and not any(f['has_text_context'] for f in figure_info) and not (
            vision and any(f['has_local_file'] for f in figure_info)):
        available, reason = False, MISSING_NO_CONTEXT
    else:
        available, reason = True, ''

    if unresolved:
        dependency = 'unresolved_tokens'
    elif required and not figures:
        dependency = 'missing'
    elif figures:
        dependency = 'present'
    else:
        dependency = 'none'
    return {
        'required': required,
        'available': available,
        'missing_reason': reason,
        'dependency': dependency,
        'mentions_image': mention,
        'figures': figure_info,
        'unresolved_token_ids': unresolved,
        'vision_available': vision,
    }


def image_dependency(question, draft=None) -> str:
    """'none' | 'present' | 'missing' | 'unresolved_tokens' (see ``image_context``)."""
    return image_context(question, draft, check_files=False)['dependency']


def student_image_context(question) -> str:
    """'none' | 'present' | 'missing' -- what a student payload may say about the figure."""
    ctx = image_context(question, check_files=False)
    if not ctx['required']:
        return 'present' if ctx['figures'] else 'none'
    return 'present' if ctx['dependency'] == 'present' else 'missing'


# ── prompt text ─────────────────────────────────────────────────────────────────────────────

def _modality_label(img) -> str:
    modality = getattr(img, 'modality', '') or 'other'
    if modality == 'other':
        return 'image'
    from .models import QuestionImage
    return dict(QuestionImage.MODALITY_CHOICES).get(modality, modality.replace('_', ' '))


def describe_figure(img, number: int, *, include_ocr: bool = False, option_letter: str = '') -> str:
    """'[Figure 2: X-Ray, chest radiograph PA view]' -- neutral, never the revealing caption."""
    parts = [_modality_label(img)]
    alt = (getattr(img, 'alt_text', '') or '').strip()
    if alt:
        parts.append(alt)
    caption = (getattr(img, 'caption', '') or '').strip()
    if caption and not getattr(img, 'caption_reveals_answer', True):
        parts.append(caption)
    if include_ocr:
        ocr = ' '.join((getattr(img, 'ocr_text', '') or '').split())
        if ocr:
            parts.append(f'text in the image: "{ocr[:300]}"')
    label = f'Figure {number}' + (f' (option {option_letter})' if option_letter else '')
    return f'[{label}: {", ".join(parts)}]'


def _figure_numbers(question, images, memo) -> dict:
    return {img.id: index for index, img in enumerate(stem_figures(question, images, memo), start=1)}


def _replace_tokens(text, numbers, by_id, *, for_query, include_ocr, question) -> str:
    def _sub(match):
        if for_query:
            return ' '
        image_id = int(match.group(1))
        img = by_id.get(image_id)
        if img is None or image_id not in numbers:
            return '[Figure: not available]'
        return describe_figure(img, numbers[image_id], include_ocr=include_ocr,
                               option_letter=option_letter_for(question, img))
    out = TOKEN_RE.sub(_sub, text or '')
    return ' '.join(out.split()) if for_query else out


def prompt_fields(question, *, draft=None, for_query: bool = False, include_ocr: bool = False) -> dict:
    """``{question_text, option_a..option_d}`` with ``[[img:N]]`` tokens replaced by neutral figure
    descriptions (removed when ``for_query``). Stem figures not referenced by a token are
    described after the stem, so the model knows a figure exists."""
    view = _with_draft(question, draft)
    rows = active_images(question)
    by_id = {img.id: img for img in rows}
    memo: dict = {}
    numbers = _figure_numbers(view, rows, memo)
    out = {}
    for field in STEM_SIDE_FIELDS:
        out[field] = _replace_tokens(_text(view, field), numbers, by_id, for_query=for_query,
                                     include_ocr=include_ocr, question=view)
    if not for_query:
        referenced = set()
        for field in STEM_SIDE_FIELDS:
            referenced.update(token_ids(_text(view, field)))
        extra = [describe_figure(by_id[image_id], number, include_ocr=include_ocr,
                                 option_letter=option_letter_for(view, by_id[image_id]))
                 for image_id, number in numbers.items() if image_id not in referenced]
        if extra:
            out[STEM_FIELD] = (out[STEM_FIELD].rstrip() + '\n' + '\n'.join(extra)).strip()
    return out


def prompt_text(question, *, draft=None, for_query: bool = False, include_ocr: bool = False) -> str:
    """The stem for a prompt (see ``prompt_fields``)."""
    return prompt_fields(question, draft=draft, for_query=for_query, include_ocr=include_ocr)[STEM_FIELD]


def strip_tokens(text) -> str:
    """``text`` without ``[[img:N]]`` tokens (retrieval queries, previews)."""
    return ' '.join(TOKEN_RE.sub(' ', text or '').split())


# ── pixels ──────────────────────────────────────────────────────────────────────────────────

def _media_path(url: str) -> Optional[str]:
    from django.conf import settings
    if not url.startswith('/media/'):
        return None
    media_root = os.path.realpath(str(settings.MEDIA_ROOT))
    candidate = os.path.realpath(os.path.join(media_root, url[len('/media/'):].split('?', 1)[0]))
    if candidate.startswith(media_root + os.sep) and os.path.isfile(candidate):
        return candidate
    return None


def _mirror_path(url: str) -> Optional[str]:
    if not url.startswith(('http://', 'https://')):
        return None
    from .views import _supabase_storage_mirror_path  # lazy: views imports serializers -> this module
    return _supabase_storage_mirror_path(url)


def local_file_path(img) -> Optional[str]:
    """Absolute path of the figure's bytes on this server, or None (never fetched over the network)."""
    stored = getattr(img, 'file', None)
    if stored:
        try:
            path = stored.path
        except (ValueError, NotImplementedError):
            path = None
        if path and os.path.isfile(path):
            return path
    url = (getattr(img, 'url', '') or '').strip()
    if not url:
        return None
    return _media_path(url) or _mirror_path(url)


def has_local_file(img) -> bool:
    try:
        return local_file_path(img) is not None
    except Exception:  # noqa: BLE001 - a broken storage row is "no file"
        return False


def flatten_to_rgb(pil_img):
    """RGB copy of a Pillow image; transparency composited onto white (black backgrounds made
    line diagrams and ECGs unreadable)."""
    from PIL import Image
    if pil_img.mode in ('RGBA', 'LA') or (pil_img.mode == 'P' and 'transparency' in pil_img.info):
        rgba = pil_img.convert('RGBA')
        background = Image.new('RGB', rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel('A'))
        return background
    return pil_img.convert('RGB') if pil_img.mode != 'RGB' else pil_img


def figure_bytes(img, max_px: int = 1024) -> Optional[bytes]:
    """PNG / JPEG bytes of the figure, long side at most ``max_px``, or None when the file is not
    on this server. PNG and GIF sources stay PNG (diagrams), others become JPEG."""
    path = local_file_path(img)
    if not path:
        return None
    try:
        from PIL import Image
        with Image.open(path) as src:
            fmt = (src.format or '').upper()
            src.load()
            pil = flatten_to_rgb(src)
        if max(pil.size) > max_px:
            pil.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        if fmt in ('PNG', 'GIF'):
            pil.save(buf, format='PNG', optimize=True)
        else:
            pil.save(buf, format='JPEG', quality=88, optimize=True)
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001 - unreadable figure = no figure
        logger.warning('figure_bytes: image %s unreadable (%s)', getattr(img, 'id', '?'), type(exc).__name__)
        return None


# ── payload dicts ───────────────────────────────────────────────────────────────────────────

SERVE_PATH = '/api/questions/images/{id}/serve/'

# Supabase Storage was shut down on 2026-11-03 (the project is gone, its host no longer resolves).
# Figures stored with such an address are served by the image endpoint from the restored copy
# (SUPABASE_STORAGE_MIRROR_DIR); a browser is never sent to the old host.
_RETIRED_STORAGE_URL_RE = re.compile(r'^https?://[^/?#]+\.supabase\.co/storage/', re.IGNORECASE)


def is_retired_storage_url(url) -> bool:
    """True for an address on retired Supabase Storage (never handed to a browser)."""
    return bool(url) and bool(_RETIRED_STORAGE_URL_RE.match(str(url).strip()))


def image_proxy_url(img, request=None) -> str:
    path = SERVE_PATH.format(id=img.id)
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:  # noqa: BLE001
            return path
    return path


def _student_url(img, role, *, revealed, request, prefer_stored_url) -> str:
    from django.conf import settings
    from .image_access import with_image_token
    stored = (getattr(img, 'url', '') or '').strip()
    use_stored = (prefer_stored_url and stored.startswith(('http://', 'https://')) and role != 'explanation'
                  and not is_retired_storage_url(stored)
                  and not getattr(settings, 'SUPABASE_STORAGE_MIRROR_DIR', ''))
    if use_stored:
        return stored
    url = image_proxy_url(img, request)
    if role == 'explanation' and revealed:
        url = with_image_token(url, img.id)
    return url


def serialize_image_for_student(img, *, revealed: bool, question=None, request=None, role: Optional[str] = None,
                                memo: Optional[dict] = None, prefer_stored_url: bool = False) -> dict:
    """The image dict of the student question payloads.

    ``revealed``: the viewer may see this question's answer (entitled and, where the caller knows
    it, after the reveal). Before that the dict carries the neutral ``alt_text`` and no caption
    when the caption may name the answer (``caption_reveals_answer``); explanation figures get a
    signed URL only when revealed (callers drop them from locked payloads). The URL is the image
    proxy (``prefer_stored_url`` keeps a stored public URL for stem-side figures when no storage
    mirror is configured, the detail payload's old behaviour). OCR text is never included.
    """
    question = question if question is not None else img.question
    role = role or runtime_role(question, img, memo)
    caption = (img.caption or '').strip()
    show_caption = bool(caption) and (revealed or not getattr(img, 'caption_reveals_answer', True))
    return {
        'id': img.id,
        'page_number': img.page_number,
        'image_index_in_page': img.image_index_in_page,
        'role': role,
        'modality': img.modality,
        'mime': img.mime,
        'width': img.width,
        'height': img.height,
        'url': _student_url(img, role, revealed=revealed, request=request, prefer_stored_url=prefer_stored_url),
        'sha256_short': img.sha256_short,
        'alt_text': (getattr(img, 'alt_text', '') or '').strip(),
        'option_label': option_letter_for(question, img),
        'caption': caption if show_caption else '',
        'caption_after_reveal': bool(caption) and not show_caption,
    }


def serialize_image_for_admin(img, *, question=None, request=None, memo: Optional[dict] = None) -> dict:
    """Everything an admin edits about a figure (stored and runtime role, alt text, caption, OCR,
    option label, role provenance) with a signed proxy URL. Never a file path."""
    from .image_access import with_image_token
    question = question if question is not None else img.question
    return {
        'id': img.id,
        'role': runtime_role(question, img, memo),
        'stored_role': img.role,
        'role_source': getattr(img, 'role_source', ''),
        'modality': img.modality,
        'alt_text': getattr(img, 'alt_text', '') or '',
        'caption': img.caption or '',
        'caption_reveals_answer': bool(getattr(img, 'caption_reveals_answer', True)),
        'ocr_text': img.ocr_text or '',
        'option_label': option_letter_for(question, img),
        'page_number': img.page_number,
        'image_index_in_page': img.image_index_in_page,
        'width': img.width,
        'height': img.height,
        'uploaded_by_admin': bool(img.uploaded_by_admin),
        'has_local_file': has_local_file(img),
        'url': with_image_token(image_proxy_url(img, request), img.id),
    }
