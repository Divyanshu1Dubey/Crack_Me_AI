"""
Master training command — indexes ALL knowledge into ChromaDB.
Scans Medura_Train for textbooks, PYQs, web knowledge, and any new files.
Supports auto-detection of new content and incremental re-indexing.

Usage:
    python manage.py train_ai                # Full training (all data)
    python manage.py train_ai --stats        # Show current stats
    python manage.py train_ai --force        # Force re-index everything
    python manage.py train_ai --dir /path    # Index a specific directory
"""
import os
import time
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Train AI: index ALL Medura_Train data into ChromaDB for RAG"

    def add_arguments(self, parser):
        parser.add_argument("--stats", action="store_true", help="Show current index stats only")
        parser.add_argument("--force", action="store_true", help="Force re-index all documents")
        parser.add_argument("--dir", type=str, help="Index a specific directory")
        parser.add_argument("--chunk-size", type=int, default=500, help="Chunk size for splitting")
        parser.add_argument("--overlap", type=int, default=50, help="Overlap between chunks")

    def handle(self, *args, **options):
        from ai_engine.rag_pipeline import RAGPipeline

        self.stdout.write(self.style.WARNING("\n" + "=" * 60))
        self.stdout.write(self.style.WARNING("  CRACK CMS — AI Training Pipeline"))
        self.stdout.write(self.style.WARNING("=" * 60))

        rag = RAGPipeline()

        if options["stats"]:
            self._show_stats(rag)
            return

        if options["force"]:
            self.stdout.write(self.style.WARNING("\n⚠️  Force re-index: clearing existing data..."))
            try:
                rag._conn.execute("DELETE FROM chunks")
                rag._conn.execute("DELETE FROM idf_cache")
                rag._conn.commit()
                self.stdout.write(self.style.SUCCESS("  ✓ Database cleared"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Clear failed: {e}"))

        start_time = time.time()
        total_chunks = 0
        results = {}

        # Determine directories to scan
        train_dir = options.get("dir") or str(settings.MEDURA_TRAIN_DIR)
        chunk_size = options["chunk_size"]
        overlap = options["overlap"]

        if not os.path.exists(train_dir):
            self.stdout.write(self.style.ERROR(f"\n✗ Training directory not found: {train_dir}"))
            return

        # Scan ALL subdirectories recursively
        scan_dirs = {
            "textbooks": os.path.join(train_dir, "textbooks"),
            "PYQ": os.path.join(train_dir, "PYQ"),
            "web_knowledge": os.path.join(train_dir, "web_knowledge"),
        }

        # Also add any custom directories at root level
        for item in os.listdir(train_dir):
            item_path = os.path.join(train_dir, item)
            if os.path.isdir(item_path) and item not in scan_dirs:
                scan_dirs[item] = item_path

        # Also check root-level files
        scan_dirs["_root"] = train_dir

        for category, dir_path in scan_dirs.items():
            if not os.path.exists(dir_path):
                continue

            self.stdout.write(self.style.HTTP_INFO(f"\n📂 Scanning: {category}/"))

            files_to_index = []
            if os.path.isdir(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    for f in files:
                        ext = Path(f).suffix.lower()
                        if ext in ['.md', '.txt', '.pdf']:
                            files_to_index.append(os.path.join(root, f))
            elif os.path.isfile(dir_path):
                files_to_index.append(dir_path)

            for file_path in files_to_index:
                filename = Path(file_path).name
                book_name = self._clean_name(filename, category)

                self.stdout.write(f"  📄 Indexing: {filename} → '{book_name}'")

                def progress_cb(current, total, name):
                    if total > 0:
                        pct = int(current / total * 100)
                        self.stdout.write(f"    Progress: {pct}% ({current}/{total} pages)", ending='\r')
                        self.stdout.flush()

                try:
                    chunks = rag.index_textbook(
                        file_path, book_name,
                        chunk_size=chunk_size,
                        overlap=overlap,
                        progress_callback=progress_cb
                    )
                    results[book_name] = chunks
                    total_chunks += chunks
                    status = "✓ new" if chunks > 0 else "⊘ already indexed"
                    self.stdout.write(f"    {status}: {chunks} chunks")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    ✗ Error: {e}"))
                    results[book_name] = -1

        elapsed = time.time() - start_time

        # Summary
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("  TRAINING COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"\n  ⏱  Time: {elapsed:.1f}s")
        self.stdout.write(f"  📊 New chunks indexed: {total_chunks}")
        self._show_stats(rag)

        self.stdout.write(self.style.SUCCESS("\n  ✅ AI is now trained with all available data!"))
        self.stdout.write(self.style.SUCCESS("  💡 Add new files to Medura_Train/ and re-run to update.\n"))

    def _show_stats(self, rag):
        stats = rag.get_stats()
        self.stdout.write(f"\n  📊 Total chunks in store: {stats['total_chunks']}")
        self.stdout.write(f"  📁 Collection: {stats['collection_name']}")

        books = stats.get("books", {})
        if books:
            self.stdout.write("\n  📚 Books indexed:")
            for book, count in sorted(books.items(), key=lambda x: -x[1]):
                self.stdout.write(f"      • {book}: {count} chunks")

    def _clean_name(self, filename, category):
        """Create a clean book name from filename."""
        name = Path(filename).stem
        # Map known files to standard names
        name_map = {
            "harrisons_medicine_cms_notes": "Harrison's Medicine",
            "ghai_pediatrics_cms_notes": "Ghai Pediatrics",
            "parks_psm_cms_notes": "Park's PSM",
            "surgery_obg_cms_notes": "Surgery & OBG (Bailey/Dutta)",
            "cms_pyq_database_2018_2024": "UPSC CMS PYQ Database 2018-2024",
            "upsc_cms_complete_syllabus": "UPSC CMS Complete Syllabus",
            "standard_student_doubts": "CMS Student Doubts & FAQ",
            "wiki_cms_overview": "CMS Wikipedia Overview",
        }
        if name in name_map:
            return name_map[name]
        # Generic cleanup
        name = name.replace('_', ' ').replace('-', ' ').title()
        if category != "_root":
            name = f"{name} ({category})"
        return name
