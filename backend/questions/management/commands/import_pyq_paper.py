"""Import a previous-year paper from a ``pyq-paper/1`` file (e.g. ``fixtures/pyq/cms_2026.json``).

    python manage.py import_pyq_paper fixtures/pyq/cms_2026.json            # dry run: the plan only
    python manage.py import_pyq_paper fixtures/pyq/cms_2026.json --apply    # write

Each question of the file is
  * skipped as already imported when the bank has a question of the same exam, year, paper and number
    (``display_number``), so a second run changes nothing;
  * skipped when an admin removed that stem (``questions.import_protection.is_removed``);
  * otherwise created with the file's subject, topic (an existing topic of that subject with the same
    name, case-insensitively, or a new one), number and key. No explanation is written. A paper is
    imported whole (the year simulator needs every question): when the bank already has the same stem
    and options under another label (an "Expert Curated" copy, another year's paper), the question is
    still created and those ids are listed, for the admin duplicate tool.

A question marked ``needs_figure`` (its stem says a figure is shown, and the file has no figure) is created
hidden (``is_active=False``, ``needs_review``, ``is_image_based``) until an admin adds the figure from the
official paper and activates it in the questions editor; the command lists them.

The key a source prints is a secondary-source signal, never a verified key: each created question gets a
``key_audit.SourceKey`` row for it (``inline_answer``, located, same option order) and the key audit runs
for the created questions, which sets ``answer_key_status``. Subjects must already exist (by code).
Prints counts and question ids only.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from questions.content_hashes import stem_hash
from questions.import_protection import is_removed
from questions.models import Question, Subject, Topic

FORMAT = 'pyq-paper/1'
RECOVERY_VERSION = 'pyq-paper-import/1'
OPTION_FIELDS = ('option_a', 'option_b', 'option_c', 'option_d')
SOURCE_EXAM_LABELS = {'cms': 'CMS', 'neet_pg': 'NEET PG', 'ini_cet': 'INI-CET', 'fmge': 'FMGE', 'usmle': 'USMLE'}


def load_paper(path) -> dict:
    """The validated file, or CommandError naming the first problems."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise CommandError(f'Cannot read {path}: {exc}') from exc
    problems = []
    if data.get('format') != FORMAT:
        problems.append(f"format must be {FORMAT!r}")
    exam_types = {choice for choice, _ in Question._meta.get_field('exam_type').choices}
    if data.get('exam_type') not in exam_types:
        problems.append(f"exam_type must be one of {sorted(exam_types)}")
    if not isinstance(data.get('year'), int) or not 1990 <= data['year'] <= 2100:
        problems.append('year must be a year')
    sources = data.get('sources') or {}
    seen = set()
    for index, q in enumerate(data.get('questions') or []):
        where = f"question #{index + 1} (paper {q.get('paper')}, no. {q.get('number')})"
        if str(q.get('paper')) not in sources:
            problems.append(f'{where}: paper has no entry in sources')
        if not isinstance(q.get('number'), int) or q['number'] < 1:
            problems.append(f'{where}: number must be a positive integer')
        if (q.get('paper'), q.get('number')) in seen:
            problems.append(f'{where}: number repeated')
        seen.add((q.get('paper'), q.get('number')))
        if not (q.get('question_text') or '').strip():
            problems.append(f'{where}: empty stem')
        if any(not (q.get(f) or '').strip() for f in OPTION_FIELDS):
            problems.append(f'{where}: an option is empty')
        if q.get('correct_answer') not in ('A', 'B', 'C', 'D'):
            problems.append(f'{where}: correct_answer must be A-D')
        if not q.get('subject_code'):
            problems.append(f'{where}: subject_code missing')
    if not data.get('questions'):
        problems.append('no questions')
    if problems:
        raise CommandError('Invalid paper file:\n  ' + '\n  '.join(problems[:12]))
    return data


def plan_import(data) -> dict:
    """What an import would do: per question (paper, number) -> (action, detail). Reads only."""
    exam_type, year = data['exam_type'], data['year']
    codes = {q['subject_code'] for q in data['questions']}
    subjects = {s.code: s for s in Subject.objects.filter(code__in=codes)}
    missing = sorted(codes - set(subjects))
    if missing:
        raise CommandError(f'Subjects missing in this database (codes): {", ".join(missing)}')
    imported = set(Question.objects.filter(exam_type=exam_type, year=year)
                   .values_list('paper', 'display_number'))
    by_hash = {}
    for row in (Question.objects.filter(exam_type=exam_type)
                .only('id', 'question_text', *OPTION_FIELDS).iterator(chunk_size=2000)):
        by_hash.setdefault(stem_hash(row), []).append(row.id)
    actions = {}
    for q in data['questions']:
        key = (q['paper'], q['number'])
        if key in imported:
            actions[key] = ('already_imported', [])
        elif is_removed(q['question_text']):
            actions[key] = ('removed', [])
        else:
            actions[key] = ('create', by_hash.get(stem_hash(q), []))
    return {'subjects': subjects, 'actions': actions}


def _topic_for(subject, name, cache):
    name = (name or '').strip()[:200] or 'General'
    key = (subject.pk, name.lower())
    if key not in cache:
        topic = Topic.objects.filter(subject=subject, name__iexact=name).first()
        if topic is None:
            topic = Topic.objects.create(subject=subject, name=name, importance=5,
                                         description=f'{name} ({subject.name})')
        cache[key] = topic
    return cache[key]


def apply_import(data, plan) -> list:
    """Create the planned questions with their SourceKey rows (one transaction). Returns them."""
    from key_audit.models import SourceKey

    now = timezone.now()
    exam_type, year = data['exam_type'], data['year']
    created, topics = [], {}
    with transaction.atomic():
        for q in data['questions']:
            if plan['actions'][(q['paper'], q['number'])][0] != 'create':
                continue
            subject = plan['subjects'][q['subject_code']]
            source = data['sources'][str(q['paper'])]
            needs_figure = bool(q.get('needs_figure'))
            question = Question.objects.create(
                is_active=not needs_figure,
                needs_review=needs_figure,
                is_image_based=needs_figure,
                exam_type=exam_type,
                exam_source=data.get('exam_source') or 'UPSC CMS',
                year=year,
                paper=q['paper'],
                display_number=q['number'],
                question_text=q['question_text'],
                option_a=q['option_a'], option_b=q['option_b'],
                option_c=q['option_c'], option_d=q['option_d'],
                correct_answer=q['correct_answer'],
                subject=subject,
                topic=_topic_for(subject, q.get('topic'), topics),
                difficulty='medium',
                source=source['file'][:200],
            )
            SourceKey.objects.create(
                question=question,
                source_file=source['file'][:255],
                source_sha256=source.get('sha256', ''),
                question_page=q.get('page') or 1,
                question_number=q['number'],
                answer_page=q.get('page') or None,
                chapter=(q.get('chapter') or '')[:160],
                source_exam=SOURCE_EXAM_LABELS.get(exam_type, exam_type.upper())[:16],
                source_year=year,
                printed_letter=q['correct_answer'],
                letter=q['correct_answer'],
                option_order='same',
                method='inline_answer',
                located=True,
                stem_hash=stem_hash(question),
                recovery_version=RECOVERY_VERSION,
                recovered_at=now,
            )
            created.append(question)
    return created


class Command(BaseCommand):
    help = 'Import a previous-year paper from a pyq-paper/1 JSON file (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('file', help='path to the paper file, e.g. fixtures/pyq/cms_2026.json')
        parser.add_argument('--apply', action='store_true', help='write (default: report the plan only)')

    def handle(self, *args, **options):
        data = load_paper(options['file'])
        plan = plan_import(data)
        counts = Counter(action for action, _ in plan['actions'].values())
        per_subject = Counter(q['subject_code'] for q in data['questions']
                              if plan['actions'][(q['paper'], q['number'])][0] == 'create')
        also = {k: ids for k, (action, ids) in plan['actions'].items() if action == 'create' and ids}
        self.stdout.write(
            f"{data['exam_source']} {data['year']}: {len(data['questions'])} questions in the file | "
            f"to create {counts['create']} | already imported {counts['already_imported']} | "
            f"removed by an admin {counts['removed']} | also in the bank under another label {len(also)}")
        if per_subject:
            self.stdout.write('  to create by subject: ' + ', '.join(f'{c} {n}' for c, n in sorted(per_subject.items())))
        for (paper, number), ids in sorted(also.items()):
            self.stdout.write(f'  paper {paper} no. {number}: same stem and options as question(s) '
                              f'{", ".join(map(str, ids[:5]))}')
        for (paper, number), (action, _) in sorted(plan['actions'].items()):
            if action == 'removed':
                self.stdout.write(f'  paper {paper} no. {number}: removed by an admin (not imported)')
        hidden = [(q['paper'], q['number']) for q in data['questions'] if q.get('needs_figure')
                  and plan['actions'][(q['paper'], q['number'])][0] == 'create']
        if hidden:
            self.stdout.write(f'  {len(hidden)} need their figure from the official paper and are created hidden: '
                              + ', '.join(f'P{p} Q{n}' for p, n in hidden))
        if not options['apply']:
            self.stdout.write(self.style.WARNING('Dry run: nothing written. Run again with --apply.'))
            return
        created = apply_import(data, plan)
        self.stdout.write(self.style.SUCCESS(
            f'Created {len(created)} questions (ids {created[0].pk}-{created[-1].pk}) with their source keys.'
            if created else 'Nothing to create.'))
        if created:
            try:
                from key_audit.services import audit_questions
                prepared = audit_questions(Question.objects.filter(pk__in=[q.pk for q in created]), save=True)
                statuses = Counter(p.result.status for p in prepared)
                self.stdout.write('  answer-key audit: ' + ', '.join(f'{s} {n}' for s, n in sorted(statuses.items())))
            except Exception as exc:  # noqa: BLE001 - the import stands; the audit can be rerun
                self.stdout.write(self.style.WARNING(
                    f'  answer-key audit not run ({type(exc).__name__}); run: manage.py audit_answer_keys --apply'))
