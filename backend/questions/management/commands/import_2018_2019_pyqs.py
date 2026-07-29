import os
import re
import json
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from django.db import transaction
from questions.models import Subject, Topic, Question
from questions.import_protection import is_removed
from ai_engine.services import AIService
from questions.text_encoding import normalize_text, read_text_file

logger = logging.getLogger(__name__)
db_lock = threading.Lock()

SUBJECT_MAP = {
    "General Medicine": "MED",
    "Pediatrics": "PED",
    "Surgery": "SUR",
    "Obstetrics & Gynaecology": "OBG",
    "Preventive & Social Medicine": "PSM",
}

class Command(BaseCommand):
    help = "Parse, import, and enrich UPSC CMS 2018 and 2019 PYQ questions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse files and show count without saving to database",
        )
        parser.add_argument(
            "--enrich",
            action="store_true",
            help="Enrich imported questions using AI service",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of questions to enrich per year (0 for all)",
        )
        parser.add_argument(
            "--no-import",
            action="store_true",
            help="Skip importing/deleting, just run enrichment on existing database records",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=0,
            help="Year to process (2018 or 2019, 0 for both)",
        )
        parser.add_argument(
            "--sleep-ms",
            type=int,
            default=300,
            help="Delay in milliseconds between AI service calls",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        enrich = options["enrich"]
        limit = options["limit"]
        no_import = options["no_import"]
        selected_year = options["year"]
        sleep_ms = options["sleep_ms"]

        # Ensure subjects exist
        if not dry_run:
            self._ensure_subjects()

        if selected_year:
            years = [selected_year]
        else:
            years = [2018, 2019]

        for year in years:
            db_questions = []
            
            if no_import:
                self.stdout.write(self.style.SUCCESS(f"\nSkipping import for {year}. Fetching existing database questions..."))
                db_questions = list(Question.objects.filter(year=year))
                self.stdout.write(self.style.SUCCESS(f"Found {len(db_questions)} questions in database for year {year}."))
            else:
                file_path = os.path.join("pyq", str(year))
                if not os.path.isabs(file_path):
                    file_path = os.path.join(os.getcwd(), file_path)

                if not os.path.exists(file_path):
                    self.stderr.write(self.style.ERROR(f"File not found for {year}: {file_path}"))
                    continue

                self.stdout.write(self.style.SUCCESS(f"\nProcessing {year} from: {file_path}"))
                # Read via text_encoding so we never re-introduce mojibake
                # if the file was written with a non-UTF-8 locale.
                content = read_text_file(file_path)

                questions = self._parse_file_content(content, year)
                self.stdout.write(self.style.SUCCESS(f"Successfully parsed {len(questions)} questions for {year}."))

                if dry_run:
                    self.stdout.write(self.style.WARNING("Dry run: showing first 2 parsed questions."))
                    for idx, q in enumerate(questions[:2]):
                        self.stdout.write(f"[{idx+1}] Paper {q['paper']} | {q['subject']} | Q{q['number']}")
                        self.stdout.write(f"Text: {q['question_text'][:150]}...")
                        self.stdout.write(f"A) {q['option_a']}")
                        self.stdout.write(f"B) {q['option_b']}")
                        self.stdout.write(f"C) {q['option_c']}")
                        self.stdout.write(f"D) {q['option_d']}")
                    continue

                # Clear existing questions for this year
                deleted_count, _ = Question.objects.filter(year=year).delete()
                self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing questions for year {year} to prevent duplicates."))

                # Save questions
                with transaction.atomic():
                    for q_data in questions:
                        sub_code = SUBJECT_MAP.get(q_data["subject"], "MED")
                        subject = Subject.objects.filter(code=sub_code).first()
                        if not subject:
                            continue

                        # General topic mapping
                        topic, _ = Topic.objects.get_or_create(
                            name="General",
                            subject=subject,
                            defaults={"importance": 5, "description": f"General topic for {subject.name}"}
                        )

                        # Honor admin "Remove from bank" tombstones — if this
                        # stem was previously removed, skip it on re-import.
                        if is_removed(q_data["question_text"]):
                            self.stdout.write(self.style.WARNING(
                                f"  → Skipping PYQ {year} P{q_data['paper']} Q{q_data.get('number','?')}: admin-removed"
                            ))
                            continue

                        new_q = Question.objects.create(
                            question_text=normalize_text(q_data["question_text"]),
                            option_a=normalize_text(q_data["option_a"]),
                            option_b=normalize_text(q_data["option_b"]),
                            option_c=normalize_text(q_data["option_c"]),
                            option_d=normalize_text(q_data["option_d"]),
                            correct_answer="",
                            explanation="",
                            subject=subject,
                            topic=topic,
                            year=year,
                            paper=q_data["paper"],
                            difficulty="medium",
                            source=f"PYQ_{year}_Paper{q_data['paper']}.txt"
                        )
                        db_questions.append(new_q)

                self.stdout.write(self.style.SUCCESS(f"Saved {len(db_questions)} questions for year {year}."))

            # Enrich questions if requested
            if enrich:
                ai_service = AIService()
                self.stdout.write(self.style.SUCCESS(f"AI Service initialized. Enriching questions for {year} in parallel..."))
                
                to_process = db_questions
                if limit > 0:
                    to_process = to_process[:limit]

                enriched_count = 0
                max_workers = 10
                self.stdout.write(self.style.SUCCESS(f"Starting ThreadPoolExecutor with {max_workers} workers for {len(to_process)} questions..."))
                
                def worker(q_item):
                    self.stdout.write(f"  [+] Started Q{q_item.id} (Year: {q_item.year} | Paper: {q_item.paper})")
                    success = self._enrich_question(q_item, ai_service)
                    if sleep_ms > 0:
                        time.sleep(sleep_ms / 1000.0)
                    return q_item.id, success

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(worker, q): q for q in to_process}
                    completed_count = 0
                    for future in as_completed(futures):
                        q_id, success = future.result()
                        completed_count += 1
                        if success:
                            enriched_count += 1
                            self.stdout.write(self.style.SUCCESS(f"    [OK] Q{q_id} enriched ({completed_count}/{len(to_process)})"))
                        else:
                            self.stdout.write(self.style.WARNING(f"    [FAIL] Q{q_id} failed ({completed_count}/{len(to_process)})"))

                self.stdout.write(self.style.SUCCESS(f"Enriched {enriched_count} questions for year {year}."))

    def _parse_file_content(self, content, year):
        lines = content.split("\n")
        questions = []
        current_q = None
        q_text_accumulator = []
        
        opt_a_re = re.compile(r"^\s*\([aA]\)\s*(.*)$")
        opt_b_re = re.compile(r"^\s*\([bB]\)\s*(.*)$")
        opt_c_re = re.compile(r"^\s*\([cC]\)\s*(.*)$")
        opt_d_re = re.compile(r"^\s*\([dD]\)\s*(.*)$")
        
        q_start_re = re.compile(r"^\s*(\d+)\s*\.?\s*(.*)$")
        
        paper_num = 1
        expected_num = 1
        
        def save_current():
            nonlocal current_q, q_text_accumulator
            if not current_q:
                return
            
            q_block_text = "\n".join(q_text_accumulator).strip()
            num_search = re.search(r"^(\d+)\s*\.?\s*(.*)", q_block_text, re.DOTALL)
            if num_search:
                text = num_search.group(2).strip()
            else:
                text = q_block_text
                
            current_q["question_text"] = text
            questions.append(current_q)
            current_q = None
            q_text_accumulator = []

        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue
                
            # Paper transition based on keyword
            if ("paper ii" in line_str.lower() or "paper-ii" in line_str.lower()) and len(questions) > 90:
                if paper_num == 1:
                    save_current()
                    paper_num = 2
                    expected_num = 1
            
            # Check options
            ma = opt_a_re.match(line_str)
            mb = opt_b_re.match(line_str)
            mc = opt_c_re.match(line_str)
            md = opt_d_re.match(line_str)
            
            if ma:
                if current_q: current_q["option_a"] = ma.group(1).strip()
                continue
            elif mb:
                if current_q: current_q["option_b"] = mb.group(1).strip()
                continue
            elif mc:
                if current_q: current_q["option_c"] = mc.group(1).strip()
                continue
            elif md:
                if current_q: current_q["option_d"] = md.group(1).strip()
                continue
                
            # Question start check
            mq = q_start_re.match(line_str)
            if mq:
                num = int(mq.group(1))
                if num == expected_num:
                    save_current()
                    
                    # Map subject
                    subject = "General Medicine"
                    if paper_num == 1:
                        subject = "General Medicine" if num <= 96 else "Pediatrics"
                    else:
                        if num <= 40:
                            subject = "Surgery"
                        elif num <= 80:
                            subject = "Obstetrics & Gynaecology"
                        else:
                            subject = "Preventive & Social Medicine"

                    current_q = {
                        "number": num,
                        "question_text": "",
                        "option_a": "",
                        "option_b": "",
                        "option_c": "",
                        "option_d": "",
                        "paper": paper_num,
                        "subject": subject,
                        "year": year
                    }
                    q_text_accumulator = [line_str]
                    expected_num += 1
                    if expected_num > 120:
                        expected_num = 1
                    continue
                    
            if current_q:
                q_text_accumulator.append(line)
                
        save_current()
        return questions

    def _ensure_subjects(self):
        subjects = [
            ("General Medicine", "MED", "#06b6d4"),
            ("Pediatrics", "PED", "#8b5cf6"),
            ("Surgery", "SUR", "#10b981"),
            ("Obstetrics & Gynaecology", "OBG", "#ec4899"),
            ("Preventive & Social Medicine", "PSM", "#f59e0b"),
        ]
        for name, code, color in subjects:
            Subject.objects.get_or_create(
                code=code,
                defaults={"name": name, "color": color}
            )

    def _enrich_question(self, q: Question, ai_service: AIService) -> bool:
        if q.correct_answer and q.explanation and q.topic.name != "General":
            return False

        prompt = f"""You are a medical data expert. Help solve this UPSC CMS (Combined Medical Services) MCQ and generate complete revision explanations.

Question: {q.question_text}
Options:
A) {q.option_a}
B) {q.option_b}
C) {q.option_c}
D) {q.option_d}
Subject: {q.subject.name}

Tasks:
1. Determine the correct option (A, B, C, or D).
2. Classify this question into a specific medical topic name under the subject.
3. Provide a concise, high-yield answer explanation.
4. Provide a conceptual background explanation.
5. Provide a mnemonic or learning tip to remember the concept.
6. Provide 3-5 keywords/tags.
7. Classify the difficulty (easy, medium, hard).

Return strict JSON only (no markdown codeblock format, no surrounding text, just raw JSON) using this format:
{{
  "correct_answer": "A",
  "topic_name": "Valvular Heart Disease",
  "difficulty": "medium",
  "explanation": "concise explanation here...",
  "concept_explanation": "concept background here...",
  "mnemonic": "mnemonic trick here...",
  "concept_tags": ["cardiology", "murmur", "mitral valve"]
}}
"""
        try:
            raw = ai_service._call_ai(
                prompt,
                system="You are a medical data enrichment assistant. Return valid JSON only.",
                temperature=0.1,
                max_tokens=1000,
            )
            
            match = re.search(r"\{.*\}", raw or "", re.DOTALL)
            if not match:
                return False
            clean_json = match.group(0)
            clean_json = re.sub(r',\s*([\]\}])', r'\1', clean_json)
            payload = json.loads(clean_json)
        except Exception as e:
            logger.warning(f"AI enrichment failed for Q{q.id}: {e}")
            return False

        # Apply results
        answer = str(payload.get("correct_answer", "")).strip().upper()[:1]
        diff = str(payload.get("difficulty", "")).strip().lower()
        topic_name = str(payload.get("topic_name", "")).strip()
        explanation_text = str(payload.get("explanation", "")).strip()
        concept_explanation_text = str(payload.get("concept_explanation", "")).strip()
        mnemonic_text = str(payload.get("mnemonic", "")).strip()
        tags = payload.get("concept_tags", [])

        with db_lock:
            if answer in {"A", "B", "C", "D"}:
                q.correct_answer = answer

            if diff in {"easy", "medium", "hard"}:
                q.difficulty = diff

            if topic_name:
                topic, _ = Topic.objects.get_or_create(
                    subject=q.subject,
                    name=topic_name,
                    defaults={"importance": 5, "description": f"{topic_name} under {q.subject.name}"}
                )
                q.topic = topic

            q.explanation = explanation_text
            q.concept_explanation = concept_explanation_text
            q.mnemonic = mnemonic_text
            
            if isinstance(tags, list):
                q.concept_tags = [str(t).strip().lower() for t in tags if str(t).strip()]

            q.save()
        return True
