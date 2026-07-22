"""Re-import the year-wise NEET PG PDFs using pdfplumber fallback.

Targets only the year-named papers (2018, 2020, 2021, 2022, 2023, 2025)
which have extractable text via pdfplumber but not PyMuPDF.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from pathlib import Path
from importers.neetpg.runner import process_one_pdf
from importers.neetpg.config import get_config
from questions.models import Question, QuestionImportJob
from collections import Counter

cfg = get_config()
src = Path(r'C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material')

job = QuestionImportJob.objects.create(
    job_type='pdf',
    status='running',
    source_filename='year_wise_papers',
    stored_file_path=str(src),
    summary={'triggered_via': 'import_year_wise.py', 'phase': 'pdfplumber fallback'},
)

year_files = [
    'NEET-PG-Question-Paper-2018-PDF-With-Solutions.pdf',
    'NEET-PG-Question-Paper-2020-With-Solutions.pdf',
    'NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf',
    'NEET-PG-2022-Question-Paper-With-Solutions.pdf',
    'NEET-PG-2023-Question-Paper-With-Solutions-PDF-1.pdf',
    'neet-pg-2025-question-paper-pdf-aug-03-2025-1781083284.pdf',
]

before = Question.objects.filter(exam_type='neet_pg', is_active=True).count()
print(f'NEET PG questions before: {before}\n')

for fname in year_files:
    p = src / fname
    if not p.exists():
        print(f'  SKIP (missing): {fname}')
        continue
    print(f'>>> {fname}')
    try:
        result = process_one_pdf(p, cfg, import_job_id=job.id, force=True)
        print(f'    questions={result.get("question_count", 0)}  images={result.get("image_count", 0)}  time={result.get("elapsed_seconds", 0):.1f}s')
    except Exception as e:
        print(f'    ERR: {type(e).__name__}: {e}')

after = Question.objects.filter(exam_type='neet_pg', is_active=True).count()
print(f'\nNEET PG questions after: {after}')
print(f'Delta: {after - before}')

# Per-year counts
yc = Counter()
for y in Question.objects.filter(exam_type='neet_pg', is_active=True).values_list('year', flat=True):
    yc[y] += 1
print(f'\nBy year:')
for y, c in sorted(yc.items()):
    print(f'  {y}: {c}')

job.status = 'completed'
job.summary = dict(job.summary or {}, completed=True, before=before, after=after)
job.save(update_fields=['status', 'summary'])
