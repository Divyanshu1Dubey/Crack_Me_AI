"""
Django management command to import PYQ questions from PDF files.
Usage: python manage.py import_pyqs [--dry-run] [--year YEAR]
"""
import os
import re
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from questions.models import Subject, Topic, Question
from ai_engine.pyq_extractor import PYQExtractor

logger = logging.getLogger(__name__)

# Subject mapping for UPSC CMS
SUBJECT_MAP = {
    "General Medicine": "MED",
    "Medicine": "MED",
    "Pediatrics": "PED",
    "Paediatrics": "PED",
    "Surgery": "SUR",
    "Obstetrics & Gynaecology": "OBG",
    "Obstetrics and Gynaecology": "OBG",
    "OBG": "OBG",
    "Gynaecology": "OBG",
    "Obstetrics": "OBG",
    "Preventive & Social Medicine": "PSM",
    "Preventive and Social Medicine": "PSM",
    "PSM": "PSM",
    "Community Medicine": "PSM",
}


class Command(BaseCommand):
    help = "Import PYQ questions from PDF files in Medura_Train/PYQ/"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Parse PDFs but don't save to database")
        parser.add_argument("--year", type=int,
                            help="Only process a specific year")
        parser.add_argument("--dir", type=str,
                            help="Custom PYQ directory path")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        target_year = options.get("year")
        custom_dir = options.get("dir")

        # Find PYQ directory
        pyq_dir = custom_dir or os.path.join(
            settings.BASE_DIR, "Medura_Train", "PYQ"
        )

        if not os.path.exists(pyq_dir):
            self.stderr.write(self.style.ERROR(f"PYQ directory not found: {pyq_dir}"))
            return

        # Get PDF files (skip "Copy of" duplicates)
        pdf_files = sorted([
            f for f in os.listdir(pyq_dir)
            if f.endswith(".pdf") and not f.startswith("Copy of")
        ])

        if not pdf_files:
            self.stderr.write(self.style.ERROR("No PDF files found"))
            return

        self.stdout.write(self.style.SUCCESS(f"\n📄 Found {len(pdf_files)} PYQ PDFs"))
        for f in pdf_files:
            self.stdout.write(f"  • {f}")

        # Filter by year if specified
        if target_year:
            pdf_files = [f for f in pdf_files if str(target_year) in f]
            self.stdout.write(f"\n🔍 Filtered to year {target_year}: {len(pdf_files)} files")

        # Ensure subjects exist
        self._ensure_subjects()

        # Initialize extractor
        extractor = PYQExtractor()

        total_imported = 0
        total_errors = 0

        for pdf_file in pdf_files:
            pdf_path = os.path.join(pyq_dir, pdf_file)
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(self.style.HTTP_INFO(f"Processing: {pdf_file}"))

            try:
                questions = extractor.extract_from_pdf(pdf_path)
                self.stdout.write(f"  Extracted {len(questions)} questions")

                if dry_run:
                    for q in questions[:3]:  # Show first 3 as sample
                        self.stdout.write(f"\n  Q{q.get('number', '?')}: {q.get('question_text', '')[:100]}...")
                        self.stdout.write(f"    Answer: {q.get('correct_answer', '?')}")
                        self.stdout.write(f"    Subject: {q.get('subject', '?')}")
                    if len(questions) > 3:
                        self.stdout.write(f"  ... and {len(questions) - 3} more")
                    total_imported += len(questions)
                    continue

                # Save to database
                saved = self._save_questions(questions, pdf_file)
                total_imported += saved
                self.stdout.write(self.style.SUCCESS(f"  ✅ Saved {saved} questions"))

            except Exception as e:
                total_errors += 1
                self.stderr.write(self.style.ERROR(f"  ❌ Error: {e}"))
                logger.exception(f"Failed to process {pdf_file}")

        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(
            f"\n📊 Import Summary:"
            f"\n  Total questions: {total_imported}"
            f"\n  Errors: {total_errors}"
            f"\n  Mode: {'DRY RUN' if dry_run else 'IMPORTED'}"
        ))

    def _ensure_subjects(self):
        """Ensure all UPSC CMS subjects exist in database."""
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

    def _save_questions(self, questions: list[dict], source_file: str) -> int:
        """Save extracted questions to the database."""
        saved = 0

        for q in questions:
            try:
                # Map subject
                subject_name = q.get("subject", "General Medicine")
                subject_code = SUBJECT_MAP.get(subject_name, "MED")
                subject = Subject.objects.filter(code=subject_code).first()
                if not subject:
                    subject = Subject.objects.first()

                # Find or create topic
                topic_name = q.get("topic", "General")
                topic = None
                if topic_name and subject:
                    topic, _ = Topic.objects.get_or_create(
                        name=topic_name,
                        subject=subject,
                        defaults={"description": f"{topic_name} - {subject.name}"}
                    )

                year = q.get("year", 0)
                q_text = q.get("question_text", "").strip()

                if not q_text or len(q_text) < 10:
                    continue

                # Check for duplicate (same year + similar text)
                if Question.objects.filter(
                    year=year,
                    question_text__icontains=q_text[:50]
                ).exists():
                    continue

                # Create question
                question = Question.objects.create(
                    question_text=q_text,
                    option_a=q.get("option_a", ""),
                    option_b=q.get("option_b", ""),
                    option_c=q.get("option_c", ""),
                    option_d=q.get("option_d", ""),
                    correct_answer=q.get("correct_answer", ""),
                    explanation=q.get("explanation", ""),
                    mnemonic=q.get("mnemonic", ""),
                    subject=subject,
                    topic=topic,
                    year=year,
                    paper=q.get("paper", 0),
                    difficulty=q.get("difficulty", "medium"),
                    concept_tags=q.get("concept_tags", []),
                    source=f"PYQ_{source_file}",
                    book_name=q.get("book_reference", ""),
                )
                saved += 1

            except Exception as e:
                logger.error(f"Failed to save Q{q.get('number', '?')}: {e}")

        return saved
