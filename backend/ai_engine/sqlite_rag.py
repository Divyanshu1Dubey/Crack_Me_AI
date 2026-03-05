"""
Lightweight SQLite-based RAG Pipeline.
Works with Python 3.14+ without ChromaDB dependency issues.
Uses TF-IDF + cosine similarity for retrieval.
"""
import os
import sqlite3
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict
import re

from django.conf import settings

logger = logging.getLogger(__name__)


class SQLiteRAGPipeline:
    """
    SQLite-based RAG pipeline using TF-IDF for similarity search.
    Fallback for systems where ChromaDB doesn't work.
    """

    DB_NAME = "rag_store.sqlite3"

    def __init__(self):
        self._conn = None
        self._gemini = None
        self._groq = None
        self._init_db()
        self._init_ai()

    def _init_db(self):
        """Initialize SQLite database for RAG storage."""
        db_dir = getattr(settings, 'CHROMA_DB_DIR', os.path.join(settings.BASE_DIR, 'chroma_db'))
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, self.DB_NAME)

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # Create tables
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                book TEXT,
                page INTEGER,
                chunk_index INTEGER,
                source_file TEXT,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_book ON documents(book);
            CREATE INDEX IF NOT EXISTS idx_page ON documents(page);

            CREATE TABLE IF NOT EXISTS indexed_files (
                file_hash TEXT PRIMARY KEY,
                file_path TEXT,
                book_name TEXT,
                chunks_count INTEGER,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()

        count = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        logger.info(f"SQLite RAG initialized: {count} existing chunks")

    def _init_ai(self):
        """Initialize AI clients for answer generation."""
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self._gemini = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("Gemini initialized for RAG")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

        groq_key = getattr(settings, 'GROQ_API_KEY', '')
        if groq_key:
            try:
                from groq import Groq
                self._groq = Groq(api_key=groq_key)
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

    # ─── INGESTION ────────────────────────────────────────

    def index_textbook(self, file_path: str, book_name: Optional[str] = None,
                       chunk_size: int = 500, overlap: int = 50,
                       progress_callback=None) -> int:
        """Index a textbook file into SQLite."""
        from ai_engine.document_processor import DocumentProcessor

        processor = DocumentProcessor()
        book_name = book_name or Path(file_path).stem

        # Check if already indexed
        file_hash = self._hash_file(file_path)
        existing = self._conn.execute(
            "SELECT * FROM indexed_files WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if existing:
            logger.info(f"Already indexed: {book_name} ({existing['chunks_count']} chunks)")
            return 0

        logger.info(f"Indexing: {book_name}")
        pages = processor.extract_text(file_path)

        if not pages:
            logger.error(f"No text extracted from {file_path}")
            return 0

        total_chunks = 0

        for i, page_data in enumerate(pages):
            page_num = page_data["page_num"]
            text = page_data["text"]

            chunks = processor.chunk_text(text, chunk_size, overlap)

            for j, chunk in enumerate(chunks):
                if len(chunk.strip()) < 30:
                    continue

                chunk_id = f"{book_name}_{page_num}_{j}"
                keywords = self._extract_keywords(chunk)

                try:
                    self._conn.execute("""
                        INSERT OR REPLACE INTO documents (id, text, book, page, chunk_index, source_file, keywords)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (chunk_id, chunk, book_name, page_num, j, Path(file_path).name, json.dumps(keywords)))
                    total_chunks += 1
                except Exception as e:
                    logger.warning(f"Failed to add chunk {chunk_id}: {e}")

            if progress_callback:
                progress_callback(i + 1, len(pages), book_name)

        # Mark file as indexed
        self._conn.execute("""
            INSERT OR REPLACE INTO indexed_files (file_hash, file_path, book_name, chunks_count)
            VALUES (?, ?, ?, ?)
        """, (file_hash, file_path, book_name, total_chunks))
        self._conn.commit()

        logger.info(f"Indexed {total_chunks} chunks from {book_name}")
        return total_chunks

    def index_all_textbooks(self, textbook_dir: str, progress_callback=None) -> dict:
        """Index all files in a directory."""
        results = {}
        for file in os.listdir(textbook_dir):
            if file.startswith('.') or file.startswith('Copy of'):
                continue
            if file.endswith(('.pdf', '.txt', '.md')):
                file_path = os.path.join(textbook_dir, file)
                book_name = self._clean_book_name(file)
                chunks = self.index_textbook(file_path, book_name, progress_callback=progress_callback)
                results[book_name] = chunks
        return results

    # ─── RETRIEVAL ────────────────────────────────────────

    def search(self, query: str, n_results: int = 5,
               book_filter: Optional[str] = None) -> List[Dict]:
        """
        Search using keyword matching + TF-IDF-like scoring (memory-efficient).
        Returns list of {text, book, page, score} dicts.
        """
        import heapq

        query_keywords = self._extract_keywords(query)
        query_lower = query.lower()

        # Build SQL query
        sql = "SELECT id, text, book, page, keywords FROM documents"
        params = []

        if book_filter:
            sql += " WHERE book = ?"
            params.append(book_filter)

        cursor = self._conn.execute(sql, params)
        top_results = []  # min-heap of (score, dict)
        batch_size = 500

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                text = row['text']
                doc_keywords = json.loads(row['keywords']) if row['keywords'] else []

                score = self._calculate_relevance(query_lower, query_keywords, text.lower(), doc_keywords)

                if score > 0.1:
                    item = (score, {
                        'text': text,
                        'book': row['book'],
                        'page': row['page'],
                        'score': round(score, 4),
                        'source_file': '',
                    })
                    if len(top_results) < n_results:
                        heapq.heappush(top_results, item)
                    elif score > top_results[0][0]:
                        heapq.heapreplace(top_results, item)

        results = [item[1] for item in sorted(top_results, key=lambda x: -x[0])]
        return results

    def _calculate_relevance(self, query: str, query_kw: List[str],
                             doc_text: str, doc_kw: List[str]) -> float:
        """Calculate relevance score between query and document."""
        score = 0.0

        # Exact phrase match (highest weight)
        if query in doc_text:
            score += 0.5

        # Keyword overlap
        query_set = set(query_kw)
        doc_set = set(doc_kw)
        if query_set and doc_set:
            overlap = len(query_set & doc_set)
            score += (overlap / max(len(query_set), 1)) * 0.3

        # Word overlap
        query_words = set(query.split())
        doc_words = set(doc_text.split())
        if query_words:
            word_overlap = len(query_words & doc_words)
            score += (word_overlap / len(query_words)) * 0.2

        return min(score, 1.0)

    # ─── RAG ANSWER ────────────────────────────────────────

    def rag_answer(self, question: str, n_context: int = 5) -> dict:
        """Answer using RAG with retrieved context."""
        context_chunks = self.search(question, n_results=n_context)

        if not context_chunks:
            return {
                "answer": "No relevant textbook content found. Please index textbooks first using: python manage.py train_ai",
                "citations": [],
                "confidence": "low",
            }

        # Build context
        context_str = ""
        citations = []
        for i, chunk in enumerate(context_chunks):
            context_str += f"\n[Source {i+1}: {chunk['book']} p.{chunk['page']}]\n{chunk['text']}\n"
            citations.append({
                "book": chunk["book"],
                "page": chunk["page"],
                "excerpt": chunk["text"][:200],
                "relevance": chunk["score"],
            })

        prompt = f"""You are a UPSC CMS exam preparation expert. Answer the following question using ONLY the provided textbook context.

QUESTION: {question}

TEXTBOOK CONTEXT:
{context_str}

Provide:
1. A clear, concise answer (2-3 paragraphs)
2. Key points for exam revision (bullet points)
3. Any helpful mnemonic if applicable
4. Reference the specific textbook and page number

Be precise and exam-focused."""

        answer = self._generate_answer(prompt)

        return {
            "answer": answer,
            "citations": citations,
            "confidence": "high" if context_chunks and context_chunks[0]["score"] > 0.3 else "medium",
        }

    def find_textbook_reference(self, question_text: str) -> List[Dict]:
        """Find textbook references for a question."""
        results = self.search(question_text, n_results=3)
        return [{
            "book": r["book"],
            "page": r["page"],
            "excerpt": r["text"][:300],
            "relevance_score": r["score"],
        } for r in results]

    # ─── HELPERS ────────────────────────────────────────

    def _generate_answer(self, prompt: str) -> str:
        """Generate answer using Gemini or Groq."""
        if self._gemini:
            try:
                response = self._gemini.generate_content(
                    prompt,
                    generation_config={"temperature": 0.2, "max_output_tokens": 2048}
                )
                return response.text
            except Exception as e:
                logger.warning(f"Gemini failed: {e}")

        if self._groq:
            try:
                response = self._groq.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are a UPSC CMS medical exam expert."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=2048,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Groq failed: {e}")

        return "AI answer generation unavailable. Please configure API keys in backend/.env"

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract medical keywords from text."""
        # Common medical terms pattern
        words = re.findall(r'\b[A-Za-z][a-z]{2,}\b', text)
        # Filter stopwords
        stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
                     'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'being',
                     'their', 'said', 'each', 'which', 'she', 'how', 'its', 'may', 'than',
                     'with', 'from', 'this', 'that', 'these', 'those', 'most', 'other'}
        keywords = [w.lower() for w in words if w.lower() not in stopwords and len(w) > 3]
        # Return unique keywords, preserving order
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:50]

    def _hash_file(self, file_path: str) -> str:
        """Create hash of file for deduplication."""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while buf:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def _clean_book_name(self, filename: str) -> str:
        """Clean filename to book name."""
        name = Path(filename).stem
        name = name.replace('_', ' ').replace('-', ' ')
        return name.strip()

    def get_stats(self) -> dict:
        """Get database statistics."""
        count = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        books = self._conn.execute("SELECT DISTINCT book FROM documents").fetchall()
        return {
            "total_chunks": count,
            "books": [b[0] for b in books],
            "backend": "sqlite",
        }

    def clear_all(self):
        """Clear all indexed data."""
        self._conn.execute("DELETE FROM documents")
        self._conn.execute("DELETE FROM indexed_files")
        self._conn.commit()
        logger.info("Cleared all RAG data")

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
