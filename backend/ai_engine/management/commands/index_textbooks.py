"""
Django management command to index textbook PDFs into ChromaDB for RAG.
Usage: python manage.py index_textbooks [--test] [--book BOOK_NAME]
"""
import os
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from ai_engine.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Index textbook PDFs into ChromaDB for RAG-powered search"

    def add_arguments(self, parser):
        parser.add_argument("--test", action="store_true",
                            help="Only index first 10 pages of each textbook")
        parser.add_argument("--book", type=str,
                            help="Only index a specific book (by filename substring)")
        parser.add_argument("--dir", type=str,
                            help="Custom textbooks directory path")
        parser.add_argument("--stats", action="store_true",
                            help="Show current index statistics only")

    def handle(self, *args, **options):
        rag = RAGPipeline()

        if options["stats"]:
            stats = rag.get_stats()
            self.stdout.write(self.style.SUCCESS(
                f"\n📊 ChromaDB Stats: {stats['total_chunks']} chunks indexed"
            ))
            return

        # Find textbook directories
        train_dir = options.get("dir") or str(settings.MEDURA_TRAIN_DIR)
        textbook_dirs = []

        # Check textbooks subdirectory
        tb_dir = os.path.join(train_dir, "textbooks")
        if os.path.exists(tb_dir):
            textbook_dirs.append(tb_dir)

        # Check root-level textbook PDFs
        if os.path.exists(train_dir):
            root_pdfs = [
                f for f in os.listdir(train_dir)
                if f.endswith('.pdf') and not f.startswith('Copy of')
                and any(kw in f.lower() for kw in ['harrison', 'ghai', 'nelson', 'park', 'textbook'])
            ]
            if root_pdfs:
                textbook_dirs.append(train_dir)

        if not textbook_dirs:
            self.stderr.write(self.style.ERROR("No textbook directories found"))
            return

        # Collect all PDF files
        all_pdfs = []
        for dir_path in textbook_dirs:
            for f in os.listdir(dir_path):
                if f.endswith('.pdf') and not f.startswith('Copy of'):
                    if options.get("book"):
                        if options["book"].lower() not in f.lower():
                            continue
                    full_path = os.path.join(dir_path, f)
                    all_pdfs.append((full_path, f))

        if not all_pdfs:
            self.stderr.write(self.style.ERROR("No PDF files found to index"))
            return

        self.stdout.write(self.style.SUCCESS(f"\n📚 Found {len(all_pdfs)} textbooks to index:"))
        for _, name in all_pdfs:
            size_mb = os.path.getsize(os.path.join(os.path.dirname(all_pdfs[0][0]), name)) / 1048576
            self.stdout.write(f"  • {name} ({size_mb:.1f} MB)")

        total_chunks = 0
        test_mode = options.get("test", False)

        for pdf_path, pdf_name in all_pdfs:
            book_name = self._clean_name(pdf_name)
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(self.style.HTTP_INFO(f"Indexing: {book_name}"))

            def progress(current, total, name):
                if current % 50 == 0 or current == total:
                    pct = (current / total) * 100
                    self.stdout.write(f"  📖 {name}: {current}/{total} pages ({pct:.0f}%)")

            try:
                if test_mode:
                    # Only index first 10 pages
                    from ai_engine.pdf_processor import PDFProcessor
                    processor = PDFProcessor()
                    pages = processor.extract_text(pdf_path, end_page=10)
                    if pages:
                        self.stdout.write(f"  [TEST MODE] First {len(pages)} pages extracted")
                        chunks = rag.index_textbook(
                            pdf_path, book_name,
                            progress_callback=progress
                        )
                        total_chunks += chunks
                        self.stdout.write(self.style.SUCCESS(f"  ✅ Indexed {chunks} chunks"))
                else:
                    chunks = rag.index_textbook(
                        pdf_path, book_name,
                        progress_callback=progress
                    )
                    total_chunks += chunks
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Indexed {chunks} chunks"))

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  ❌ Error: {e}"))
                logger.exception(f"Failed to index {pdf_name}")

        # Summary
        stats = rag.get_stats()
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(
            f"\n📊 Indexing Complete:"
            f"\n  New chunks added: {total_chunks}"
            f"\n  Total chunks in DB: {stats['total_chunks']}"
            f"\n  Mode: {'TEST' if test_mode else 'FULL'}"
        ))

    def _clean_name(self, filename: str) -> str:
        """Clean up filename to book name."""
        name = Path(filename).stem
        # Remove UUID suffixes
        parts = name.split('_')
        if len(parts) > 1 and len(parts[-1]) > 20:
            name = '_'.join(parts[:-1])
        name = name.replace("Copy of ", "")
        return name.strip()
