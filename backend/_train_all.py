"""
Full training script: indexes ALL documents in Medura_Train into the RAG knowledge base.
Run: python _train_all.py
Memory-optimized: defers IDF rebuild, uses gc.collect() after each file.
"""
import os
import re
import sys
import gc

import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
django.setup()

from ai_engine.rag_pipeline import RAGPipeline  # noqa: E402
from pathlib import Path  # noqa: E402

MEDURA = Path(__file__).resolve().parent / 'Medura_Train'

# Max PDF size: 50 MB — larger PDFs (full textbooks) are skipped since .md notes exist
MAX_PDF_SIZE_MB = 50

# Book name mapping for cleaner display
NAME_MAP = {
    'ghai_pediatrics_cms_notes': 'Ghai Essential Pediatrics (Notes)',
    'harrisons_medicine_cms_notes': "Harrison's Medicine (Notes)",
    'parks_psm_cms_notes': "Park's PSM (Notes)",
    'surgery_obg_cms_notes': 'Surgery & OBG (Notes)',
    'cms_pyq_database_2018_2024': 'CMS PYQ Database 2018-2024',
    'standard_student_doubts': 'Common Student Doubts & Answers',
    'upsc_cms_complete_syllabus': 'UPSC CMS Complete Syllabus',
    'wiki_cms_overview': 'CMS Exam Overview (Wiki)',
    # New comprehensive notes
    'anatomy_cms_notes': 'Anatomy (Comprehensive CMS Notes)',
    'physiology_cms_notes': 'Physiology (Comprehensive CMS Notes)',
    'biochemistry_cms_notes': 'Biochemistry (Comprehensive CMS Notes)',
    'ent_cms_notes': 'ENT (Comprehensive CMS Notes)',
    'ophthalmology_cms_notes': 'Ophthalmology (Comprehensive CMS Notes)',
    'dermatology_cms_notes': 'Dermatology (Comprehensive CMS Notes)',
    'psychiatry_cms_notes': 'Psychiatry (Comprehensive CMS Notes)',
    'anesthesia_cms_notes': 'Anesthesia (Comprehensive CMS Notes)',
    'radiology_cms_notes': 'Radiology (Comprehensive CMS Notes)',
    'pathology_cms_notes': 'Pathology (Comprehensive CMS Notes)',
    'forensic_medicine_extended_cms_notes': 'Forensic Medicine Extended (CMS Notes)',
    'microbiology_extended_cms_notes': 'Microbiology Extended (CMS Notes)',
    'pharmacology_extended_cms_notes': 'Pharmacology Extended (CMS Notes)',
}

def clean_name(filepath):
    stem = Path(filepath).stem
    # Check name map first
    if stem in NAME_MAP:
        return NAME_MAP[stem]
    # Handle "Copy of" prefix
    name = stem
    if name.startswith('Copy of '):
        name = name[8:]
    # Remove UUID suffix
    name = re.sub(r'_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', '', name)
    name = re.sub(r'\(\d+\)$', '', name).strip()
    return name

def progress(current, total, book):
    pct = int(current / total * 100) if total else 0
    sys.stdout.write(f'\r  [{pct:3d}%] {book}: page {current}/{total}')
    sys.stdout.flush()

def main():
    rag = RAGPipeline()

    # Show current stats
    stats = rag.get_stats()
    print(f"Current RAG state: {stats['total_chunks']} chunks from {len(stats.get('books', {}))} books")
    print()

    # Collect ALL indexable files
    files_to_index = []
    skipped = []

    def should_skip(filepath):
        """Skip 'Copy of' duplicates, oversized PDFs, and hidden files."""
        name = filepath.name
        if name.startswith('.') or name.startswith('Copy of'):
            return f"duplicate/hidden: {name}"
        if filepath.suffix.lower() == '.pdf':
            size_mb = filepath.stat().st_size / (1024 * 1024)
            if size_mb > MAX_PDF_SIZE_MB:
                return f"too large ({size_mb:.0f} MB): {name}"
        return None

    # 1. Textbook PDFs
    textbook_dir = MEDURA / 'textbooks'
    if textbook_dir.exists():
        for f in sorted(textbook_dir.iterdir()):
            if f.suffix.lower() in ('.pdf', '.md', '.txt'):
                reason = should_skip(f)
                if reason:
                    skipped.append(reason)
                    continue
                files_to_index.append((str(f), clean_name(f), 'textbook'))

    # 2. PYQ files
    pyq_dir = MEDURA / 'PYQ'
    if pyq_dir.exists():
        for f in sorted(pyq_dir.iterdir()):
            if f.suffix.lower() in ('.pdf', '.md', '.txt'):
                reason = should_skip(f)
                if reason:
                    skipped.append(reason)
                    continue
                files_to_index.append((str(f), clean_name(f), 'pyq'))

    # 3. Web knowledge
    web_dir = MEDURA / 'web_knowledge'
    if web_dir.exists():
        for f in sorted(web_dir.iterdir()):
            if f.suffix.lower() in ('.md', '.txt'):
                reason = should_skip(f)
                if reason:
                    skipped.append(reason)
                    continue
                files_to_index.append((str(f), clean_name(f), 'web'))

    # 4. Root PDFs (exam docs, syllabi etc. — skip form/certificate PDFs)
    skip_keywords = ['affidavit', 'performa', 'proforma', 'disability', 'obc',
                     'sc-st', 'ews', 'travelling', 'daf', 'form notice',
                     'time table', 'copy of upsc', 'copy of performa',
                     'copy of proforma', 'copy of disability', 'copy of travelling',
                     'copy of instructions', 'copy of affidavit']
    for f in sorted(MEDURA.iterdir()):
        if f.is_file() and f.suffix.lower() in ('.pdf', '.md', '.txt'):
            name_lower = f.stem.lower()
            if any(kw in name_lower for kw in skip_keywords):
                skipped.append(f"form/cert: {f.name}")
                continue
            reason = should_skip(f)
            if reason:
                skipped.append(reason)
                continue
            files_to_index.append((str(f), clean_name(f), 'root'))

    if skipped:
        print(f"Skipped {len(skipped)} files (duplicates/oversized):")
        for reason in skipped:
            print(f"  - SKIP: {reason}")
        print()

    print(f"Found {len(files_to_index)} files to index:\n")
    for path, name, cat in files_to_index:
        print(f"  [{cat:8s}] {name}")
    print()

    total_new_chunks = 0
    for i, (path, name, cat) in enumerate(files_to_index, 1):
        print(f"\n[{i}/{len(files_to_index)}] Indexing: {name}")
        try:
            # skip_idf_rebuild=True → defer to one IDF rebuild at the end
            chunks = rag.index_textbook(path, name, progress_callback=progress,
                                        skip_idf_rebuild=True)
            if chunks > 0:
                total_new_chunks += chunks
                print(f'\n  [OK] Added {chunks} new chunks')
            else:
                print(f'\n  [--] Already indexed or no extractable text')
        except Exception as e:
            print(f'\n  [ERR] Error: {e}')
        # Free memory between files
        gc.collect()

    # Single IDF rebuild at the end (memory-efficient)
    if total_new_chunks > 0:
        print("\nRebuilding IDF index...")
        rag._rebuild_idf()
        print("[OK] IDF index rebuilt")

    print(f"\n{'='*60}")
    print("Training complete!")
    print(f"New chunks added: {total_new_chunks}")
    stats = rag.get_stats()
    print(f"Total chunks in knowledge base: {stats['total_chunks']}")
    print(f"Books indexed: {len(stats.get('books', {}))}")
    for book, count in sorted(stats.get('books', {}).items(), key=lambda x: -x[1]):
        print(f"  - {book}: {count} chunks")
    rag.close()

if __name__ == '__main__':
    main()



