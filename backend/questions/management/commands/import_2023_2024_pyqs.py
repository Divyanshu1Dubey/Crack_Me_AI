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
from ai_engine.services import AIService

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
    help = "Parse, import, and enrich UPSC CMS 2023 and 2024 PYQ questions."

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
        sleep_ms = options["sleep_ms"]

        # Ensure subjects exist
        if not dry_run:
            self._ensure_subjects()

        years = [2023, 2024]
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
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                questions = self._parse_lines(lines, year)
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

                        new_q = Question.objects.create(
                            question_text=q_data["question_text"],
                            option_a=q_data["option_a"],
                            option_b=q_data["option_b"],
                            option_c=q_data["option_c"],
                            option_d=q_data["option_d"],
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
                    # We print start
                    self.stdout.write(f"  [+] Started Q{q_item.id} (Year: {q_item.year})")
                    success = self._enrich_question(q_item, ai_service)
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

    def _parse_lines(self, lines, year):
        questions = []
        first_paper = 1 if year == 2024 else 2
        current_paper = first_paper
        expected_number = 1
        current_question = None
        question_text_lines = []

        inline_pattern = re.compile(
            r"^\s*\([aA]\)\s*(.*?)\s*\([bB]\)\s*(.*?)\s*\([cC]\)\s*(.*?)\s*\([dD]\)\s*(.*)$"
        )

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check if we explicitly hit a paper change marker
            if "paper" in line_str.lower() or "end of paper" in line_str.lower() or "combined medical service" in line_str.lower():
                if current_question:
                    current_question["question_text"] = "\n".join(question_text_lines).strip()
                    questions.append(current_question)
                    current_question = None
                current_paper = 3 - first_paper
                expected_number = 1
                continue

            # Check for new question start
            q_match = re.match(r"^\s*(\d+)\.\s*(.*)", line_str)
            if q_match:
                num = int(q_match.group(1))
                rest = q_match.group(2)
                if num == expected_number:
                    if current_question:
                        current_question["question_text"] = "\n".join(question_text_lines).strip()
                        questions.append(current_question)
                    
                    # Assign subject
                    subject = None
                    if year == 2024:
                        if current_paper == 1:
                            subject = "General Medicine" if num <= 96 else "Pediatrics"
                        else:
                            if num <= 40:
                                subject = "Surgery"
                            elif num <= 80:
                                subject = "Obstetrics & Gynaecology"
                            else:
                                subject = "Preventive & Social Medicine"
                    else: # year == 2023
                        if current_paper == 2:
                            if num <= 40:
                                subject = "Surgery"
                            elif num <= 80:
                                subject = "Obstetrics & Gynaecology"
                            else:
                                subject = "Preventive & Social Medicine"
                        else: # Paper 1
                            subject = "General Medicine" if num <= 96 else "Pediatrics"

                    current_question = {
                        "number": num,
                        "question_text": "",
                        "option_a": "",
                        "option_b": "",
                        "option_c": "",
                        "option_d": "",
                        "paper": current_paper,
                        "subject": subject,
                        "year": year
                    }
                    question_text_lines = [rest]
                    expected_number += 1
                    if expected_number > 120:
                        expected_number = 1
                        current_paper = 3 - first_paper
                    continue

            # Check for options
            inline_match = inline_pattern.match(line_str)
            if inline_match and current_question:
                current_question["option_a"] = inline_match.group(1).strip()
                current_question["option_b"] = inline_match.group(2).strip()
                current_question["option_c"] = inline_match.group(3).strip()
                current_question["option_d"] = inline_match.group(4).strip()
                continue

            opt_a_match = re.match(r"^\s*\([aA]\)\s*(.*)", line_str)
            opt_b_match = re.match(r"^\s*\([bB]\)\s*(.*)", line_str)
            opt_c_match = re.match(r"^\s*\([cC]\)\s*(.*)", line_str)
            opt_d_match = re.match(r"^\s*\([dD]\)\s*(.*)", line_str)

            if opt_a_match and current_question:
                current_question["option_a"] = opt_a_match.group(1).strip()
            elif opt_b_match and current_question:
                current_question["option_b"] = opt_b_match.group(1).strip()
            elif opt_c_match and current_question:
                current_question["option_c"] = opt_c_match.group(1).strip()
            elif opt_d_match and current_question:
                current_question["option_d"] = opt_d_match.group(1).strip()
            else:
                if current_question and not current_question["option_a"]:
                    question_text_lines.append(line) # preserve raw spacing/newlines

        if current_question:
            current_question["question_text"] = "\n".join(question_text_lines).strip()
            questions.append(current_question)

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
