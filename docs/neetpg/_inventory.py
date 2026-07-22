"""Inventory the NEET PG / INI-CET recall dataset and detect OCR/PDF tooling."""
import hashlib
import importlib.util as u
import json
import sys
from pathlib import Path

DATA = Path(r"C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material")
OUT = Path(r"C:\Users\DIVYANSHU\Desktop\crack_cms\docs\neetpg\_inventory.json")

MODS = [
    "fitz", "pdfplumber", "pypdf", "pytesseract", "PIL",
    "pdf2image", "cv2", "numpy", "rapidfuzz", "sentence_transformers",
    "tiktoken", "easyocr", "imagehash",
]


def sha256_short(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def detect():
    out = {}
    for m in MODS:
        spec = u.find_spec(m)
        if not spec:
            out[m] = {"available": False, "version": None}
            continue
        try:
            mod = __import__(m)
            out[m] = {"available": True, "version": getattr(mod, "__version__", "?")}
        except Exception as e:
            out[m] = {"available": False, "version": None, "error": str(e)[:120]}
    return out


def inventory():
    pdfs = []
    for p in sorted(DATA.glob("*.pdf")):
        st = p.stat()
        pdfs.append({
            "filename": p.name,
            "path": str(p),
            "size_mb": round(st.st_size / 1024 / 1024, 2),
            "size_bytes": st.st_size,
            "sha256_short": sha256_short(p),
            "mtime": st.st_mtime,
        })
    return pdfs


def main():
    pdfs = inventory()
    tooling = detect()
    result = {
        "source_dir": str(DATA),
        "pdf_count": len(pdfs),
        "size_mb_total": round(sum(p["size_mb"] for p in pdfs), 2),
        "pdfs": pdfs,
        "tooling": tooling,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"WROTE {OUT}")
    print(f"PDFs: {result['pdf_count']}  total MB: {result['size_mb_total']}")
    avail = [m for m, v in tooling.items() if v["available"]]
    miss = [m for m, v in tooling.items() if not v["available"]]
    print("AVAILABLE:", ", ".join(avail) or "(none)")
    print("MISSING:", ", ".join(miss) or "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
