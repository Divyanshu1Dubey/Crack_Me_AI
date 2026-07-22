"""One-shot: remap NEET PG subjects using the topic_mapper output.

Existing Question rows still have subject='General Medicine' (the
fallback before the db_writer fix). Apply the same _subject_row_for
mapping using the `source` filename so each PDF gets its proper
subject (e.g. 'Anatomy pyqs.pdf' -> 'Anatomy').

Bulk update path: build a {Question.id: Subject.id} map, then use
`Question.objects.filter(id__in=...).update(subject_id=...)` in
batches — ~100x faster than per-row save().
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from collections import Counter, defaultdict

from importers.neetpg.topic_mapper import FILENAME_SUBJECT_HINTS
from importers.neetpg.db_writer import DjangoWriter
from questions.models import Question, Subject

DEFAULT_MAP = DjangoWriter._SUBJECT_NAME_MAP


def resolve_subject(name):
    if not name:
        return None
    norm = name.strip().lower()
    target = DEFAULT_MAP.get(norm, name.strip())
    for s in Subject.objects.all():
        if s.name.lower() == target.lower():
            return s
    for s in Subject.objects.all():
        if target.lower() in s.name.lower() or s.name.lower() in target.lower():
            return s
    return None


def main():
    # Build {source_filename: inferred subject string} from hints.
    by_source: dict[str, str] = {}
    for q in Question.objects.filter(exam_type='neet_pg', is_active=True).values_list('source', flat=True).distinct():
        src = (q or '').lower()
        for hint, subject_name in FILENAME_SUBJECT_HINTS.items():
            if hint in src:
                by_source[q] = subject_name
                break

    print(f'Distinct NEET PG source filenames: {len(by_source)}')
    print('Source -> inferred subject:')
    for src, s in sorted(by_source.items()):
        print(f'  {s!r:35s}  {src}')

    # Build {source: subject_id}
    src_to_subj_id: dict[str, int] = {}
    for src, name in by_source.items():
        subj = resolve_subject(name)
        if subj:
            src_to_subj_id[src] = subj.id
    print(f'\nResolved source -> Subject.id: {len(src_to_subj_id)}')

    # Group Question IDs by target subject_id for bulk update.
    subj_to_qids: dict[int, list[int]] = defaultdict(list)
    unmapped_sources: set[str] = set()
    for q in Question.objects.filter(exam_type='neet_pg', is_active=True).values_list('id', 'source', 'subject_id'):
        qid, src, current_sid = q
        target = src_to_subj_id.get(src or '')
        if not target:
            unmapped_sources.add(src)
            continue
        if target != current_sid:
            subj_to_qids[target].append(qid)
    print(f'\nUnmapped sources (will be left as-is): {sorted(unmapped_sources)}')

    # Bulk update each bucket.
    total_fixed = 0
    for sid, qids in subj_to_qids.items():
        n = Question.objects.filter(id__in=qids).update(subject_id=sid)
        total_fixed += n
        print(f'  Subject_id={sid}: updated {n} questions')
    print(f'\nTotal questions remapped: {total_fixed}')

    sub_counter = Counter()
    for q in Question.objects.filter(exam_type='neet_pg', is_active=True).select_related('subject'):
        sub_counter[q.subject.name if q.subject else 'NO_SUBJECT'] += 1
    print('\nSubjects after backfill:')
    for sub, cnt in sub_counter.most_common(20):
        print(f'  {cnt:5}  {sub}')


if __name__ == '__main__':
    main()
