import os
import re
import json
import time
import logging
import fitz  # PyMuPDF
from django.core.management.base import BaseCommand
from django.db import transaction
from questions.models import Subject, Topic, Question
from ai_engine.services import AIService

logger = logging.getLogger(__name__)

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

class Command(BaseCommand):
    help = "Parse and import NEET PG questions into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--enrich",
            action="store_true",
            help="Enrich questions using AIService (solve correct answers and generate explanations)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of questions to enrich (0 for all)",
        )

    def handle(self, *args, **options):
        enrich = options["enrich"]
        limit = options["limit"]

        # Paths
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        txt_path = os.path.join(base_dir, "pyq", "Neet-PG", "2025")
        pdf_path = os.path.join(base_dir, "pyq", "Neet-PG", "neet_pg_2020_question_paper_with_answer_key_pdfs_january_5questions.pdf")

        # 1. Clean existing NEET PG questions to prevent duplicate pollution
        self.stdout.write("Cleaning existing NEET PG questions...")
        deleted_count, _ = Question.objects.filter(exam_source="NEET PG").delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} old NEET PG questions."))

        # Initialize subjects
        self._ensure_subjects()

        # 2. Parse & Import 2025 Text questions (28 MCQs)
        self.stdout.write("\nParsing NEET PG 2025 text file...")
        parsed_2025 = []
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()
            parsed_2025 = self._parse_2025_text(content)
            self.stdout.write(self.style.SUCCESS(f"Parsed {len(parsed_2025)} questions from NEET PG 2025 text file."))
        else:
            self.stderr.write(f"NEET PG 2025 text file not found at: {txt_path}")

        # 3. Parse & Import 2020 PDF questions (299 MCQs)
        self.stdout.write("\nParsing NEET PG 2020 PDF file...")
        parsed_2020 = []
        if os.path.exists(pdf_path):
            doc = fitz.open(pdf_path)
            full_pdf_text = ""
            for page in doc:
                full_pdf_text += page.get_text() + "\n"
            doc.close()
            parsed_2020 = self._parse_2020_pdf(full_pdf_text)
            self.stdout.write(self.style.SUCCESS(f"Parsed {len(parsed_2020)} questions from NEET PG 2020 PDF file."))
        else:
            self.stderr.write(f"NEET PG 2020 PDF file not found at: {pdf_path}")

        # 4. Save to Database
        ai_service = AIService() if enrich else None
        saved_2025 = self._save_questions(parsed_2025, 2025, NEET_PG_2025_ANSWERS, ai_service, limit)
        saved_2020 = self._save_questions(parsed_2020, 2020, {}, ai_service, limit)

        self.stdout.write(self.style.SUCCESS(f"\nImport Finished!"))
        self.stdout.write(f"  • NEET PG 2025 saved: {saved_2025}")
        self.stdout.write(f"  • NEET PG 2020 saved: {saved_2020}")

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

    def _parse_2025_text(self, text):
        questions = []
        # Pattern for Q1., Q2., etc.
        pattern = r'(?:^|\n)\s*Q(\d+)\.\s+(.+?)\s+\(?a\)?\s+(.+?)\s+\(?b\)?\s+(.+?)\s+\(?c\)?\s+(.+?)\s+\(?d\)?\s+(.+?)(?=\n\s*Q\d+\.|\Z)'
        matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
        for num_str, q_text, opt_a, opt_b, opt_c, opt_d in matches:
            questions.append({
                "number": int(num_str),
                "question_text": q_text.strip(),
                "option_a": opt_a.strip(),
                "option_b": opt_b.strip(),
                "option_c": opt_c.strip(),
                "option_d": opt_d.strip(),
            })
        return questions

    def _parse_2020_pdf(self, text):
        questions = []
        # Pattern for 1., 2., etc. with (A), (B), (C), (D) options
        pattern = r'(\d+)\.\s+(.+?)\s+\(?A\)?\s+(.+?)\s+\(?B\)?\s+(.+?)\s+\(?C\)?\s+(.+?)\s+\(?D\)?\s+(.+?)(?=\n\s*\d+\.|\Z)'
        matches = re.findall(pattern, text, re.DOTALL)
        for num_str, q_text, opt_a, opt_b, opt_c, opt_d in matches:
            # Clean up page footer noise in question text
            clean_q = re.sub(r'Page\s+\d+\s+of\s+\d+|This\s+question\s+paper\s+contains.*', '', q_text, flags=re.IGNORECASE).strip()
            questions.append({
                "number": int(num_str),
                "question_text": clean_q,
                "option_a": opt_a.strip(),
                "option_b": opt_b.strip(),
                "option_c": opt_c.strip(),
                "option_d": opt_d.strip(),
            })
        return questions

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

    def _save_questions(self, parsed_questions, year, answer_map, ai_service, enrich_limit):
        saved = 0
        enriched_count = 0

        for idx, q in enumerate(parsed_questions):
            subject_name = self._classify_subject(q["question_text"])
            sub_code = SUBJECT_CODES[subject_name]
            subject = Subject.objects.get(code=sub_code)

            # Find/create topic
            topic, _ = Topic.objects.get_or_create(
                name="General",
                subject=subject,
                defaults={"importance": 5, "description": f"General topic for {subject.name}"}
            )

            # Determine correct answer
            correct_ans = answer_map.get(q["number"], "A")  # Default to A or mapped answer
            explanation = "Reference: NEET PG previous year question bank."

            # Call AI service for enrichment if requested and within limit
            if ai_service and (enrich_limit == 0 or enriched_count < enrich_limit):
                self.stdout.write(f"  -> Querying AI for Q{q['number']} ({year})...")
                options_dict = {
                    "A": q["option_a"],
                    "B": q["option_b"],
                    "C": q["option_c"],
                    "D": q["option_d"]
                }
                ai_ans = ai_service.get_consensus_answer(q["question_text"], options_dict)
                if ai_ans:
                    correct_ans = ai_ans
                    self.stdout.write(f"     ✅ AI determined correct option: {ai_ans}")
                
                # Get explanation from AI
                ai_exp = ai_service.explain_after_answer(
                    q["question_text"],
                    options=options_dict,
                    correct_answer=correct_ans
                )
                if ai_exp:
                    explanation = ai_exp
                
                enriched_count += 1
                time.sleep(0.5)

            # Save question
            Question.objects.create(
                question_text=q["question_text"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                correct_answer=correct_ans,
                explanation=explanation,
                subject=subject,
                topic=topic,
                year=year,
                paper=1,
                difficulty="medium",
                exam_source="NEET PG",
                source=f"NEET_PG_{year}_IMPORT"
            )
            saved += 1

        return saved
