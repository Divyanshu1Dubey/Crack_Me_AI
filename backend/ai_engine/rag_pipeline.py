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



def ai_offline_mode() -> bool:
    """AI_OFFLINE_MODE: never call an external LLM; answer extractively."""
    return os.getenv('AI_OFFLINE_MODE', '').strip().lower() in ('1', 'true', 'yes')


class RAGPipeline:
    """
    Full RAG pipeline:
    1. Ingest PDFs/MD/TXT → extract text → chunk → store in SQLite
    2. Query → BM25 over the whole store (ai_engine.lexical_index) → top chunks
       → LLM answer with citations, or an extractive answer when no LLM is
       available (AI_OFFLINE_MODE or every provider failed).

    Constructing the pipeline is cheap and read-only: the SQLite write
    connection (and schema creation) is opened only when indexing, and the
    AI clients only when an answer has to be generated. (It used to switch
    the git-tracked store to WAL and run DDL + COMMIT on every request.)
    """

    COLLECTION_NAME = "crackcms_textbooks"

    def __init__(self):
        # Abort early on memory-constrained environments
        if os.getenv('DISABLE_RAG', '').lower() in ('1', 'true', 'yes'):
            raise RuntimeError("RAG disabled via DISABLE_RAG env var")
        self._gemini = None
        self._groq = None
        self._omniroute = None
        self._clients_ready = False
        self._write_conn = None
        db_dir = getattr(settings, 'CHROMA_DB_DIR', os.path.join(settings.BASE_DIR, 'chroma_db'))
        self._db_dir = db_dir
        self._db_path = os.path.join(db_dir, 'rag_store.sqlite3')

    @property
    def _conn(self) -> sqlite3.Connection:
        """Write connection (ingestion only); creates the schema on first use."""
        if self._write_conn is None:
            os.makedirs(self._db_dir, exist_ok=True)
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS idf_cache (
                    term TEXT PRIMARY KEY,
                    idf REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book)")
            conn.commit()
            self._write_conn = conn
        return self._write_conn

    def _init_ai_clients(self):
        """Initialize AI clients for answer generation (OmniRoute first, then fallbacks)."""
        if self._clients_ready:
            return
        self._clients_ready = True
        # OmniRoute gateway — first-stop for all AI calls
        omniroute_key = getattr(settings, 'OMNIROUTE_API_KEY', '') or os.getenv('OMNIROUTE_API_KEY', '')
        omniroute_base = getattr(settings, 'OMNIROUTE_BASE_URL', '') or os.getenv('OMNIROUTE_BASE_URL', 'https://omniroute-production-9d6b.up.railway.app/v1')
        if omniroute_key and omniroute_base:
            try:
                from openai import OpenAI
                self._omniroute = OpenAI(
                    api_key=omniroute_key,
                    base_url=omniroute_base,
                    max_retries=0
                )
                logger.info("✅ OmniRoute gateway initialized for RAG")
            except Exception as e:
                logger.warning(f"OmniRoute init failed for RAG: {e}")

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
        if total_chunks > 0:
            from ai_engine.lexical_index import invalidate
            invalidate(self._db_path)
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
        """BM25 search over the whole store (see ai_engine/lexical_index.py).

        Results: dicts with text, book, page, score (BM25, unbounded) and
        source_file, best first. Raw question-paper chunks are only returned
        when ``book_filter`` names that book. Personal/administrative
        documents are never returned.
        """
        from ai_engine.lexical_index import get_index

        if not (query or '').strip():
            return []
        try:
            n = max(1, min(int(n_results), 50))
        except (TypeError, ValueError):
            n = 5
        index, _stats = get_index(self._db_path)
        if index is None:
            return []
        hits = index.search(query, n, book=book_filter or None,
                            min_score=float(getattr(settings, 'RAG_MIN_SCORE', 0.0)))
        ceiling = index.max_score(query) or 1.0
        return [{
            "text": doc.text,
            "book": doc.book,
            "page": doc.page,
            "score": round(score, 4),
            # Score as a share of the best possible score for this query (0..1).
            "norm_score": round(min(1.0, score / ceiling), 4),
            "source_file": doc.source_file,
        } for score, doc in hits]

    # ─── RAG ANSWER ────────────────────────────────────────

    def rag_answer(self, question: str, n_context: int = 5) -> dict:
        """Answer using RAG with textbook context and citations."""
        context_chunks = self.search(question, n_results=n_context)
        if not context_chunks:
            # Friendly fallback surfaced to the student — the previous
            # message leaked the operator-only `python manage.py train_ai`
            # command which made it look like the platform was broken.
            return {
                "answer": (
                    "No matching textbook content was found for this query. "
                    "Please try a different search term, or use AI Tutor mode "
                    "for a general answer."
                ),
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
                # 0..1 (the UI shows it as a percentage); raw BM25 is unbounded.
                "relevance": chunk.get("norm_score", 0.0),
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

        confidence = _confidence(context_chunks[0].get("norm_score", 0.0))
        answer = None if ai_offline_mode() else self._generate_answer(prompt)
        if answer:
            return {
                "answer": answer,
                "citations": citations,
                "confidence": confidence,
                "generated": True,
                "offline": False,
            }
        # No LLM (offline mode, or every provider failed): answer with the
        # retrieved sentences themselves, cited. Callers should not charge
        # for this (generated=False).
        from ai_engine.lexical_index import extractive_answer
        extract = extractive_answer(question, context_chunks)
        if extract:
            return {
                "answer": "Offline answer from the textbook passages (no AI model was used):\n\n" + extract["answer"],
                "citations": extract["citations"],
                "confidence": "medium" if extract["coverage"] >= 0.5 else "low",
                "generated": False,
                "offline": True,
            }
        return {
            "answer": ("AI answers are unavailable right now and no textbook passage answers this "
                       "directly. The closest passages are listed below."),
            "citations": citations,
            "confidence": "low",
            "generated": False,
            "offline": True,
        }

    def find_textbook_reference(self, question_text: str) -> list[dict]:
        """Find where a topic is discussed in standard textbooks."""
        results = self.search(question_text, n_results=3)
        return [{
            "book": r["book"],
            "page": r["page"],
            "excerpt": r["text"][:300],
            "relevance_score": r.get("norm_score", 0.0),
        } for r in results]

    # ─── HELPERS ────────────────────────────────────────

    def _generate_answer(self, prompt: str) -> Optional[str]:
        """Generate answer using OmniRoute gateway first, then Gemini/Groq fallbacks.

        Returns None when no model produced text (the caller falls back to an
        extractive answer instead of showing an operator message).
        """
        if ai_offline_mode():
            return None
        self._init_ai_clients()
        # Try OmniRoute first (tries multiple models via gateway)
        if self._omniroute:
            for model_name in ["auto/fast", "auto/best-chat", "auto/best-reasoning", "openai/gpt-4o-mini"]:
                try:
                    response = self._omniroute.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "You are a UPSC CMS medical exam expert."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.2,
                        max_tokens=2048,
                        timeout=20.0,
                    )
                    text = response.choices[0].message.content
                    if text:
                        logger.info(f"RAG OmniRoute [{model_name}] OK")
                        return text
                except Exception as e:
                    logger.warning(f"RAG OmniRoute [{model_name}] error: {e}")
                    continue

        # Fallback to Gemini
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

        return None

    def _make_id(self, book_name: str, page_num: int) -> str:
        return hashlib.md5(f"{book_name}:{page_num}".encode()).hexdigest()

    def _clean_book_name(self, filename: str) -> str:
        name = Path(filename).stem
        name = name.split('_')[0] if '_' in name and len(name.split('_')[-1]) > 20 else name
        name = name.replace("Copy of ", "")
        return name.strip()

    def get_stats(self) -> dict:
        """Store statistics (read-only), plus what the search index serves."""
        from ai_engine.lexical_index import get_index
        if not os.path.exists(self._db_path):
            return {"total_chunks": 0, "collection_name": self.COLLECTION_NAME, "books": {}}
        conn = sqlite3.connect(f'file:{self._db_path}?mode=ro', uri=True, check_same_thread=False)
        try:
            count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            book_stats = dict(conn.execute("SELECT book, COUNT(*) FROM chunks GROUP BY book").fetchall())
        finally:
            conn.close()
        _index, stats = get_index(self._db_path)
        return {
            "total_chunks": count,
            "collection_name": self.COLLECTION_NAME,
            "books": book_stats,
            "searchable_chunks": stats.docs_indexed if stats else 0,
        }

    def close(self):
        if self._write_conn is not None:
            self._write_conn.close()
            self._write_conn = None


def _confidence(norm_score: float) -> str:
    """Coarse retrieval-confidence label from the top hit's normalised score.

    Calibrated on the benchmark's dev split (docs/audit/RAG_BENCHMARK.md):
    raw BM25 scores did not predict relevance at all, the normalised score
    does somewhat (>= 0.3: a relevant passage in the top 5 for 64% of dev
    queries vs 51% overall), and no cut-off is reliable enough to say "high".
    """
    medium = float(getattr(settings, 'RAG_CONFIDENCE_MEDIUM_NORM', 0.3))
    return "medium" if norm_score >= medium else "low"


def generate_rag_response_sync(prompt: str) -> str:
    """Helper to instantiate pipeline and run RAG synchronously."""
    try:
        pipeline = RAGPipeline()
        # rag_answer normally returns a dict with 'answer' and 'context_used'
        res = pipeline.rag_answer(prompt, n_context=3)
        pipeline.close()
        return res.get('answer', str(res))
    except Exception as e:
        logger.error(f"RAG sync error: {e}")
        return f"AI Assistant received your query but RAG failed: {e}"
