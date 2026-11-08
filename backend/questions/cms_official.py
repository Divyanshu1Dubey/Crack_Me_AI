"""UPSC CMS papers made to match the official question papers and answer keys (2026-11-07 / 08).

Plans (each applied by one data migration):

* ``data/cms_official_2018_2025.json`` (questions.0047): source "UPSC CMS 2009-2025 with Answer Key.pdf" (the
  owner's copy of the official question papers and UPSC answer keys, Series A). Every bank question of those years
  was matched to its official question by text, every key that disagreed was checked on a crop of the key page,
  and every question added was typed from the scanned paper.
* ``data/cms_official_2026.json`` (questions.0048): the official 2026 papers (Series A) the owner supplied:
  numbering, layouts, figures cropped from the scans. No official 2026 key exists yet: no key is changed.
* ``data/cms_official_2014_2017.json`` (questions.0049): the same PDF's text layer: 939 official questions added
  with the key of the paper's key table (spelling slips of the transcription corrected, each listed on its
  ``add`` as ``spelling``), 21 untagged copies tagged, their second copies hidden.

Each operation on an existing row was written for the row as it was found (stem hash, key, active flag, paper).
A row is touched only while it still matches, so an admin's later edit wins and a second run changes nothing.
Before a row changes its previous state is stored as a ``QuestionRevisionSnapshot`` (the editor can show and undo
it); nothing is deleted.

Operations, in this order:

* ``hide``    a second copy of an official question (``keep``: the copy kept) or a question that is not in
              the official paper or is broken: ``is_active=False``.
* ``repair``  text damaged on import (lost options, text between '<' and '>' stripped) set to the official text.
* ``restore`` a hidden question that is the only copy of an official question: active again, its key set.
* ``format``  the same words laid out as the paper prints them (statements on their own lines, tables).
* ``add``     an official question the bank lacked: created with the official text and key; the subject is the
              paper's section (``subject_name``; up to 2017 Paper I ends with General Ability, 91-120), and
              skipped when the bank already has it (``_same_question``).
* ``place``   ``paper`` and ``display_number`` (the number in the official paper), and ``year`` (``to_year``)
              for a copy that had none.
* ``subject`` the paper's section as subject (the topic follows when the new subject has one of the same name).
* ``key``     the official key, recorded like ``questions.editorial.change_answer_key``: an ``AnswerKeyChange``
              with the official key as evidence, the old key kept there, an explanation written for the old key
              marked stale (students are not shown it; it is generated again for the new key).
* ``dropped`` UPSC dropped the question (no answer was scored): ``is_dropped=True``; it stays active.
* ``figure``  a figure cropped from the official paper attached (and the question made live when it was hidden
              only for the missing figure).
* ``mojibake`` UTF-8 text that was read as cp437 ("ΓåÆ" for "→", "┬░" for "°") decoded back; hashes recorded
              for the old text (explanation, reviews, evidence) move to the new text, which says the same.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from questions.content_hashes import stem_hash, valid_key
# QuestionViewSet._serialize_revision_state (content_repairs' tests keep the two in step)
from questions.content_repairs import REVISION_FIELDS

DATA = Path(__file__).resolve().parent / 'data' / 'cms_official_2018_2025.json'
DATA_2026 = Path(__file__).resolve().parent / 'data' / 'cms_official_2026.json'
DATA_2014_2017 = Path(__file__).resolve().parent / 'data' / 'cms_official_2014_2017.json'
OP_ORDER = ('hide', 'repair', 'restore', 'format', 'add', 'place', 'subject', 'key', 'dropped', 'figure', 'mojibake')
# questions/media_restore.py writes a staged file to MEDIA_ROOT when the image endpoint first asks for it (and
# start_web.sh restores every staged file at container start); same table as scripts/railway/upload_media_to_db.py
MEDIA_DDL = """
CREATE TABLE IF NOT EXISTS ops_media_transfer (
    id bigserial PRIMARY KEY,
    target text NOT NULL CHECK (target IN ('media', 'mirror')),
    rel_path text NOT NULL,
    sha256 char(64) NOT NULL,
    size bigint NOT NULL,
    data bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (target, rel_path)
)
"""
TEXT_FIELDS = ('question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'explanation', 'concept_explanation',
               'mnemonic', 'why_correct', 'why_wrong_a', 'why_wrong_b', 'why_wrong_c', 'why_wrong_d', 'ai_explanation',
               'ai_answer', 'ai_mnemonic', 'ai_clinical_pearl', 'reference_text', 'learning_technique', 'shortcut_tip')
STEM_FIELDS = ('question_text', 'option_a', 'option_b', 'option_c', 'option_d')
EXPLANATION_FIELDS = ('explanation', 'concept_explanation', 'mnemonic')


def load_data(path: Path | None = None) -> dict:
    path = Path(path or DATA)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['_dir'] = str(path.parent)
    return data


# The 2018 Paper II runs Preventive & Social Medicine (1-40), Obstetrics & Gynaecology (41-80), Surgery (81-120).
SECTION_ORDER = {(2018, 2): ('Community Medicine', 'Obstetrics & Gynaecology', 'General Surgery')}


def subject_name(paper: int, n: int, year: int | None = None) -> str:
    if (year, paper) in SECTION_ORDER:
        return SECTION_ORDER[(year, paper)][min((n - 1) // 40, 2)]
    if paper == 1:
        return 'General Medicine' if n <= 96 else 'Paediatrics'
    return 'General Surgery' if n <= 40 else 'Obstetrics & Gynaecology' if n <= 80 else 'Community Medicine'


# ── mojibake ─────────────────────────────────────────────────────────────────────────────────────────────────────
_CP437 = {bytes([b]).decode('cp437'): b for b in range(0x80, 0x100)}


def repair_mojibake(text):
    """Decode every run of cp437 characters that spells a valid UTF-8 sequence ('ΓåÆ' -> '→', '├ù' -> '×').
    A character outside such a run (real Greek, accents, '°' followed by text) is left as it is."""
    if not text or not isinstance(text, str):
        return text
    out, i = [], 0
    while i < len(text):
        lead = _CP437.get(text[i])
        if lead is not None and 0xC2 <= lead <= 0xF4:
            size = 2 if lead < 0xE0 else 3 if lead < 0xF0 else 4
            seq = text[i:i + size]
            if len(seq) == size and all(c in _CP437 and 0x80 <= _CP437[c] <= 0xBF for c in seq[1:]):
                try:
                    out.append(bytes(_CP437[c] for c in seq).decode('utf-8'))
                    i += size
                    continue
                except UnicodeDecodeError:
                    pass
        out.append(text[i])
        i += 1
    return ''.join(out)


def explanation_hash(question) -> str:
    parts = [(getattr(question, name, '') or '').strip() for name in EXPLANATION_FIELDS]
    return hashlib.sha256('\x1f'.join(parts).encode('utf-8')).hexdigest()


def revision_state(question) -> dict:
    return {name: getattr(question, name, None) for name in REVISION_FIELDS}


# ── checks ───────────────────────────────────────────────────────────────────────────────────────────────────────
def row_refusal(question, guard: dict) -> str:
    """Why the row no longer is the row the plan was written for ('' when it is)."""
    if question is None:
        return 'missing'
    if stem_hash(question) != guard['stem_hash']:
        return 'stem or options changed'
    if 'key' in guard and valid_key(question.correct_answer) != guard['key']:
        return 'key changed'
    if 'active' in guard and question.is_active != guard['active']:
        return 'active flag changed'
    if 'cur_paper' in guard and question.paper != guard['cur_paper']:
        return 'paper changed'
    return ''


def _canon_stem(text: str) -> str:
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in (text or '').casefold()).split())


def _same_question(text: dict, other) -> bool:
    """``other`` (a bank row) is the question ``text`` describes: the same opening words and at least three of the
    four options. A stem alone is not enough: "Which one of the following pairs is not correctly matched?" is
    asked several times in one year, with other pairs as options."""
    if _canon_stem(other.question_text)[:120] != _canon_stem(text['question_text'])[:120]:
        return False
    mine = [_canon_stem(text.get(f'option_{letter}')) for letter in 'abcd']
    theirs = [_canon_stem(getattr(other, f'option_{letter}', '')) for letter in 'abcd']
    return sum(1 for option in mine if option and option in theirs) >= 3


def evidence_for(data: dict, op: dict, new_key: str) -> list[dict]:
    year, paper = op['off'][:4], op['off'][-1]
    return [{
        'kind': 'official_key',
        'source_title': data['source']['title'],
        'source_sha256': data['source']['sha256'],
        'year': int(year),
        'tier': 1,
        'page_start': op['key_page'],
        'page_end': op['key_page'],
        'page_label': f"UPSC answer key, CMS {year} Paper {'I' if paper == '1' else 'II'}, Series A",
        'quote': f"{op['n']}. {op.get('official', new_key)}",
        'supports_option': new_key,
    }]


class _Models:
    def __init__(self, question, snapshot, key_change, subject, audit=None, extra_hash_models=(), image=None):
        self.Question, self.Snapshot, self.KeyChange, self.Subject = question, snapshot, key_change, subject
        self.Audit, self.Image = audit, image
        # (model, field) pairs that store a questions.content_hashes.stem_hash of a question
        self.extra_hash_models = tuple(extra_hash_models)


def apply_plan(*, question_model, snapshot_model, key_change_model, subject_model, audit_model=None,
               extra_hash_models=(), image_model=None, data=None, now=None) -> Counter:
    """Apply the plan; returns a Counter of outcomes ('<op> applied', '<op> skipped: <why>')."""
    data = data or load_data()
    m = _Models(question_model, snapshot_model, key_change_model, subject_model, audit_model, extra_hash_models,
                image_model)
    now = now or timezone.now()
    results = Counter()
    ops = sorted(data['ops'], key=lambda o: OP_ORDER.index(o['op']))

    # 1. every touched row is checked once, against the state the plan was written for
    guards, row_ops = {}, defaultdict(list)
    for op in ops:
        if op.get('id') is not None:
            guards.setdefault(op['id'], op)
            row_ops[op['id']].append(op['op'])
    rows = m.Question.objects.in_bulk(list(guards))
    usable = {}
    for qid, guard in guards.items():
        why = row_refusal(rows.get(qid), guard)
        if why:
            for name in row_ops[qid]:
                results[f'{name} skipped: {why}'] += 1
        else:
            usable[qid] = rows[qid]
    snapshotted = set()

    def snapshot(question, reason):
        if question.pk in snapshotted:
            return
        m.Snapshot.objects.create(question_id=question.pk, changed_by=None, reason=reason[:200],
                                  snapshot=revision_state(question))
        snapshotted.add(question.pk)

    added_keys = {(op['off'], op['n']): op['to'] for op in ops if op['op'] == 'key' and op.get('id') is None}
    subjects = {}
    added = set()  # (paper, number) of the questions this run added

    for op in ops:
        kind, qid = op['op'], op.get('id')
        if qid is not None and qid not in usable:
            continue
        q = usable.get(qid)
        if kind == 'hide' and op.get('keep') in guards and op['keep'] not in usable:
            results['hide skipped: kept copy changed since the plan'] += 1
            continue
        try:
            with transaction.atomic():
                outcome = _apply_one(m, data, op, q, snapshot, added_keys, subjects, now, added)
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the deploy
            outcome = f'skipped: error {type(exc).__name__}'
        results[f'{kind} {outcome}'] += 1
    return results


# Subjects a plan may need that a bank may not have yet: name -> (code, paper, description)
CREATABLE_SUBJECTS = {
    'General Ability': ('GENABIL', 1, 'General Ability section of CMS Paper I (papers up to 2017).'),
}


def _subject(m, subjects, name):
    if name not in subjects:
        subject = m.Subject.objects.filter(name=name).first()
        if subject is None and name in CREATABLE_SUBJECTS:
            code, paper, description = CREATABLE_SUBJECTS[name]
            if not m.Subject.objects.filter(code=code).exists():
                subject = m.Subject.objects.create(name=name, code=code, exam_type='cms', paper=paper,
                                                   description=description)
        subjects[name] = subject
    return subjects[name]


def _apply_one(m, data, op, q, snapshot, added_keys, subjects, now, added) -> str:
    kind = op['op']
    label = (f"CMS official reconciliation {data.get('prepared', '2026-11-07')} "
             f"({op.get('off', 'bank')} Q{op.get('n', '-')})")
    if kind == 'hide':
        if not q.is_active:
            return 'skipped: already hidden'
        if op.get('keep'):
            keep = m.Question.objects.filter(pk=op['keep']).first()
            if keep is None or not keep.is_active:
                return 'skipped: kept copy not active'
        snapshot(q, f"{label}: hidden, {op['reason']}")
        m.Question.objects.filter(pk=q.pk).update(is_active=False, updated_at=now)
        q.is_active = False
        return 'applied'
    if kind in ('repair', 'restore'):
        snapshot(q, f"{label}: {'restored' if kind == 'restore' else 'text repaired'}"
                    f"{' - ' + op['reason'] if op.get('reason') else ''}")
        updates = dict(op.get('fields') or op.get('text') or {})
        if kind == 'restore':
            updates.update(is_active=True, is_dropped=False)
        for field, value in updates.items():
            setattr(q, field, value)
        m.Question.objects.filter(pk=q.pk).update(updated_at=now, **updates)
        return 'applied'
    if kind == 'add':
        year, paper, n = op['year'], op['paper'], op['n']
        text = op['text']
        for other in m.Question.objects.filter(exam_type='cms', year=year).only('id', *STEM_FIELDS):
            if _same_question(text, other):
                return 'skipped: already in the bank'
        name = op.get('subject') or subject_name(paper, n, year)
        subject = _subject(m, subjects, name)
        if subject is None:
            return f'skipped: no subject {name}'
        key = added_keys.get((op['off'], n), '')
        m.Question.objects.create(
            exam_type='cms', exam_source='UPSC CMS', year=year, paper=paper, display_number=n,
            subject=subject, correct_answer=key, is_active=True, needs_review=bool(op.get('needs_review')),
            source=(op.get('source') or
                    f"UPSC CMS {year} Paper {'I' if paper == 1 else 'II'} (official paper, Series A) Q{n}")[:200],
            **{field: text[field] for field in STEM_FIELDS})
        added.add((op['off'], n))
        return 'applied'
    if kind == 'place':
        year = op.get('to_year', q.year)
        if q.paper == op['to_paper'] and q.display_number == op['to_n'] and q.year == year:
            return 'skipped: already numbered so'
        snapshot(q, f'{label}: numbered as in the official paper')
        m.Question.objects.filter(pk=q.pk).update(paper=op['to_paper'], display_number=op['to_n'], year=year,
                                                  updated_at=now)
        q.paper, q.display_number, q.year = op['to_paper'], op['to_n'], year
        return 'applied'
    if kind == 'subject':
        subject = _subject(m, subjects, op['to_subject'])
        if subject is None:
            return f"skipped: no subject {op['to_subject']}"
        if q.subject_id == subject.pk:
            return 'skipped: already in that subject'
        # the topic belongs to the old subject: the topic of the same name in the new one, else none
        topic_id = None
        if q.topic_id:
            old_topic = m.Question._meta.get_field('topic').related_model.objects.filter(pk=q.topic_id).first()
            if old_topic is not None:
                same = old_topic.__class__.objects.filter(subject_id=subject.pk, name=old_topic.name).first()
                topic_id = same.pk if same else None
        snapshot(q, f"{label}: subject {op['to_subject']} (the paper's section)")
        m.Question.objects.filter(pk=q.pk).update(subject_id=subject.pk, topic_id=topic_id, updated_at=now)
        return 'applied'
    if kind == 'key':
        if op.get('id') is None:  # set when the question was added
            return 'applied' if (op['off'], op['n']) in added else 'skipped: question not added in this run'
        old, new = valid_key(q.correct_answer), op['to']
        if old == new:
            return 'skipped: already the official key'
        snapshot(q, f"{label}: official key {new}")
        # an explanation argues for the old key, unless it was written for the official one all along
        had_explanation = (bool((q.explanation or '').strip() or (q.ai_explanation or '').strip())
                           and (getattr(q, 'explanation_for_key', '') or '') != new)
        audit = m.Audit.objects.filter(question_id=q.pk).first() if m.Audit is not None else None
        m.KeyChange.objects.create(
            question_id=q.pk, old_key=old, new_key=new, changed_by=None, source='official_key',
            reason=(f"Official UPSC answer key: CMS {op['off'][:4]} Paper {'I' if op['off'][-1] == '1' else 'II'} "
                    f"(Series A) Q{op['n']} is {op.get('official', new)}"),
            evidence=evidence_for(data, op, new), explanation_action='kept_stale' if had_explanation else '',
            audit_status_before=getattr(audit, 'status', '') or '', audit_id=getattr(audit, 'pk', None))
        updates = {'correct_answer': new, 'is_disputed': False, 'needs_review': False,
                   'answer_key_status': 'unaudited', 'updated_at': now}
        if had_explanation:
            # the same reason questions.editorial.change_answer_key records (the column holds 40 characters)
            updates.update(explanation_status='stale', explanation_status_reason=f'Key changed from {old} to {new}')
        m.Question.objects.filter(pk=q.pk).update(**updates)
        q.correct_answer = new
        return 'applied'
    if kind == 'dropped':
        if q.is_dropped:
            return 'skipped: already dropped'
        snapshot(q, f'{label}: dropped by UPSC')
        m.Question.objects.filter(pk=q.pk).update(is_dropped=True, updated_at=now)
        return 'applied'
    if kind == 'format':
        q = m.Question.objects.get(pk=q.pk)
        if all(getattr(q, field) == value for field, value in op['fields'].items()):
            return 'skipped: already formatted'
        return _rewrite(m, q, dict(op['fields']), snapshot, f"{label}: {op['reason']}", now)
    if kind == 'figure':
        return _attach_figures(m, data, op, q, snapshot, label, now)
    if kind == 'mojibake':
        q = m.Question.objects.get(pk=q.pk)  # current values (earlier operations may have run)
        updates = {}
        for field in TEXT_FIELDS:
            value = getattr(q, field, None)
            fixed = repair_mojibake(value)
            if isinstance(value, str) and fixed != value:
                updates[field] = fixed
        if not updates:
            return 'skipped: nothing to repair'
        return _rewrite(m, q, updates, snapshot, f'{label}: characters repaired (mojibake)', now)
    return 'skipped: unknown operation'


def _attach_figures(m, data, op, q, snapshot, label, now) -> str:
    """The figure cropped from the official paper: staged for the media volume (Postgres) and attached as the
    question's image; a question hidden only because its figure was missing becomes live."""
    from django.db import connection

    if m.Image is None:
        return 'skipped: no image model'
    if m.Image.objects.filter(question_id=q.pk, is_active=True).exclude(role='explanation').exists():
        return 'skipped: already has its figure'
    folder = Path(data.get('_dir') or DATA.parent) / data.get('figures_dir', '')
    staged = []
    for fig in op['figures']:
        blob = (folder / fig['file']).read_bytes()
        if hashlib.sha256(blob).hexdigest() != fig['sha256']:
            return 'skipped: figure file does not match its checksum'
        staged.append((fig, blob, f"question_figures/official/{fig['file']}"))
    if connection.vendor == 'postgresql':
        with connection.cursor() as cur:
            cur.execute(MEDIA_DDL)
            for fig, blob, rel in staged:
                cur.execute('INSERT INTO ops_media_transfer (target, rel_path, sha256, size, data) VALUES '
                            '(%s, %s, %s, %s, %s) ON CONFLICT (target, rel_path) DO UPDATE SET sha256 = EXCLUDED.sha256, '
                            'size = EXCLUDED.size, data = EXCLUDED.data, created_at = now()',
                            ['media', rel, fig['sha256'], len(blob), blob])
    snapshot(q, f'{label}: figure attached from the official paper')
    for index, (fig, blob, rel) in enumerate(staged):
        m.Image.objects.create(
            question_id=q.pk, page_number=int(fig.get('page') or 0), image_index_in_page=index, url=f'/media/{rel}',
            mime='image/jpeg', width=fig['width'], height=fig['height'], bytes=len(blob), sha256=fig['sha256'],
            sha256_short=fig['sha256'][:16], role='primary', role_source='position_heuristic', is_active=True,
            alt_text='Figure for this question (official question paper)', caption_source='source_pdf')
    if op.get('activate') and not q.is_active:
        m.Question.objects.filter(pk=q.pk).update(is_active=True, needs_review=False, updated_at=now)
        q.is_active = True
        return 'applied (question made live)'
    return 'applied'


def _rewrite(m, q, updates, snapshot, reason, now) -> str:
    """A formatting-only text change (same words): the hashes recorded for the old text move to the new text, so
    the explanation, its review and the audit's reviews stay attached to the question."""
    old_stem, old_expl = stem_hash(q), explanation_hash(q)
    snapshot(q, reason)
    for field, value in updates.items():
        setattr(q, field, value)
    new_stem, new_expl = stem_hash(q), explanation_hash(q)
    if q.explanation_stem_hash == old_stem:
        updates['explanation_stem_hash'] = new_stem
    if getattr(q, 'explanation_hash', '') == old_expl:
        updates['explanation_hash'] = new_expl
    if getattr(q, 'explanation_reviewed_hash', '') == old_expl:
        updates['explanation_reviewed_hash'] = new_expl
    m.Question.objects.filter(pk=q.pk).update(updated_at=now, **updates)
    if new_stem != old_stem:
        _carry_stem_hash(m, q.pk, old_stem, new_stem)
    return 'applied'


def _carry_stem_hash(m, qid, old, new):
    """Reviews / evidence recorded for the text before the repair stay valid: the words are the same."""
    if m.Audit is not None:
        for audit in m.Audit.objects.filter(question_id=qid):
            reviews = audit.reviews or []
            if any(isinstance(r, dict) and r.get('stem_hash') == old for r in reviews):
                audit.reviews = [dict(r, stem_hash=new) if isinstance(r, dict) and r.get('stem_hash') == old else r
                                 for r in reviews]
                audit.save(update_fields=['reviews'])
    for model, field in m.extra_hash_models:
        model.objects.filter(question_id=qid, **{field: old}).update(**{field: new})
