#!/usr/bin/env python3
"""
=============================================================
  CrackCMS RAG Training Script
  Run this LOCALLY (not Colab) from the backend/ directory:
    python train_on_colab.py
  
  OR copy to Colab if local crashes — see instructions below.
=============================================================

This script indexes ALL textbooks, PYQs, notes, and web knowledge
into the SQLite RAG store so the AI tutor can answer with citations.

It processes files in small batches to avoid memory crashes.
"""
import os
import sys
import json
import hashlib
import sqlite3
import re
import math
import time
from pathlib import Path
from collections import Counter

# ─── CONFIGURATION ────────────────────────────────────────
# If running locally from backend/ directory:
BASE_DIR = Path(__file__).resolve().parent
MEDURA_DIR = BASE_DIR / "Medura_Train"
DB_PATH = BASE_DIR / "chroma_db" / "rag_store.sqlite3"

# If running on Colab, mount drive and set paths:
# from google.colab import drive
# drive.mount('/content/drive')
# BASE_DIR = Path("/content/drive/MyDrive/crack_cms/backend")
# MEDURA_DIR = BASE_DIR / "Medura_Train"
# DB_PATH = BASE_DIR / "chroma_db" / "rag_store.sqlite3"

CHUNK_SIZE = 500  # words per chunk
CHUNK_OVERLAP = 50  # overlap words


# ─── TEXT EXTRACTION ──────────────────────────────────────
def extract_text_from_file(file_path):
    """Extract text from PDF, MD, or TXT files. Returns list of {page_num, text}."""
    ext = Path(file_path).suffix.lower()
    
    if ext in ['.txt', '.md']:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            if not text.strip():
                return []
            # Split long markdown files into logical pages by headers
            sections = re.split(r'\n(?=#{1,3}\s)', text)
            pages = []
            for i, section in enumerate(sections):
                if section.strip():
                    pages.append({"page_num": i + 1, "text": section.strip()})
            return pages if pages else [{"page_num": 1, "text": text.strip()}]
        except Exception as e:
            print(f"  ❌ Failed to read {file_path}: {e}")
            return []
    
    if ext == '.pdf':
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if text.strip() and len(text.strip()) > 30:
                        pages.append({"page_num": i + 1, "text": text.strip()})
            return pages
        except ImportError:
            print("  ⚠️ pdfplumber not installed. Install: pip install pdfplumber")
            return []
        except Exception as e:
            print(f"  ❌ Failed to parse PDF {file_path}: {e}")
            return []
    
    return []


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks by sentence boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_len = 0
    
    for sentence in sentences:
        words = sentence.split()
        sentence_len = len(words)
        
        if current_len + sentence_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep overlap
            overlap_words = []
            overlap_len = 0
            for s in reversed(current_chunk):
                s_words = s.split()
                if overlap_len + len(s_words) > overlap:
                    break
                overlap_words.insert(0, s)
                overlap_len += len(s_words)
            current_chunk = overlap_words
            current_len = overlap_len
        
        current_chunk.append(sentence)
        current_len += sentence_len
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


# ─── TOKENIZATION & IDF ──────────────────────────────────
STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall',
    'should', 'may', 'might', 'must', 'can', 'could', 'of', 'in', 'to',
    'for', 'with', 'on', 'at', 'from', 'by', 'as', 'or', 'and', 'but',
    'not', 'no', 'if', 'so', 'it', 'its', 'this', 'that', 'these', 'those',
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'they', 'them'
}

def tokenize(text):
    """Simple word tokenizer for TF-IDF."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


def rebuild_idf(conn):
    """Rebuild IDF cache from all documents."""
    total_docs = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if total_docs == 0:
        return
    
    print(f"\n📊 Rebuilding IDF index for {total_docs} chunks...")
    rows = conn.execute("SELECT tokens FROM chunks").fetchall()
    df = Counter()
    for (tokens_json,) in rows:
        try:
            tokens = set(json.loads(tokens_json))
            for t in tokens:
                df[t] += 1
        except (json.JSONDecodeError, TypeError):
            pass
    
    conn.execute("DELETE FROM idf_cache")
    for term, freq in df.items():
        idf = math.log((total_docs + 1) / (freq + 1)) + 1
        conn.execute("INSERT OR REPLACE INTO idf_cache VALUES (?, ?)", (term, idf))
    conn.commit()
    print(f"✅ IDF cache rebuilt: {len(df)} unique terms")


# ─── DATABASE SETUP ───────────────────────────────────────
def setup_db():
    """Create/open the SQLite RAG database."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
    return conn


def make_id(book_name, page_num):
    return hashlib.md5(f"{book_name}:{page_num}".encode()).hexdigest()


# ─── BOOK NAME MAPPING ───────────────────────────────────
BOOK_NAMES = {
    # Textbook PDFs
    "Copy of Ghai Essential Pediatrics": "Ghai Essential Pediatrics, 9E",
    "Ghai Essential Pediatrics": "Ghai Essential Pediatrics, 9E",
    "Copy of Harrison": "Harrison's Principles of Internal Medicine",
    "Copy of Nelson Textbook": "Nelson Textbook of Pediatrics",
    "Nelson Textbook": "Nelson Textbook of Pediatrics",
    "Copy of Park Textbook": "Park's Preventive & Social Medicine",
    # Markdown notes
    "ghai_pediatrics_cms_notes": "Ghai Pediatrics (CMS Notes)",
    "harrisons_medicine_cms_notes": "Harrison's Medicine (CMS Notes)",
    "parks_psm_cms_notes": "Park's PSM (CMS Notes)",
    "surgery_obg_cms_notes": "Surgery & OBG (CMS Notes)",
    # Web knowledge
    "standard_student_doubts": "CMS Student Doubts & FAQs",
    "upsc_cms_complete_syllabus": "UPSC CMS Complete Syllabus",
    "wiki_cms_overview": "CMS Exam Overview (Wiki)",
    # PYQ database
    "cms_pyq_database_2018_2024": "CMS PYQ Database 2018-2024",
}


def get_book_name(file_path):
    """Map file path to a clean book name."""
    stem = Path(file_path).stem
    for key, name in BOOK_NAMES.items():
        if key.lower() in stem.lower():
            return name
    # For PYQ PDFs like "2024 Paper 1_xxxxx"
    pyq_match = re.match(r'(\d{4})\s*(Paper\s*\d)', stem, re.IGNORECASE)
    if pyq_match:
        return f"CMS PYQ {pyq_match.group(1)} {pyq_match.group(2)}"
    # Fallback
    return stem.replace('_', ' ').strip().title()


# ─── INDEXING ─────────────────────────────────────────────
def index_file(conn, file_path, book_name=None):
    """Index a single file into the RAG store."""
    book_name = book_name or get_book_name(file_path)
    
    # Check if already indexed
    existing = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE book=?", (book_name,)
    ).fetchone()[0]
    if existing > 0:
        print(f"  ⏭️  Already indexed: {book_name} ({existing} chunks)")
        return 0
    
    pages = extract_text_from_file(file_path)
    if not pages:
        print(f"  ⚠️  No text extracted from {Path(file_path).name}")
        return 0
    
    total_chunks = 0
    for page_data in pages:
        page_num = page_data["page_num"]
        text = page_data["text"]
        chunks = chunk_text(text)
        
        for j, chunk in enumerate(chunks):
            if len(chunk.strip()) < 30:
                continue
            
            chunk_id = f"{make_id(book_name, page_num)}_c{j}"
            tokens = tokenize(chunk)
            
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO chunks (id, document, book, page, chunk_index, source_file, tokens) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (chunk_id, chunk, book_name, page_num, j, Path(file_path).name, json.dumps(tokens))
                )
                total_chunks += 1
            except Exception as e:
                print(f"    ❌ Chunk error: {e}")
    
    conn.commit()
    return total_chunks


def get_all_files():
    """Collect all files to index, organized by priority."""
    files = []
    
    # 1. Markdown notes (fast, high value)
    md_dirs = [
        MEDURA_DIR / "textbooks",
        MEDURA_DIR / "web_knowledge",
        MEDURA_DIR / "PYQ",
    ]
    for d in md_dirs:
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.suffix in ['.md', '.txt']:
                    files.append(("📝 Notes", str(f)))

    # 2. PYQ PDFs (medium, very high value)
    pyq_dir = MEDURA_DIR / "PYQ"
    if pyq_dir.exists():
        for f in sorted(pyq_dir.iterdir()):
            if f.suffix == '.pdf':
                files.append(("📋 PYQ PDF", str(f)))

    # 3. Textbook PDFs (large, do last) — skip duplicates ("Copy of")
    tb_dir = MEDURA_DIR / "textbooks"
    if tb_dir.exists():
        seen_books = set()
        for f in sorted(tb_dir.iterdir()):
            if f.suffix == '.pdf':
                name = get_book_name(str(f))
                if name not in seen_books:
                    seen_books.add(name)
                    files.append(("📚 Textbook", str(f)))

    # 4. Root directory PDFs that are textbooks (not forms)
    for f in sorted(MEDURA_DIR.iterdir()):
        if f.suffix == '.pdf' and f.is_file():
            name = f.stem.lower()
            # Only include actual textbooks, not admin forms
            if any(kw in name for kw in ['ghai', 'nelson', 'harrison', 'park', 'final']):
                files.append(("📚 Textbook (root)", str(f)))
    
    return files


# ─── MAIN ─────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  🧠 CrackCMS RAG Training Script")
    print("=" * 60)
    print(f"  📂 Data directory: {MEDURA_DIR}")
    print(f"  💾 Database: {DB_PATH}")
    print()
    
    if not MEDURA_DIR.exists():
        print(f"❌ Medura_Train directory not found at {MEDURA_DIR}")
        print("   Make sure you're running from the backend/ directory")
        sys.exit(1)
    
    conn = setup_db()
    
    # Show current stats
    existing = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    books = conn.execute("SELECT DISTINCT book, COUNT(*) FROM chunks GROUP BY book").fetchall()
    print(f"📊 Current RAG store: {existing} chunks from {len(books)} books")
    for book, count in books:
        print(f"   • {book}: {count} chunks")
    print()
    
    # Gather all files
    all_files = get_all_files()
    print(f"📁 Found {len(all_files)} files to process\n")
    
    grand_total = 0
    
    for i, (category, file_path) in enumerate(all_files):
        filename = Path(file_path).name
        book_name = get_book_name(file_path)
        print(f"[{i+1}/{len(all_files)}] {category} {filename}")
        print(f"         → Book: {book_name}")
        
        start = time.time()
        chunks = index_file(conn, file_path, book_name)
        elapsed = time.time() - start
        
        if chunks > 0:
            print(f"         ✅ Indexed {chunks} chunks ({elapsed:.1f}s)")
            grand_total += chunks
        print()
    
    # Rebuild IDF if new content was added
    if grand_total > 0:
        rebuild_idf(conn)
    
    # Final stats
    total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    books = conn.execute("SELECT DISTINCT book, COUNT(*) FROM chunks GROUP BY book").fetchall()
    
    print("\n" + "=" * 60)
    print(f"  ✅ TRAINING COMPLETE")
    print(f"  📊 Total chunks: {total}")
    print(f"  📚 Books indexed: {len(books)}")
    print("=" * 60)
    for book, count in sorted(books, key=lambda x: -x[1]):
        print(f"   • {book}: {count} chunks")
    
    conn.close()
    print("\n💾 Database saved to:", DB_PATH)
    print("🚀 Restart the Django server to use the trained model!")


if __name__ == "__main__":
    main()
