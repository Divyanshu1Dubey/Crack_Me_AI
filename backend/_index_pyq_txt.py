"""Quick script to index all PYQ .txt files into the RAG store."""
import os, sys, re, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from ai_engine.rag_pipeline import RAGPipeline
from pathlib import Path

rag = RAGPipeline()
pyq_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Medura_Train', 'PYQ')

# Only process .txt files
txt_files = sorted([f for f in os.listdir(pyq_dir) if f.endswith('.txt')])
print(f'Found {len(txt_files)} TXT files to index:')
for f in txt_files:
    print(f'  - {f}')

total = 0
for f in txt_files:
    filepath = os.path.join(pyq_dir, f)
    stem = Path(f).stem
    m = re.match(r'(\d{4})paper(\d)', stem)
    if m:
        year, paper = m.groups()
        book_name = f'CMS PYQ {year} Paper {paper}'
    else:
        book_name = stem

    print(f'\nIndexing: {f} -> "{book_name}"')
    chunks = rag.index_textbook(filepath, book_name, chunk_size=500, overlap=50, skip_idf_rebuild=True)
    print(f'  -> {chunks} new chunks')
    total += chunks

# Rebuild IDF once at end
if total > 0:
    print(f'\nRebuilding IDF cache...')
    rag._rebuild_idf()

print(f'\n=== DONE: {total} total new chunks indexed ===')

# Show updated stats
stats = rag.get_stats()
print(f'Total chunks in store: {stats["total_chunks"]}')
pyq_books = {k: v for k, v in stats.get('books', {}).items() if 'PYQ' in k or 'Paper' in k or 'pyq' in k.lower()}
print(f'\nPYQ-related entries:')
for book, count in sorted(pyq_books.items()):
    print(f'  {book}: {count} chunks')
