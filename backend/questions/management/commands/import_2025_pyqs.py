import os
import re
import json
import time
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from questions.models import Subject, Topic, Question
from ai_engine.services import AIService

logger = logging.getLogger(__name__)

SUBJECT_MAP = {
    "General Medicine": "MED",
    "Pediatrics": "PED",
    "Surgery": "SUR",
    "Obstetrics & Gynaecology": "OBG",
    "Preventive & Social Medicine": "PSM",
}

class Command(BaseCommand):
    help = "Parse, import, and enrich UPSC CMS 2025 PYQ questions from the raw text file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=os.path.join("pyq", "2025"),
            help="Path to the 2025 questions text file relative to backend directory",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse file and show count without saving to database",
        )
        parser.add_argument(
            "--enrich",
            action="store_true",
            help="Enrich imported questions using AI service (solve correct answers and generate explanations)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of questions to process/enrich (0 for all)",
        )
        parser.add_argument(
            "--start",
            type=int,
            default=0,
            help="Index of the question to start processing/enriching from",
        )
        parser.add_argument(
            "--sleep-ms",
            type=int,
            default=300,
            help="Delay in milliseconds between AI service calls",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        dry_run = options["dry_run"]
        enrich = options["enrich"]
        limit = options["limit"]
        start_idx = options["start"]
        sleep_ms = options["sleep_ms"]

        # 1. Parse raw text file
        self.stdout.write(self.style.SUCCESS(f"Reading file from: {file_path}"))
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.getcwd(), file_path)

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        questions = self._parse_lines(lines)
        self.stdout.write(self.style.SUCCESS(f"Successfully parsed {len(questions)} questions from file."))

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run mode: showing parsed samples."))
            for i, q in enumerate(questions[:3]):
                self.stdout.write(f"\n[{i+1}] Paper {q['paper']} | {q['subject']} | Q{q['number']}")
                self.stdout.write(f"Text: {q['question_text'][:100]}...")
                self.stdout.write(f"A) {q['option_a']}")
                self.stdout.write(f"B) {q['option_b']}")
                self.stdout.write(f"C) {q['option_c']}")
                self.stdout.write(f"D) {q['option_d']}")
            return

        # 2. Ensure subjects exist
        self._ensure_subjects()

        # 3. Save questions to database
        saved_count = 0
        duplicate_count = 0
        db_questions = []

        with transaction.atomic():
            for q_data in questions:
                # Find/Create subject
                sub_code = SUBJECT_MAP.get(q_data["subject"], "MED")
                subject = Subject.objects.filter(code=sub_code).first()
                if not subject:
                    self.stderr.write(self.style.ERROR(f"Subject not found: {q_data['subject']}"))
                    continue

                # Find or create a generic Topic
                topic, _ = Topic.objects.get_or_create(
                    name="General",
                    subject=subject,
                    defaults={"importance": 5, "description": f"General topic for {subject.name}"}
                )

                # Check for duplicate using full text to avoid false positives on similar prefixes
                existing_q = Question.objects.filter(
                    year=2025,
                    subject=subject,
                    question_text=q_data["question_text"]
                ).first()

                if existing_q:
                    duplicate_count += 1
                    db_questions.append(existing_q)
                else:
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
                        year=2025,
                        paper=q_data["paper"],
                        difficulty="medium",
                        source=f"PYQ_2025_Paper{q_data['paper']}.txt"
                    )
                    saved_count += 1
                    db_questions.append(new_q)

        self.stdout.write(self.style.SUCCESS(f"Database sync complete. Saved: {saved_count}, Duplicates found/skipped: {duplicate_count}"))

        # 4. Enrich questions if requested
        if enrich:
            ai_service = AIService()
            self.stdout.write(self.style.SUCCESS("AI Service initialized. Beginning enrichment..."))
            
            # Filter questions to be processed
            to_process = db_questions[start_idx:]
            if limit > 0:
                to_process = to_process[:limit]

            self.stdout.write(self.style.HTTP_INFO(f"Enriching {len(to_process)} questions starting from index {start_idx}..."))
            
            enriched_count = 0
            for idx, q in enumerate(to_process):
                global_idx = start_idx + idx
                self.stdout.write(f"[{global_idx+1}/{len(db_questions)}] Enriching Q{q.id} (Year: {q.year}, Subject: {q.subject.name})...")
                
                success = self._enrich_question(q, ai_service)
                if success:
                    enriched_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  -> Q{q.id} enriched successfully! Ans: {q.correct_answer}, Topic: {q.topic.name}"))
                else:
                    self.stdout.write(self.style.WARNING(f"  -> Q{q.id} enrichment skipped or failed."))
                
                if idx < len(to_process) - 1:
                    time.sleep(sleep_ms / 1000.0)

            self.stdout.write(self.style.SUCCESS(f"Enrichment session finished. Successfully enriched {enriched_count} questions."))

    def _parse_lines(self, lines):
        questions = []
        current_paper = 1
        current_subject = "General Medicine"
        
        current_question = None
        question_text_lines = []
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
                
            # Detect paper
            if "PAPER 1" in line_str or "PAPER I" in line_str:
                current_paper = 1
                continue
            elif "PAPER 2" in line_str or "PAPER II" in line_str:
                current_paper = 2
                continue
                
            # Detect subject headers
            if "GENERAL MEDICINE" in line_str and ("Q1" in line_str or "Q96" in line_str or "(Q" in line_str):
                current_subject = "General Medicine"
                continue
            elif "PEDIATRICS" in line_str:
                current_subject = "Pediatrics"
                continue
            elif "SURGERY" in line_str:
                current_subject = "Surgery"
                continue
            elif "GYNAECOLOGY" in line_str or "OBSTETRICS" in line_str:
                current_subject = "Obstetrics & Gynaecology"
                continue
            elif "PREVENTIVE & SOCIAL MEDICINE" in line_str or "PREVENTIVE" in line_str:
                current_subject = "Preventive & Social Medicine"
                continue
                
            # Check for question start
            q_match = re.match(r"^Q(\d+)\.\s*(.*)", line_str)
            if q_match:
                if current_question:
                    current_question["question_text"] = "\n".join(question_text_lines).strip()
                    questions.append(current_question)
                q_num = int(q_match.group(1))
                q_text_start = q_match.group(2)
                current_question = {
                    "number": q_num,
                    "question_text": "",
                    "option_a": "",
                    "option_b": "",
                    "option_c": "",
                    "option_d": "",
                    "paper": current_paper,
                    "subject": current_subject,
                    "year": 2025
                }
                question_text_lines = [q_text_start]
                continue
                
            # Check for options
            opt_a_match = re.match(r"^\([aA]\)\s*(.*)", line_str)
            opt_b_match = re.match(r"^\([bB]\)\s*(.*)", line_str)
            opt_c_match = re.match(r"^\([cC]\)\s*(.*)", line_str)
            opt_d_match = re.match(r"^\([dD]\)\s*(.*)", line_str)
            
            if opt_a_match and current_question:
                current_question["option_a"] = opt_a_match.group(1).strip()
                continue
            elif opt_b_match and current_question:
                current_question["option_b"] = opt_b_match.group(1).strip()
                continue
            elif opt_c_match and current_question:
                current_question["option_c"] = opt_c_match.group(1).strip()
                continue
            elif opt_d_match and current_question:
                current_question["option_d"] = opt_d_match.group(1).strip()
                continue
                
            if current_question and not current_question["option_a"]:
                question_text_lines.append(line_str)
                
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
        # Check if already fully enriched
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
            
            # Clean json output in case AI added markdown blocks
            match = re.search(r"\{.*\}", raw or "", re.DOTALL)
            if not match:
                return False
            clean_json = match.group(0)
            # Remove trailing commas before closing braces/brackets
            clean_json = re.sub(r',\s*([\]\}])', r'\1', clean_json)
            payload = json.loads(clean_json)
        except Exception as e:
            logger.warning(f"AI enrichment failed for Q{q.id}: {e}")
            return False

        # Apply results
        answer = str(payload.get("correct_answer", "")).strip().upper()[:1]
        if answer in {"A", "B", "C", "D"}:
            q.correct_answer = answer

        diff = str(payload.get("difficulty", "")).strip().lower()
        if diff in {"easy", "medium", "hard"}:
            q.difficulty = diff

        topic_name = str(payload.get("topic_name", "")).strip()
        if topic_name:
            topic, _ = Topic.objects.get_or_create(
                subject=q.subject,
                name=topic_name,
                defaults={"importance": 5, "description": f"{topic_name} under {q.subject.name}"}
            )
            q.topic = topic

        q.explanation = str(payload.get("explanation", "")).strip()
        q.concept_explanation = str(payload.get("concept_explanation", "")).strip()
        q.mnemonic = str(payload.get("mnemonic", "")).strip()
        
        tags = payload.get("concept_tags", [])
        if isinstance(tags, list):
            q.concept_tags = [str(t).strip().lower() for t in tags if str(t).strip()]

        q.save()
        return True
