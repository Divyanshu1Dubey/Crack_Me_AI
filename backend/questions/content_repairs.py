"""Reviewed one-off repairs of question content, applied once per database by a data migration.

A repair is written for one question as it was found: it applies only while the row still holds the
expected key and the defect text (``requires`` / ``forbids``), so an admin's later edit wins and a
second run changes nothing. Before writing, the previous state is stored as a
``QuestionRevisionSnapshot`` (same shape as ``QuestionViewSet._serialize_revision_state``), so the
editor's revision history shows the change and can undo it. Keys are never changed here.

Explanations written here are AI-written (``explanation_origin`` 'ai', or 'mixed' when added to
imported text) and stay ``ai_generated`` until an admin reviews them in the editor.
"""
from __future__ import annotations

import hashlib

from django.db import transaction
from django.utils import timezone

from questions.content_hashes import stem_hash, valid_key

# QuestionViewSet._serialize_revision_state (tests keep the two in step).
REVISION_FIELDS = (
    'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'year', 'subject_id',
    'topic_id', 'difficulty', 'paper', 'concept_id', 'explanation', 'concept_explanation', 'mnemonic',
    'book_name', 'chapter', 'page_number', 'reference_text', 'textbook_references', 'concept_tags',
    'ai_answer', 'ai_explanation', 'ai_references', 'is_verified_by_admin', 'verified_note', 'is_active',
)
EXPLANATION_FIELDS = ('explanation', 'concept_explanation', 'mnemonic')


def explanation_hash(question) -> str:
    """Same as questions.editorial.explanation_hash (tests keep the two in step)."""
    parts = [(getattr(question, name, '') or '').strip() for name in EXPLANATION_FIELDS]
    return hashlib.sha256('\x1f'.join(parts).encode('utf-8')).hexdigest()


def revision_state(question) -> dict:
    return {name: getattr(question, name, None) for name in REVISION_FIELDS}


# ── 2026-11-07 ────────────────────────────────────────────────────────────────────────────────────
# #2058 / #2065 / #2103 / #2113 (CMS 2025 Paper I): the key was corrected earlier (key-audit signal
# "key_changed": B->C, A->C, B->D, A->D) but the locked explanation still argued for the old key.
# The current keys follow standard teaching (pellagra and maize; osteoarthritis spares the ankle and
# involves C5-C6; CHIPES radiopaque poisons; the RBSK "Deficiencies" group), so the explanations are
# rewritten for them. #22462 (CMS 2022 Paper II Q118): the stem lost its five Apgar observations;
# they come from Medura_Train/PYQ/2022paper2.txt and score 3, the stored key (C).

PELLAGRA = (
    "The sore mouth with a bright red tongue (glossitis), diarrhoea, irritability and a pigmented, scaly "
    "rash around the neck (Casal's necklace, on sun-exposed skin) point to **pellagra**, the disease of "
    "niacin (vitamin B3) deficiency.\n\n"
    "Pellagra is classically seen where **maize (corn)** is the staple food. Most of the niacin in maize "
    "is bound and cannot be absorbed unless the grain is treated with alkali, and maize protein is low in "
    "tryptophan, from which the body makes niacin. In India it is also seen in people who live mainly on "
    "jowar (sorghum), whose high leucine content interferes with niacin metabolism.\n\n"
    "Rice and wheat are not the classic association, and fish is a good source of niacin.\n\n"
    "**Answer: (c) Corn**"
)
OSTEOARTHRITIS = (
    "Primary osteoarthritis typically involves the knees, the hips, the small joints of the hand (distal "
    "and proximal interphalangeal joints and the base of the thumb), the **first metatarsophalangeal "
    "joint**, and the **spine**: the lower cervical spine (C5-C6 is the level most often affected) and "
    "the lumbar spine.\n\n"
    "The wrist, the elbow and the **ankle** are usually spared. Osteoarthritis of the ankle is uncommon "
    "and usually follows an earlier injury.\n\n"
    "So I (first MTP joint), II (PIP joint) and IV (C5-C6) are commonly affected, while III (ankle) is "
    "not.\n\n"
    "**Answer: (c) I, II and IV only**"
)
RADIOPAQUE = (
    "Poisons that can be seen as a radiopaque density on a plain abdominal X-ray are remembered by the "
    "mnemonic **CHIPES**: **C**hloral hydrate (and calcium-containing tablets), **H**eavy metals such as "
    "lead and mercury, **I**ron and iodides, **P**henothiazines and other psychotropic tablets, "
    "**E**nteric-coated tablets, and **S**olvents such as chlorinated hydrocarbons (for example carbon "
    "tetrachloride). Of the options, only **chloral hydrate** is on this list.\n\n"
    "Ethylene glycol does not show on an X-ray: its poisoning is recognised by a high anion gap metabolic "
    "acidosis, a raised osmolal gap and calcium oxalate crystals in the urine on microscopy. "
    "Phenazopyridine (which turns the urine orange-red) and chloroquine are not classic radiopaque poisons "
    "either.\n\n"
    "**Answer: (d) Chloral hydrate**"
)
RBSK = (
    "Under the **Rashtriya Bal Swasthya Karyakram (RBSK)**, children from birth to 18 years are screened "
    "for 30 conditions grouped as the '4 Ds': Defects at birth, **Deficiencies**, Diseases of childhood, "
    "and Developmental delays and disabilities.\n\n"
    "The **Deficiencies** group is: anaemia (especially severe anaemia), **vitamin A deficiency** (Bitot's "
    "spots), **vitamin D deficiency** (rickets), severe acute malnutrition and goitre. Congenital "
    "hypothyroidism is not in this group: it is one of the optional conditions (with sickle cell anaemia "
    "and beta thalassaemia) that states may add to the screening.\n\n"
    "So II (vitamin A deficiency), III (anaemia) and IV (vitamin D deficiency) are included, and I "
    "(hypothyroidism) is not.\n\n"
    "**Answer: (d) II, III and IV**"
)
APGAR_STEM = (
    "In a newborn, the Apgar score has been recorded at 1 minute of birth. The doctor recorded the "
    "following observations:\n\n"
    "Heart rate: 92 per minute\n"
    "Respiratory effort: Slow, irregular\n"
    "Muscle tone: Flaccid\n"
    "Reflex response: No response\n"
    "Colour: Body pink, extremities blue\n\n"
    "Which one of the following best reflects the Apgar score of this newborn infant on a scale of 0 to "
    "10? (2022 PYQ)"
)
APGAR_WORKING = (
    "**Scoring the observations** (each sign scores 0, 1 or 2):\n"
    "- Heart rate 92 per minute (present, below 100): 1\n"
    "- Respiratory effort slow and irregular: 1\n"
    "- Muscle tone flaccid (limp): 0\n"
    "- No reflex response: 0\n"
    "- Body pink with blue extremities: 1\n\n"
    "Total = 1 + 1 + 0 + 0 + 1 = **3**.\n\n"
    "**Answer: (c) 3**\n\n"
)

REPAIRS_2026_11_07 = (
    {
        'id': 2058, 'key': 'C', 'origin': 'ai', 'lock_explanation': True,
        'requires': {'question_text': 'bright red tongue', 'option_c': 'corn',
                     'explanation': 'wheat, especially when consumed as a staple'},
        'set': {'explanation': PELLAGRA},
        'reason': 'Content repair 2026-11-07: explanation argued for Wheat (old key B); rewritten for key C (Corn)',
    },
    {
        'id': 2065, 'key': 'C', 'origin': 'ai', 'lock_explanation': True,
        'requires': {'question_text': 'commonly affected in osteoarthritis', 'option_c': 'i, ii and iv only',
                     'explanation': 'is not typically associated with osteoarthritis'},
        'set': {'explanation': OSTEOARTHRITIS},
        'reason': 'Content repair 2026-11-07: explanation argued for I and II only (old key A); rewritten for key C',
    },
    {
        'id': 2103, 'key': 'D', 'origin': 'ai', 'lock_explanation': True,
        'requires': {'question_text': 'radiopaque density', 'option_d': 'chloral hydrate',
                     'explanation': 'ethylene glycol poisoning can cause radiopaque densities'},
        'set': {'explanation': RADIOPAQUE},
        'reason': 'Content repair 2026-11-07: explanation argued for Ethylene glycol (old key B); rewritten for key D',
    },
    {
        'id': 2113, 'key': 'D', 'origin': 'ai', 'lock_explanation': True,
        'requires': {'question_text': 'rashtriya bal swasthya', 'option_d': 'ii, iii and iv',
                     'explanation': 'vitamin d deficiency is not listed'},
        'set': {'explanation': RBSK},
        'reason': 'Content repair 2026-11-07: explanation argued for I, II and III (old key A); rewritten for key D',
    },
    {
        'id': 22462, 'key': 'C', 'origin': 'mixed',
        'requires': {'question_text': 'apgar score has been recorded at 1 minute', 'option_c': '3',
                     'explanation': 'the apgar score is taken at 1 minute'},
        'forbids': {'question_text': 'heart rate'},
        'set': {'question_text': APGAR_STEM},
        'prepend': {'explanation': APGAR_WORKING},
        'reason': 'Content repair 2026-11-07: restored the Apgar observations from the 2022 paper; worked score added',
    },
)


def _contains(value, needle: str) -> bool:
    return needle.casefold() in ' '.join(str(value or '').split()).casefold()


def refusal(question, repair) -> str:
    """Why ``repair`` must not be applied to ``question`` ('' when it may)."""
    if question is None:
        return 'missing'
    if valid_key(question.correct_answer) != repair['key']:
        return 'key changed'
    touches_explanation = 'explanation' in repair.get('set', {}) or 'explanation' in repair.get('prepend', {})
    if touches_explanation and (getattr(question, 'admin_explanation_override', '') or '').strip():
        return 'admin override'
    for field, needle in repair.get('forbids', {}).items():
        if _contains(getattr(question, field, ''), needle):
            return 'already repaired'
    for field, needle in repair.get('requires', {}).items():
        if not _contains(getattr(question, field, ''), needle):
            return f'{field} edited'
    return ''


def apply_repairs(repairs, *, question_model, snapshot_model) -> list[tuple[int, str]]:
    """Apply each repair that still fits its question; returns (question id, 'repaired' or the refusal)."""
    from questions.text_encoding import normalize_text

    results = []
    for repair in repairs:
        question = question_model.objects.filter(pk=repair['id']).first()
        reason = refusal(question, repair)
        if reason:
            results.append((repair['id'], reason))
            continue
        with transaction.atomic():
            snapshot_model.objects.create(question_id=question.pk, changed_by=None, reason=repair['reason'][:200],
                                          snapshot=revision_state(question))
            updates = {}
            for field, value in repair.get('set', {}).items():
                updates[field] = normalize_text(value)
            for field, value in repair.get('prepend', {}).items():
                updates[field] = normalize_text(value + (getattr(question, field, '') or '').strip())
            for field, value in updates.items():
                setattr(question, field, value)
            updates.update(
                explanation_for_key=repair['key'],
                explanation_stem_hash=stem_hash(question),
                explanation_status='ai_generated',
                explanation_status_reason='',
                explanation_origin=repair['origin'],
                explanation_hash=explanation_hash(question),
                updated_at=timezone.now(),
            )
            if 'lock_explanation' in repair:
                updates['lock_explanation'] = repair['lock_explanation']
            question_model.objects.filter(pk=question.pk).update(**updates)
        results.append((repair['id'], 'repaired'))
    return results


# ── Questions hidden on 2026-11-07 ─────────────────────────────────────────────────────────────────────────
# The owner's rule: a question is never hidden or deleted unless it is a duplicate or wrong. These were found by
# the figure audit and approved by the owner. Each is hidden only while it is active and still holds the stem and
# options it was judged on (stem_hash); a duplicate only while its kept copy is active with the same key. A
# QuestionRevisionSnapshot is stored first and nothing is deleted: the editor can show the question again.
HIDES_2026_11_07 = (
    {'id': 12605, 'keep': 12321,
     'stem_hash': 'ebc4b2014a1dd378d796f3dc57c6e6038bba55e5e1f0fa35601234d311e2e3bc',
     'reason': 'Hidden 2026-11-07: duplicate of #12321 (the same NEET PG 2021 question imported twice)'},
    {'id': 22456, 'keep': 6477,
     'stem_hash': 'a582399af713620e9d2c47029340f76df4be2e2d4480cf7bdf91ee93779a136f',
     'reason': 'Hidden 2026-11-07: duplicate of #6477 (CMS 2018 Paper II) that lost its data table'},
    {'id': 22631, 'keep': 2210,
     'stem_hash': '32257dfe4c5720fa65d6eca3a4d77cbd4637bf7ae28ae3df8910480306258417',
     'reason': 'Hidden 2026-11-07: duplicate of #2210 (CMS 2025 Paper II) that lost its ECG table'},
    {'id': 26454,
     'stem_hash': '3e1f72f1c06fa68b97d6469e33dab9cd76e5dad6c29693510ecb7182f2924532',
     'reason': 'Hidden 2026-11-07: seed demo question; its image file never existed ("[image unavailable]")'},
    {'id': 26451,
     'stem_hash': '7b6b4d14d59732ff00ff6fbfbf01446cc8b915c638a82807791a3e4465d1a917',
     'reason': 'Hidden 2026-11-07: seed demo question; its image file never existed ("[image unavailable]")'},
    {'id': 15370,
     'stem_hash': '8e34c9b0570425f25b8240270027db385677e2731a293168a81484f8f1fa1d58',
     'reason': 'Hidden 2026-11-07: the source book omits the lab values the question asks about'},
    {'id': 15618,
     'stem_hash': '81c84e11834af72facd3380b91a9772e1520f502ee00a289a948ee6a0201e0a1',
     'reason': 'Hidden 2026-11-07: the source book omits the list of substances the options refer to'},
)


def hide_refusal(question, item, question_model) -> str:
    """Why ``item`` must not hide ``question`` ('' when it may)."""
    if question is None:
        return 'missing'
    if not question.is_active:
        return 'already hidden'
    if stem_hash(question) != item['stem_hash']:
        return 'stem or options changed'
    keep_id = item.get('keep')
    if keep_id:
        keep = question_model.objects.filter(pk=keep_id).first()
        if keep is None or not keep.is_active:
            return 'kept copy not active'
        if valid_key(keep.correct_answer) != valid_key(question.correct_answer):
            return 'kept copy has another key'
    return ''


def apply_hides(items, *, question_model, snapshot_model) -> list[tuple[int, str]]:
    """Hide each question that still fits its item; returns (question id, 'hidden' or the refusal)."""
    results = []
    for item in items:
        question = question_model.objects.filter(pk=item['id']).first()
        reason = hide_refusal(question, item, question_model)
        if reason:
            results.append((item['id'], reason))
            continue
        with transaction.atomic():
            snapshot_model.objects.create(question_id=question.pk, changed_by=None, reason=item['reason'][:200],
                                          snapshot=revision_state(question))
            question_model.objects.filter(pk=question.pk).update(is_active=False, updated_at=timezone.now())
        results.append((item['id'], 'hidden'))
    return results
