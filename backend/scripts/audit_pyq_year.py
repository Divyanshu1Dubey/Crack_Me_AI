"""
audit_pyq_year.py — Review PYQ text files for one exam year and emit a
human-reviewable CSV of (question, options, current_correct_answer).

This does NOT auto-correct answers (medical questions require expert review),
but it produces a flat, sortable CSV that the user can mark up in Excel /
Google Sheets and then re-import via _review_and_fix_answers.py.

Usage:
    cd backend
    python scripts/audit_pyq_year.py --year 2019 --out pyq_2019_audit.csv

Output columns:
    q_no, paper, question_text, option_a, option_b, option_c, option_d,
    flagged_note

The parser handles the standard UPSC CMS PYQ format used in backend/pyq/<year>:
  Q. <number>.
  <question text wrapping multiple lines>
  (a) <option A>
  (b) <option B>
  (c) <option C>
  (d) <option D>

Multi-statement questions (Select the correct answer using the code given
below) are also captured; their statements are joined into the question text.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

# Allow running this file from either repo root or backend/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PYQ_DIR = PROJECT_ROOT / "backend" / "pyq"


def parse_pyq_file(path: Path) -> list[dict]:
    """Parse a single PYQ text file into structured records."""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Normalise CRLF and the Page-N header lines the file printer inserts.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)

    # Split into questions by "Q." prefix on its own line OR followed by number.
    # The file uses patterns like:
    #   "1. Austin Flint Murmur..."
    # We tokenise on "(a) " option-A prefix to find question boundaries.
    records: list[dict] = []
    current_paper = "I"  # default; updated below
    paper_match = re.search(r"PAPER[-\s]?(I{1,3}V?)\b", text, re.IGNORECASE)
    if paper_match:
        current_paper = paper_match.group(1).upper()

    # Each question starts at "N.\n" where N is 1-3 digits at line start,
    # and ends just before the next such marker or EOF.
    blocks = re.split(r"\n(?=\d{1,3}\.\s*\n)", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Extract question number and text.
        m = re.match(r"^(\d{1,3})\.\s*\n(.+?)(?=\n\(a\))", block, re.DOTALL)
        if not m:
            continue
        q_no = int(m.group(1))
        question_text = " ".join(line.strip() for line in m.group(2).splitlines() if line.strip())

        # Extract options.
        opt_pattern = re.compile(r"\(([a-d])\)\s*(.+?)(?=\n\([a-d]\)|\Z)", re.DOTALL)
        options = {letter: " ".join(t.strip().split()) for letter, t in opt_pattern.findall(block)}
        if len(options) < 2:
            # Not a valid MCQ block — skip.
            continue

        records.append({
            "q_no": q_no,
            "paper": current_paper,
            "question_text": question_text[:500],
            "option_a": options.get("a", ""),
            "option_b": options.get("b", ""),
            "option_c": options.get("c", ""),
            "option_d": options.get("d", ""),
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, help="PYQ year, e.g. 2019")
    parser.add_argument("--pyq-dir", default=str(DEFAULT_PYQ_DIR))
    parser.add_argument("--out", default=None, help="Output CSV path")
    args = parser.parse_args()

    pyq_dir = Path(args.pyq_dir)
    # Files can be either a directory per year or a flat .txt file
    year_dir = pyq_dir / args.year
    if year_dir.is_dir():
        files = sorted(year_dir.glob("*.txt"))
    elif (pyq_dir / args.year).is_file():
        files = [pyq_dir / args.year]
    else:
        print(f"❌ Could not find PYQ data for year {args.year} in {pyq_dir}")
        return 1

    if not files:
        print(f"❌ No .txt files found under {year_dir}")
        return 1

    all_records: list[dict] = []
    for f in files:
        records = parse_pyq_file(f)
        print(f"  ✓ {f.name}: parsed {len(records)} questions")
        all_records.extend(records)

    out_path = Path(args.out) if args.out else pyq_dir / f"{args.year}_audit.csv"
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["q_no", "paper", "question_text", "option_a", "option_b", "option_c", "option_d", "flagged_note"],
        )
        writer.writeheader()
        # flagged_note is left blank for human reviewers to fill in.
        for r in all_records:
            writer.writerow({**r, "flagged_note": ""})

    print(f"\n✅ Wrote {len(all_records)} questions to {out_path}")
    print("   Open the CSV, add a 'flagged_note' column if a question needs review,")
    print("   then re-import via the existing _export_fixture workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
