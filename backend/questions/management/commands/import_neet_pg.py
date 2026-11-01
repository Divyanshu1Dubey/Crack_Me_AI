"""Import the NEET PG 2025 memory-based paper and the NEET PG 2020 paper.

Manual, opt-in command. It used to run from build.sh on every deploy, where
it deleted every ``exam_source="NEET PG"`` question (cascading their
attempts, bookmarks, notes, flashcards, discussions and test responses) and
re-created them: the 2020 paper with answer "A" for every question, ten 2025
stems cut in half by the option regex, and all of it as ``exam_type="cms"``
so it showed up in the UPSC CMS bank. It now:

* never deletes anything;
* upserts on a stable key: (exam_source "NEET PG", year, source
  ``NEET_PG_<year>_IMPORT``, display_number = the question's number in the
  paper). The number alone is not trusted -- ``backfill_display_number.py``
  and ``audit_questions --apply`` write ordinals into display_number -- so
  the row must also carry the question's stem or its B/C options (or be
  admin-protected). Other rows, such as those left by the old command (no
  display_number), are adopted by stem hash, including the cut-off stems its
  parser produced;
* by default only creates questions that are not in the bank yet and leaves
  existing rows alone. ``--replace`` also updates matched rows (text,
  options, answer, exam_type, display number), except rows an admin edited
  or answer-locked; a matched row with no answer key is hidden
  (``is_active=False``, ``needs_review=True``) instead of keeping a
  made-up answer;
* never invents an answer: a question without an answer key is skipped.
  ``--enrich`` asks the AI service for those (flagging them needs_review)
  and writes AI explanations (the ``why_correct`` text, only when the result
  is genuine content); a keyed answer always wins over the AI. An AI outage
  or an unusable reply (``AIUnavailable``) skips the AI step for that
  question instead of aborting the run;
* tags rows ``exam_type="neet_pg"`` (and the NEET PG exam track if present);
* honours ``RemovedQuestion`` tombstones and skips stems already present in
  the NEET PG bank from another source.

``--dry-run`` reports what would change without writing (and without AI
calls).
"""
import logging
import os
import re
import time
from collections import Counter

from django.core.management.base import BaseCommand

from questions.models import ExamTrack, Question, RemovedQuestion, Subject, Topic, compute_stem_hash
from questions.text_encoding import normalize_text, read_text_file

logger = logging.getLogger(__name__)

EXAM_SOURCE = "NEET PG"
EXAM_TYPE = "neet_pg"
LEGACY_PLACEHOLDER_EXPLANATION = "Reference: NEET PG previous year question bank."

# Subject mapping based on codes
SUBJECT_CODES = {
    "General Medicine": "MED",
    "Pediatrics": "PED",
    "Surgery": "SUR",
    "Obstetrics & Gynecology": "OBG",
    "Preventive & Social Medicine": "PSM",
}

# Mapping of correct answers for the 28 NEET PG 2025 questions
NEET_PG_2025_ANSWERS = {
    1: 'A', 2: 'B', 3: 'B', 4: 'C', 5: 'B', 6: 'B', 7: 'A', 8: 'C', 9: 'A', 10: 'B',
    11: 'B', 12: 'C', 13: 'C', 14: 'A', 15: 'B', 16: 'B', 17: 'B', 18: 'B', 19: 'B', 20: 'B',
    21: 'A', 22: 'B', 23: 'B', 24: 'B', 25: 'B', 26: 'B', 27: 'A', 28: 'C'
}

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEFAULT_PAPER_2025 = os.path.join(_BACKEND_DIR, "pyq", "Neet-PG", "2025")
DEFAULT_PAPER_2020 = os.path.join(
    _BACKEND_DIR, "pyq", "Neet-PG",
    "neet_pg_2020_question_paper_with_answer_key_pdfs_january_5questions.pdf",
)

_PAGE_NUMBER_LINE = re.compile(r"^\d{1,3}$")
_OPTION_LINE = re.compile(r"^\(([a-dA-D])\)\s*(.*)$")
_Q2025_START = re.compile(r"^Q(\d+)\.\s*(.*)$")
_Q2020_START = re.compile(r"^(\d+)\.\s+(.*)$")
_PAPER_2020_NOISE = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"^page\s+\d+\s+of\s+\d+$",
    r"^this question paper contains\b",
    r"^\((?:i|ii|iii|iv|v|vi)\)$",
    r"^it comprises\b",
    r"^attempt every question\b",
    r"^booklet\.$",
    r"^general instructions$",
    r"^neet\s*pg\s+\d{4}$",
    r"^question paper$",
    r"^detailed step-by-step solutions$",
))


def source_label(year):
    return f"NEET_PG_{year}_IMPORT"


def parse_paper(text, start_re, noise_res=()):
    """Line-based MCQ parser shared by both papers.

    A question starts on a line matching ``start_re``: the first such line,
    then only a number that follows the previous question (at most 3 ahead,
    so a numbered list inside a stem is not mistaken for a new question).
    Options are lines that *start* with
    "(a)".."(d)" in that order; the old regex accepted a bare " a " anywhere,
    which cut stems such as "Which of the following is a loop diuretic?" in
    half. Bare page numbers and ``noise_res`` lines (page footers, the
    instructions block) are dropped. Blocks without all four options are
    discarded.
    """
    questions = []
    current = None
    last_number = 0

    def finish(block):
        if block is None:
            return
        opts = block["options"]
        # Source line breaks are layout wraps, not paragraph breaks.
        stem = " ".join(block["stem"]).strip()
        if len(opts) == 4 and stem:
            questions.append({
                "number": block["number"],
                "question_text": stem,
                "option_a": " ".join(opts["A"]).strip(),
                "option_b": " ".join(opts["B"]).strip(),
                "option_c": " ".join(opts["C"]).strip(),
                "option_d": " ".join(opts["D"]).strip(),
            })

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or _PAGE_NUMBER_LINE.match(line) or any(r.match(line) for r in noise_res):
            continue
        start = start_re.match(line)
        if start:
            number = int(start.group(1))
            complete = current is None or len(current["options"]) == 4
            follows = last_number < number <= last_number + 3 and (complete or number == last_number + 1)
            if current is None or follows:
                finish(current)
                first = start.group(2).strip()
                current = {"number": number, "stem": [first] if first else [], "options": {}, "label": None}
                last_number = number
                continue
        if current is None:
            continue
        option = _OPTION_LINE.match(line)
        if option and len(current["options"]) < 4:
            expected = "ABCD"[len(current["options"])]
            if option.group(1).upper() == expected:
                body = option.group(2).strip()
                current["options"][expected] = [body] if body else []
                current["label"] = expected
                continue
        if current["label"]:
            current["options"][current["label"]].append(line)
        else:
            current["stem"].append(line)
    finish(current)
    return questions


def parse_2025_text(text):
    return parse_paper(text, _Q2025_START)


def parse_2020_pdf_text(text):
    return parse_paper(text, _Q2020_START, _PAPER_2020_NOISE)


# --- Legacy parsers --------------------------------------------------------
# Verbatim copies of the regexes the old command stored rows with. They are
# used only to recognise those rows (and the tombstones admins recorded for
# them), whose stems differ from what parse_paper() now produces.

def _legacy_item(num_str, q_text, opt_a, opt_b, opt_c, opt_d):
    return {
        "number": int(num_str),
        "question_text": q_text.strip(),
        "option_a": opt_a.strip(),
        "option_b": opt_b.strip(),
        "option_c": opt_c.strip(),
        "option_d": opt_d.strip(),
    }


def legacy_parse_2025_text(text):
    pattern = r'(?:^|\n)\s*Q(\d+)\.\s+(.+?)\s+\(?a\)?\s+(.+?)\s+\(?b\)?\s+(.+?)\s+\(?c\)?\s+(.+?)\s+\(?d\)?\s+(.+?)(?=\n\s*Q\d+\.|\Z)'
    return [_legacy_item(*m) for m in re.findall(pattern, text or "", re.DOTALL | re.MULTILINE)]


def legacy_parse_2020_pdf_text(text):
    pattern = r'(\d+)\.\s+(.+?)\s+\(?A\)?\s+(.+?)\s+\(?B\)?\s+(.+?)\s+\(?C\)?\s+(.+?)\s+\(?D\)?\s+(.+?)(?=\n\s*\d+\.|\Z)'
    out = []
    for num_str, q_text, *options in re.findall(pattern, text or "", re.DOTALL):
        clean_q = re.sub(
            r'Page\s+\d+\s+of\s+\d+|This\s+question\s+paper\s+contains.*', '', q_text, flags=re.IGNORECASE,
        ).strip()
        out.append(_legacy_item(num_str, clean_q, *options))
    return out


def _stem_hashes(*stems):
    hashes = set()
    for stem in stems:
        for variant in (stem, normalize_text(stem) if stem else stem):
            if variant:
                hashes.add(compute_stem_hash(variant))
    return hashes


def _option_signature(option_b, option_c):
    """Options B and C, which the old parser kept intact (it garbled the stem
    and option A, and left page numbers inside some options)."""
    def norm(text):
        tokens = (text or "").lower().split()
        return " ".join(t for t in tokens if not (t.isdigit() and len(t) <= 3))
    return norm(option_b), norm(option_c)


def _row_matches_item(row, new_hashes, signature, belongs_elsewhere=None):
    """Whether ``row`` (found by display_number) really is this question:
    same current stem, same B/C options, or admin-protected (an admin may
    have rewritten both; such rows are never updated anyway) -- unless the
    protected row's content is clearly another parsed question's
    (``belongs_elsewhere(row)``): its number is then a backfill ordinal, and
    claiming it here left that question without its row (created again as a
    duplicate) and this question's real row unrepaired."""
    if compute_stem_hash(row.question_text or "") in new_hashes:
        return True
    if _option_signature(row.option_b, row.option_c) == signature:
        return True
    if row.admin_edited or row.lock_answer:
        return not (belongs_elsewhere is not None and belongs_elsewhere(row))
    return False


def _adopt_legacy_row(item, new_hashes, all_hashes, rows_by_hash, claimed):
    """Find the row stored for ``item`` among the rows no question claimed by
    number -- the old command's rows (no display_number) and rows whose
    display_number is an ordinal rather than the paper's number -- or None.
    Stems alone are ambiguous: the old parser cut several of them to the
    same "Which of the following is"."""
    candidates = {}
    for stem_hash in all_hashes:
        for row in rows_by_hash.get(stem_hash, []):
            if row.pk not in claimed:
                candidates[row.pk] = row
    if not candidates:
        return None
    signature = _option_signature(normalize_text(item["option_b"]), normalize_text(item["option_c"]))
    same_options = [r for r in candidates.values() if _option_signature(r.option_b, r.option_c) == signature]
    if same_options:
        # Identical stems and options: the old command created rows in paper order.
        return min(same_options, key=lambda r: r.pk)
    same_current_stem = [r for r in candidates.values() if compute_stem_hash(r.question_text or "") in new_hashes]
    if len(same_current_stem) == 1:
        return same_current_stem[0]
    return None


class Command(BaseCommand):
    help = (
        "Import the NEET PG 2025 (memory-based) and 2020 papers. Never deletes; "
        "creates missing questions only, unless --replace."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--enrich",
            action="store_true",
            help="Ask AIService for answers to questions without an answer key (flagged needs_review) "
                 "and for explanations.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of questions to enrich (0 for all)",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Also update questions this command imported before (skipping admin-edited or answer-locked "
                 "rows); rows without an answer key are hidden (is_active=False, needs_review=True). "
                 "Nothing is ever deleted.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database or calling the AI service.",
        )
        parser.add_argument("--paper-2025", default=DEFAULT_PAPER_2025, help="Path of the NEET PG 2025 text file.")
        parser.add_argument("--paper-2020", default=DEFAULT_PAPER_2020, help="Path of the NEET PG 2020 PDF.")

    def handle(self, *args, **options):
        self.enrich_limit = options["limit"]
        self.replace = options["replace"]
        self.dry_run = options["dry_run"]
        self.enriched = 0
        self.ai_service = None
        if options["enrich"] and not self.dry_run:
            from ai_engine.services import AIService
            self.ai_service = AIService()
        self.would_enrich = bool(options["enrich"] and self.dry_run)

        papers = []
        txt_path = options["paper_2025"]
        self.stdout.write("\nParsing NEET PG 2025 text file...")
        if txt_path and os.path.exists(txt_path):
            content = read_text_file(txt_path)
            parsed = parse_2025_text(content)
            papers.append((2025, parsed, legacy_parse_2025_text(content), NEET_PG_2025_ANSWERS))
            self.stdout.write(self.style.SUCCESS(f"Parsed {len(parsed)} questions from NEET PG 2025 text file."))
        else:
            self.stderr.write(f"NEET PG 2025 text file not found at: {txt_path}")

        pdf_path = options["paper_2020"]
        self.stdout.write("\nParsing NEET PG 2020 PDF file...")
        if pdf_path and os.path.exists(pdf_path):
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(pdf_path)
                full_pdf_text = "".join(page.get_text() + "\n" for page in doc)
                doc.close()
                parsed = parse_2020_pdf_text(full_pdf_text)
                # The PDF has no answer key, so these need --enrich.
                papers.append((2020, parsed, legacy_parse_2020_pdf_text(full_pdf_text), {}))
                self.stdout.write(self.style.SUCCESS(f"Parsed {len(parsed)} questions from NEET PG 2020 PDF file."))
            except Exception as e:
                self.stderr.write(f"Error parsing PDF: {e}")
        else:
            self.stderr.write(f"NEET PG 2020 PDF file not found at: {pdf_path}")

        if not any(parsed for _, parsed, _, _ in papers):
            self.stdout.write(self.style.WARNING("No questions parsed from any source file. Nothing to do."))
            return

        self.subjects, self.topics = {}, {}
        self.exam_track = ExamTrack.objects.filter(code=EXAM_TYPE).first()
        if not self.dry_run:
            self._ensure_subjects()
        self.elsewhere_hashes = self._bank_hashes_from_other_sources()

        for year, parsed, legacy, answers in papers:
            stats = self._import_paper(year, parsed, legacy, answers)
            self._report(year, len(parsed), stats)

        if self.dry_run:
            self.stdout.write(self.style.WARNING("\nDry run: nothing was written."))
        self.stdout.write(self.style.SUCCESS("\nImport Finished!"))

    # -- taxonomy ------------------------------------------------------------

    def _ensure_subjects(self):
        subjects = [
            ("General Medicine", "MED", "#06b6d4"),
            ("Pediatrics", "PED", "#8b5cf6"),
            ("Surgery", "SUR", "#10b981"),
            ("Obstetrics & Gynecology", "OBG", "#ec4899"),
            ("Preventive & Social Medicine", "PSM", "#f59e0b"),
        ]
        for name, code, color in subjects:
            Subject.objects.get_or_create(
                code=code,
                defaults={"name": name, "color": color}
            )

    def _subject_and_topic(self, subject_name):
        code = SUBJECT_CODES[subject_name]
        if code not in self.subjects:
            subject = Subject.objects.get(code=code)
            topic, _ = Topic.objects.get_or_create(
                name="General",
                subject=subject,
                defaults={"importance": 5, "description": f"General topic for {subject.name}"}
            )
            self.subjects[code] = subject
            self.topics[code] = topic
        return self.subjects[code], self.topics[code]

    def _classify_subject(self, text):
        """Intelligently classify a question into a medical subject based on keywords."""
        text_lower = text.lower()

        # OBG
        if any(k in text_lower for k in ["uterus", "contraception", "pregnancy", "obstetrics", "gynaecology", "ovary", "menstrual", "placenta", "labor", "lactation", "ectopic", "vaginal", "gestational", "breast"]):
            return "Obstetrics & Gynecology"
        # Pediatrics
        if any(k in text_lower for k in ["pediatric", "child", "infant", "neonatal", "croup", "measles", "rubella", "newborn", "growth", "milestones", "kawasaki", "boy", "girl"]):
            return "Pediatrics"
        # Surgery
        if any(k in text_lower for k in ["resection", "hernia", "fracture", "ligate", "appendicitis", "incision", "amputation", "orthopedic", "surgical", "anesthesia", "intubation", "trauma", "artery", "vein"]):
            return "Surgery"
        # PSM
        if any(k in text_lower for k in ["vaccine", "prevention", "immunization", "program", "incidence", "epidemiology", "biostatistics", "sensitivity", "specificity", "maternal mortality"]):
            return "Preventive & Social Medicine"

        # Default
        return "General Medicine"

    # -- import --------------------------------------------------------------

    def _bank_hashes_from_other_sources(self):
        """Stem hashes of NEET PG questions that did not come from this command."""
        rows = (
            Question.objects.filter(exam_source__startswith=EXAM_SOURCE)
            .exclude(source__in=[source_label(2025), source_label(2020)])
            .values_list("question_text", flat=True)
        )
        return {compute_stem_hash(text) for text in rows if text}

    def _import_paper(self, year, parsed, legacy, answer_map):
        stats = Counter()
        source = source_label(year)
        removed_hashes = set(
            RemovedQuestion.objects.filter(exam_source=EXAM_SOURCE, year=year)
            .values_list("question_text_hash", flat=True)
        )
        existing = list(Question.objects.filter(exam_source=EXAM_SOURCE, year=year, source=source))
        rows_by_number = {}
        for q in existing:
            if q.display_number is not None:
                rows_by_number.setdefault(q.display_number, []).append(q)
        # A row is this question's by number only if its content agrees:
        # backfill_display_number.py / `audit_questions --apply` store
        # ordinals in display_number, and trusting those made the default
        # mode create duplicates and --replace rewrite the wrong rows.
        # The same two content keys _row_matches_item uses (current stem, B/C
        # options -- the old parser cut stems, so its stems are not keys).
        item_keys = {}
        for item in parsed:
            item_keys.setdefault(item["number"], (
                _stem_hashes(item["question_text"]),
                _option_signature(normalize_text(item["option_b"]), normalize_text(item["option_c"])),
            ))

        def content_of_another_item(number):
            def check(row):
                row_hash = compute_stem_hash(row.question_text or "")
                row_signature = _option_signature(row.option_b, row.option_c)
                return any(
                    other != number and (row_hash in hashes or (any(row_signature) and row_signature == sig))
                    for other, (hashes, sig) in item_keys.items()
                )
            return check

        by_number = {}
        for item in parsed:
            new_hashes = _stem_hashes(item["question_text"])
            signature = _option_signature(normalize_text(item["option_b"]), normalize_text(item["option_c"]))
            for q in rows_by_number.get(item["number"], []):
                if _row_matches_item(q, new_hashes, signature, content_of_another_item(item["number"])):
                    by_number[item["number"]] = q
                    break
        numbered_pks = {q.pk for q in by_number.values()}
        legacy_rows_by_hash = {}
        for q in existing:
            if q.pk not in numbered_pks:
                legacy_rows_by_hash.setdefault(compute_stem_hash(q.question_text or ""), []).append(q)
        legacy_by_number = {}
        for item in legacy:
            legacy_by_number.setdefault(item["number"], item)
        claimed = set(numbered_pks)

        for item in parsed:
            number = item["number"]
            legacy_item = legacy_by_number.get(number)
            new_hashes = _stem_hashes(item["question_text"])
            hashes = new_hashes | _stem_hashes(legacy_item["question_text"] if legacy_item else "")

            if hashes & removed_hashes:
                # A tombstone that matches only an old cut-off stem (e.g.
                # "Which of the following is") cannot tell which of the
                # questions sharing it was removed; skip them all, as the
                # old command did, rather than bring one back.
                precise = bool(new_hashes & removed_hashes)
                self.stdout.write(self.style.WARNING(
                    f"  -> Skipping NEET PG {year} Q{number} (admin-removed; "
                    f"{'stem hash matches' if precise else 'matches an old cut-off stem'})"
                ))
                stats["skipped_removed" if precise else "skipped_removed_old_stem"] += 1
                continue

            row = by_number.get(number)
            if row is None:
                row = _adopt_legacy_row(item, new_hashes, hashes, legacy_rows_by_hash, claimed)
            if row is not None:
                claimed.add(row.pk)
                if not self.replace:
                    stats["unchanged"] += 1
                    continue
                if row.admin_edited or row.lock_answer:
                    stats["protected"] += 1
                    continue
            elif hashes & self.elsewhere_hashes:
                stats["skipped_duplicate"] += 1
                continue

            answer, answer_from_ai, explanation = self._resolve_answer(item, answer_map)
            if not answer and self.would_enrich:
                stats["would_enrich"] += 1
                continue

            if row is None:
                if not answer:
                    stats["skipped_no_answer"] += 1
                    continue
                if not self.dry_run:
                    self._create(item, year, source, answer, answer_from_ai, explanation)
                stats["created"] += 1
            else:
                if not self.dry_run:
                    self._update(row, item, answer, answer_from_ai, explanation)
                stats["updated" if answer else "hidden_no_answer"] += 1
        return stats

    def _resolve_answer(self, item, answer_map):
        """Return (answer, answer_from_ai, explanation). Never guesses."""
        answer = (answer_map.get(item["number"]) or "").strip().upper()
        if self.would_enrich:
            return answer, False, None
        if not self.ai_service or not (self.enrich_limit == 0 or self.enriched < self.enrich_limit):
            return answer, False, None

        from ai_engine.services import AIUnavailable
        from questions.ai_per_question import usable_ai_text, usable_explain_result

        self.stdout.write(f"  -> Querying AI for Q{item['number']}...")
        options_dict = {
            "A": item["option_a"],
            "B": item["option_b"],
            "C": item["option_c"],
            "D": item["option_d"],
        }
        answer_from_ai = False
        if not answer:
            try:
                ai_ans = (self.ai_service.get_consensus_answer(item["question_text"], options_dict) or "")
            except AIUnavailable as exc:
                self._ai_unavailable(item, "answer", exc)
                ai_ans = ""
            ai_ans = str(ai_ans).strip().upper()[:1]
            if ai_ans in ("A", "B", "C", "D"):
                answer, answer_from_ai = ai_ans, True
                self.stdout.write(f"     AI determined correct option: {ai_ans}")
        explanation = None
        if answer:
            try:
                ai_exp = self.ai_service.explain_after_answer(
                    item["question_text"], options=options_dict, correct_answer=answer,
                )
            except AIUnavailable as exc:
                # Outage or unparseable reply (AIOutputUnusable): import the
                # question without an AI explanation instead of aborting.
                self._ai_unavailable(item, "explanation", exc)
                ai_exp = None
            # explain_after_answer returns a structured dict; only its
            # why_correct text is an explanation, and only when the result is
            # genuine content (never outage text or an unparsed fallback).
            if usable_explain_result(ai_exp):
                explanation = usable_ai_text(ai_exp.get("why_correct")) or None
        self.enriched += 1
        time.sleep(0.5)
        return answer, answer_from_ai, explanation

    def _ai_unavailable(self, item, what, exc):
        logger.warning("import_neet_pg: AI %s unavailable for Q%s: %s", what, item["number"], exc)
        self.stdout.write(self.style.WARNING(f"     AI {what} unavailable ({exc}); continuing without it"))

    def _create(self, item, year, source, answer, answer_from_ai, explanation):
        subject, topic = self._subject_and_topic(self._classify_subject(item["question_text"]))
        explanation = explanation or LEGACY_PLACEHOLDER_EXPLANATION
        Question.objects.create(
            question_text=normalize_text(item["question_text"]),
            option_a=normalize_text(item["option_a"]),
            option_b=normalize_text(item["option_b"]),
            option_c=normalize_text(item["option_c"]),
            option_d=normalize_text(item["option_d"]),
            correct_answer=answer,
            explanation=normalize_text(explanation),
            subject=subject,
            topic=topic,
            year=year,
            paper=1,
            difficulty="medium",
            exam_source=EXAM_SOURCE,
            exam_type=EXAM_TYPE,
            exam_track=self.exam_track,
            source=source,
            display_number=item["number"],
            needs_review=answer_from_ai,
        )

    def _update(self, row, item, answer, answer_from_ai, explanation):
        row.question_text = normalize_text(item["question_text"])
        row.option_a = normalize_text(item["option_a"])
        row.option_b = normalize_text(item["option_b"])
        row.option_c = normalize_text(item["option_c"])
        row.option_d = normalize_text(item["option_d"])
        row.exam_type = EXAM_TYPE
        row.display_number = item["number"]
        fields = [
            "question_text", "option_a", "option_b", "option_c", "option_d",
            "exam_type", "display_number", "updated_at",
        ]
        if self.exam_track is not None:
            row.exam_track = self.exam_track
            fields.append("exam_track")
        if answer:
            row.correct_answer = answer
            fields.append("correct_answer")
            if answer_from_ai:
                row.needs_review = True
                fields.append("needs_review")
            if explanation and (row.explanation or "").strip() in ("", LEGACY_PLACEHOLDER_EXPLANATION):
                row.explanation = normalize_text(explanation)
                fields.append("explanation")
        else:
            # No answer key: the old command published this row with "A".
            row.is_active = False
            row.needs_review = True
            fields += ["is_active", "needs_review"]
        row.save(update_fields=fields)

    def _report(self, year, parsed_count, stats):
        self.stdout.write(f"\nNEET PG {year}: {parsed_count} parsed")
        labels = (
            ("created", "created"),
            ("unchanged", "already in the bank, left unchanged (use --replace to update)"),
            ("updated", "updated (--replace)"),
            ("hidden_no_answer", "hidden: no answer key (is_active=False, needs_review=True)"),
            ("protected", "skipped: admin-edited or answer-locked"),
            ("skipped_no_answer", "skipped: no answer key (use --enrich to ask the AI service)"),
            ("would_enrich", "no answer key: --enrich would ask the AI service"),
            ("skipped_removed", "skipped: admin-removed"),
            ("skipped_removed_old_stem",
             "skipped: a removal recorded against an old cut-off stem shared by several questions "
             "(review in the admin)"),
            ("skipped_duplicate", "skipped: stem already in the NEET PG bank from another source"),
        )
        for key, label in labels:
            if stats.get(key):
                self.stdout.write(f"  - {label}: {stats[key]}")
