"""
RAG (Retrieval-Augmented Generation) Pipeline for textbook search.
Uses SQLite + TF-IDF for local vector storage (Python 3.14 compatible).
"""
import os
import json
import hashlib
import logging
import sqlite3
import math
import re
import warnings
from pathlib import Path
from typing import Optional
from collections import Counter

# Suppress deprecation warning from google.generativeai (still functional)
warnings.filterwarnings("ignore", message=".*google.generativeai.*", category=FutureWarning)

from django.conf import settings
logger = logging.getLogger(__name__)



class RAGPipeline:
    """
    Full RAG pipeline:
    1. Ingest PDFs/MD/TXT → extract text → chunk → store in SQLite
    2. Query → TF-IDF search → retrieve similar chunks → generate answer with citations
    """

    COLLECTION_NAME = "crackcms_textbooks"
    # Max chunks to score per query (prevents OOM on low-memory hosts)
    MAX_SEARCH_CHUNKS = 2000

    def __init__(self):
        # Abort early on memory-constrained environments
        if os.getenv('DISABLE_RAG', '').lower() in ('1', 'true', 'yes'):
            raise RuntimeError("RAG disabled via DISABLE_RAG env var")
        self._gemini = None
        self._groq = None
        self._db_path = None
        self._conn = None
        self._init_db()
        self._init_ai_clients()

    def _init_db(self):
        """Initialize SQLite-based vector store."""
        db_dir = getattr(settings, 'CHROMA_DB_DIR',
                         os.path.join(settings.BASE_DIR, 'chroma_db'))
        os.makedirs(db_dir, exist_ok=True)
        self._db_path = os.path.join(db_dir, 'rag_store.sqlite3')

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document TEXT NOT NULL,
                book TEXT NOT NULL,
                page INTEGER DEFAULT 0,
                chunk_index INTEGER DEFAULT 0,
                source_file TEXT DEFAULT '',
                tokens TEXT DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS idf_cache (
                term TEXT PRIMARY KEY,
                idf REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book)")
        self._conn.commit()

        count = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        logger.info(f"RAG SQLite store initialized: {count} existing chunks")

    def _init_ai_clients(self):
        """Initialize Gemini and Groq for answer generation."""
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

    # ─── TEXT PROCESSING ──────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple word tokenizer for TF-IDF."""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
        tokens = text.split()
        stop = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall',
                'should', 'may', 'might', 'must', 'can', 'could', 'of', 'in', 'to',
                'for', 'with', 'on', 'at', 'from', 'by', 'as', 'or', 'and', 'but',
                'not', 'no', 'if', 'so', 'it', 'its', 'this', 'that', 'these', 'those',
                'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'they', 'them'}
        return [t for t in tokens if len(t) > 1 and t not in stop]

    def _rebuild_idf(self):
        """Rebuild IDF cache from all documents (memory-efficient row iteration)."""
        total_docs = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if total_docs == 0:
            return
        df = Counter()
        cursor = self._conn.execute("SELECT tokens FROM chunks")
        batch_size = 500
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for (tokens_json,) in rows:
                try:
                    tokens = set(json.loads(tokens_json))
                    for t in tokens:
                        df[t] += 1
                except (json.JSONDecodeError, TypeError):
                    pass
        self._conn.execute("DELETE FROM idf_cache")
        batch = []
        for term, freq in df.items():
            idf = math.log((total_docs + 1) / (freq + 1)) + 1
            batch.append((term, idf))
            if len(batch) >= 1000:
                self._conn.executemany("INSERT OR REPLACE INTO idf_cache VALUES (?, ?)", batch)
                batch.clear()
        if batch:
            self._conn.executemany("INSERT OR REPLACE INTO idf_cache VALUES (?, ?)", batch)
        self._conn.commit()
        logger.info(f"IDF cache rebuilt: {len(df)} terms from {total_docs} docs")

    def _get_idf(self, term: str) -> float:
        """Get IDF for a term."""
        row = self._conn.execute("SELECT idf FROM idf_cache WHERE term=?", (term,)).fetchone()
        return row[0] if row else 1.0

    def _tfidf_score(self, query_tokens: list[str], doc_tokens_json: str) -> float:
        """Compute TF-IDF cosine similarity between query and document."""
        try:
            doc_tokens = json.loads(doc_tokens_json)
        except (json.JSONDecodeError, TypeError):
            return 0.0
        doc_tf = Counter(doc_tokens)
        doc_total = len(doc_tokens) or 1
        query_tf = Counter(query_tokens)
        query_total = len(query_tokens) or 1

        score = 0.0
        for term in set(query_tokens):
            idf = self._get_idf(term)
            q_tfidf = (query_tf[term] / query_total) * idf
            d_tfidf = (doc_tf.get(term, 0) / doc_total) * idf
            score += q_tfidf * d_tfidf

        q_norm = math.sqrt(sum(((query_tf[t] / query_total) * self._get_idf(t)) ** 2 for t in query_tf))
        d_norm = math.sqrt(sum(((doc_tf[t] / doc_total) * self._get_idf(t)) ** 2 for t in doc_tf))

        if q_norm == 0 or d_norm == 0:
            return 0.0
        return score / (q_norm * d_norm)

    # ─── INGESTION ────────────────────────────────────────

    def index_textbook(self, file_path: str, book_name: Optional[str] = None,
                       chunk_size: int = 200, overlap: int = 30,
                       progress_callback=None, skip_idf_rebuild: bool = False) -> int:
        """Index a textbook PDF or MD file into the vector store."""
        from ai_engine.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        book_name = book_name or Path(file_path).stem
        logger.info(f"Indexing document: {book_name}")
        pages = processor.extract_text(file_path)
        if not pages:
            logger.error(f"No text extracted from {file_path}")
            return 0

        total_chunks = 0
        for i, page_data in enumerate(pages):
            page_num = page_data["page_num"]
            text = page_data["text"]
            page_id = self._make_id(book_name, page_num)
            if self._conn.execute("SELECT 1 FROM chunks WHERE id=?", (page_id,)).fetchone():
                continue
            chunks = processor.chunk_text(text, chunk_size, overlap)
            for j, chunk in enumerate(chunks):
                if len(chunk.strip()) < 30:
                    continue
                chunk_id = f"{page_id}_c{j}"
                if self._conn.execute("SELECT 1 FROM chunks WHERE id=?", (chunk_id,)).fetchone():
                    continue
                tokens = self._tokenize(chunk)
                try:
                    self._conn.execute(
                        "INSERT INTO chunks (id, document, book, page, chunk_index, source_file, tokens) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (chunk_id, chunk, book_name, page_num, j, Path(file_path).name, json.dumps(tokens))
                    )
                    total_chunks += 1
                except Exception as e:
                    logger.warning(f"Failed to add chunk {chunk_id}: {e}")
            if progress_callback:
                progress_callback(i + 1, len(pages), book_name)

        self._conn.commit()
        if total_chunks > 0 and not skip_idf_rebuild:
            self._rebuild_idf()
        logger.info(f"Indexed {total_chunks} chunks from {book_name}")
        return total_chunks

    def index_all_textbooks(self, textbook_dir: str, progress_callback=None) -> dict:
        """Index all PDFs/MD/TXT in a directory."""
        results = {}
        for file in sorted(os.listdir(textbook_dir)):
            if file.startswith('Copy of') or file.startswith('.'):
                continue
            if file.endswith('.pdf') or file.endswith('.txt') or file.endswith('.md'):
                file_path = os.path.join(textbook_dir, file)
                book_name = self._clean_book_name(file)
                chunks = self.index_textbook(file_path, book_name, progress_callback=progress_callback)
                results[book_name] = chunks
        return results

    # ─── RETRIEVAL ────────────────────────────────────────

    def search(self, query: str, n_results: int = 5,
               book_filter: Optional[str] = None) -> list[dict]:
        """Search across indexed textbooks using TF-IDF similarity (memory-efficient)."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        if book_filter:
            cursor = self._conn.execute(
                "SELECT id, document, book, page, source_file, tokens FROM chunks WHERE book=?",
                (book_filter,)
            )
        else:
            cursor = self._conn.execute(
                "SELECT id, document, book, page, source_file, tokens FROM chunks"
            )

        import heapq
        top_results = []  # min-heap of (score, counter, dict) -- counter breaks ties
        counter = 0
        batch_size = 500
        chunks_scanned = 0
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row_id, doc, book, page, source_file, tokens_json in rows:
                chunks_scanned += 1
                if chunks_scanned > self.MAX_SEARCH_CHUNKS:
                    break
                score = self._tfidf_score(query_tokens, tokens_json)
                if score > 0:
                    result_dict = {
                        "text": doc,
                        "book": book,
                        "page": page,
                        "score": round(score, 4),
                        "source_file": source_file,
                    }
                    item = (score, counter, result_dict)
                    counter += 1
                    if len(top_results) < n_results:
                        heapq.heappush(top_results, item)
                    elif score > top_results[0][0]:
                        heapq.heapreplace(top_results, item)
            if chunks_scanned > self.MAX_SEARCH_CHUNKS:
                break

        results = [item[2] for item in sorted(top_results, key=lambda x: -x[0])]
        return results

    # ─── RAG ANSWER ────────────────────────────────────────

    def rag_answer(self, question: str, n_context: int = 5) -> dict:
        """Answer using RAG with textbook context and citations."""
        context_chunks = self.search(question, n_results=n_context)
        if not context_chunks:
            return {
                "answer": "No relevant textbook content found. Please run: python manage.py train_ai",
                "citations": [],
                "confidence": "low",
            }

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

        prompt = f"""You are a UPSC CMS exam preparation expert. Answer the following question using ONLY the provided textbook context. Be precise, exam-focused, and cite specific textbook references.

QUESTION: {question}

TEXTBOOK CONTEXT:
{context_str}

Provide:
1. A clear, concise answer (2-3 paragraphs)
2. Key points for exam revision (bullet points)
3. Any helpful mnemonic if applicable
4. Reference the specific textbook and page number

Answer in a structured, student-friendly format."""

        answer = self._generate_answer(prompt)
        return {
            "answer": answer,
            "citations": citations,
            "confidence": "high" if context_chunks[0]["score"] > 0.3 else "medium",
        }

    def find_textbook_reference(self, question_text: str) -> list[dict]:
        """Find where a topic is discussed in standard textbooks."""
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
                logger.warning(f"Gemini generation failed: {e}")

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
                logger.warning(f"Groq generation failed: {e}")

        return "AI answer generation is unavailable. Please configure API keys."

    def _make_id(self, book_name: str, page_num: int) -> str:
        return hashlib.md5(f"{book_name}:{page_num}".encode()).hexdigest()

    def _clean_book_name(self, filename: str) -> str:
        name = Path(filename).stem
        name = name.split('_')[0] if '_' in name and len(name.split('_')[-1]) > 20 else name
        name = name.replace("Copy of ", "")
        return name.strip()

    def get_stats(self) -> dict:
        count = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        books = self._conn.execute("SELECT DISTINCT book FROM chunks").fetchall()
        book_stats = {}
        for (book,) in books:
            bc = self._conn.execute("SELECT COUNT(*) FROM chunks WHERE book=?", (book,)).fetchone()[0]
            book_stats[book] = bc
        return {
            "total_chunks": count,
            "collection_name": self.COLLECTION_NAME,
            "books": book_stats,
        }

    def close(self):
        if self._conn:
            self._conn.close()
