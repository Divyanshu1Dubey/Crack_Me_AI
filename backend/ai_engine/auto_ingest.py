"""
Auto-Ingest Service: Automatically adds uploaded PDFs, folders, or files
to the AI knowledge base (ChromaDB).
Monitors Medura_Train directory for new files and indexes them.
"""
import os
import logging
import hashlib
from pathlib import Path
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class AutoIngestService:
    """
    Handles automatic ingestion of new files into the RAG knowledge base.
    Call ingest_file() or ingest_directory() to add content to AI memory.
    """

    # Track indexed files to avoid re-processing
    _index_log_path = None

    def __init__(self):
        self._index_log_path = os.path.join(
            str(settings.BASE_DIR), 'chroma_db', '.index_log'
        )

    def _get_indexed_files(self) -> set:
        """Get set of already-indexed file hashes."""
        if os.path.exists(self._index_log_path):
            with open(self._index_log_path, 'r') as f:
                return set(line.strip() for line in f.readlines())
        return set()

    def _mark_indexed(self, file_hash: str):
        """Mark a file as indexed."""
        os.makedirs(os.path.dirname(self._index_log_path), exist_ok=True)
        with open(self._index_log_path, 'a') as f:
            f.write(f"{file_hash}\n")

    def _file_hash(self, file_path: str) -> str:
        """Get a hash of file path + modification time."""
        stat = os.stat(file_path)
        key = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(key.encode()).hexdigest()

    def ingest_file(self, file_path: str, book_name: Optional[str] = None,
                    force: bool = False) -> dict:
        """
        Ingest a single file into the AI knowledge base.
        Returns dict with status and chunk count.
        """
        from ai_engine.rag_pipeline import RAGPipeline

        if not os.path.exists(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}

        ext = Path(file_path).suffix.lower()
        if ext not in ['.pdf', '.md', '.txt']:
            return {"status": "error", "message": f"Unsupported file type: {ext}. Use PDF, MD, or TXT."}

        # Check if already indexed
        file_hash = self._file_hash(file_path)
        if not force and file_hash in self._get_indexed_files():
            return {"status": "skipped", "message": "File already indexed", "chunks": 0}

        # Index the file
        rag = RAGPipeline()
        book_name = book_name or self._auto_name(file_path)

        try:
            chunks = rag.index_textbook(file_path, book_name)
            self._mark_indexed(file_hash)
            logger.info(f"Auto-ingested: {book_name} ({chunks} chunks)")
            return {
                "status": "success",
                "book_name": book_name,
                "chunks": chunks,
                "message": f"Successfully indexed {chunks} chunks from '{book_name}'"
            }
        except Exception as e:
            logger.error(f"Auto-ingest failed for {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    def ingest_directory(self, dir_path: str, force: bool = False) -> dict:
        """
        Ingest all supported files in a directory into AI knowledge base.
        Recursively scans for PDF, MD, TXT files.
        """
        if not os.path.exists(dir_path):
            return {"status": "error", "message": f"Directory not found: {dir_path}"}

        results = {}
        total_chunks = 0
        files_processed = 0

        for root, dirs, files in os.walk(dir_path):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in ['.pdf', '.md', '.txt']:
                    file_path = os.path.join(root, f)
                    result = self.ingest_file(file_path, force=force)
                    results[f] = result
                    if result["status"] == "success":
                        total_chunks += result.get("chunks", 0)
                        files_processed += 1

        return {
            "status": "success",
            "files_processed": files_processed,
            "total_chunks": total_chunks,
            "details": results,
        }

    def ingest_uploaded_file(self, uploaded_file, book_name: Optional[str] = None) -> dict:
        """
        Ingest an uploaded file (from Django request.FILES).
        Saves to Medura_Train/uploads/ then indexes.
        """
        upload_dir = os.path.join(str(settings.MEDURA_TRAIN_DIR), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        # Save uploaded file
        filename = uploaded_file.name
        save_path = os.path.join(upload_dir, filename)

        with open(save_path, 'wb+') as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)

        # Index it
        return self.ingest_file(save_path, book_name=book_name)

    def scan_for_new_files(self) -> dict:
        """
        Scan Medura_Train directory for any new/modified files and index them.
        This is the 'auto-detect' function.
        """
        train_dir = str(settings.MEDURA_TRAIN_DIR)
        if not os.path.exists(train_dir):
            return {"status": "error", "message": "Medura_Train directory not found"}

        indexed = self._get_indexed_files()
        new_files = []

        for root, dirs, files in os.walk(train_dir):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in ['.pdf', '.md', '.txt']:
                    file_path = os.path.join(root, f)
                    file_hash = self._file_hash(file_path)
                    if file_hash not in indexed:
                        new_files.append(file_path)

        if not new_files:
            return {"status": "success", "message": "No new files found", "new_files": 0}

        # Index new files
        total_chunks = 0
        for fp in new_files:
            result = self.ingest_file(fp)
            if result["status"] == "success":
                total_chunks += result.get("chunks", 0)

        return {
            "status": "success",
            "new_files": len(new_files),
            "total_chunks": total_chunks,
            "message": f"Indexed {len(new_files)} new files ({total_chunks} chunks)"
        }

    def get_knowledge_stats(self) -> dict:
        """Get statistics about the current AI knowledge base."""
        from ai_engine.rag_pipeline import RAGPipeline
        rag = RAGPipeline()
        stats = rag.get_stats()

        return {
            "total_chunks": stats["total_chunks"],
            "collection_name": stats["collection_name"],
            "books": stats.get("books", {}),
            "indexed_files": len(self._get_indexed_files()),
        }

    @staticmethod
    def _auto_name(file_path: str) -> str:
        """Auto-generate a book name from file path."""
        name = Path(file_path).stem
        # Clean up
        name = name.replace('_', ' ').replace('-', ' ')
        # Remove common prefixes
        for prefix in ['copy of ', 'Copy of ']:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name.strip().title()
