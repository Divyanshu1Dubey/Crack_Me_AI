import os
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from questions.models import Subject, Topic, Question
from ai_engine.document_processor import DocumentProcessor
import logging

logger = logging.getLogger(__name__)

# Common patterns for question detection in CMS PYQs
QUESTION_PATTERNS = [
    # "1." or "Q1." or "Q.1" or "1)" format
    r'(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,3})[.)]\s*(.+?)(?=(?:\n\s*(?:Q\.?\s*)?\d{1,3}[.)]|\Z))',
    # "Question 1:" format
    r'(?:^|\n)\s*Question\s+(\d{1,3})\s*[:.]\s*(.+?)(?=(?:\n\s*Question\s+\d{1,3}|\Z))',
]

OPTION_PATTERNS = [
    # "(a)" or "(A)" or "a)" or "A." format
    r'\(?\s*([a-dA-D])\s*[.)]\s*(.+?)(?=\(?\s*[a-dA-D]\s*[.)]|\Z)',
    # "a." or "A." format
    r'(?:^|\n)\s*([a-dA-D])\s*[.)]\s*(.+?)(?=(?:\n\s*[a-dA-D]\s*[.)]|\Z))',
]

class Command(BaseCommand):
    help = 'Import CMS questions directly from PYQ PDFs.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', type=str, help='Directory containing PYQ PDFs')

    def handle(self, *args, **options):
        # Default directory
        base_dir = options.get('dir')
        if not base_dir:
            from django.conf import settings
            base_dir = os.path.join(settings.BASE_DIR, 'Medura_Train', 'PYQ')
            
        if not os.path.exists(base_dir):
            self.stderr.write(self.style.ERROR(f'Directory not found: {base_dir}'))
            return
            
        processor = DocumentProcessor()
            
        pdf_files = [f for f in os.listdir(base_dir) if f.endswith('.pdf') and not f.startswith('Copy of')]
        
        self.stdout.write(self.style.SUCCESS(f'Found {len(pdf_files)} PYQ PDFs. Processing...'))
        
        total_saved = 0
        for pdf_name in pdf_files:
            pdf_path = os.path.join(base_dir, pdf_name)
            
            # Extract Year and Paper Number
            year_match = re.search(r'(20\d{2})', pdf_name)
            year = int(year_match.group(1)) if year_match else 2024
            
            paper_match = re.search(r'Paper\s*(\d)', pdf_name, re.IGNORECASE)
            paper = int(paper_match.group(1)) if paper_match else 1
            
            self.stdout.write(self.style.SUCCESS(f'\nReading {pdf_name}...'))
            pages = processor.extract_text(pdf_path)
            if not pages:
                self.stderr.write(self.style.WARNING(f'Could not extract text from {pdf_name}'))
                continue
                
            text = "\n".join([p["text"] for p in pages])
            questions = self.detect_questions(text)
            
            self.stdout.write(self.style.SUCCESS(f'Detected {len(questions)} questions. Saving to database...'))
            saved = self.save_questions(questions, year, paper, pdf_name)
            total_saved += saved
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {saved} questions from {pdf_name}'))
            
        self.stdout.write(self.style.SUCCESS(f'\nFinished! Total {total_saved} questions imported.'))

    def detect_questions(self, text):
        questions = []
        for pattern in QUESTION_PATTERNS:
            matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
            if len(matches) > 0:
                for q_num, q_text in matches:
                    q_text = q_text.strip()
                    options = self.extract_options(q_text)
                    if options:
                        question_text = q_text
                        for opt_letter, opt_text in options.items():
                            question_text = question_text.replace(opt_text, "").strip()
                            # Extra cleanup of options letter
                            question_text = re.sub(rf'\(?\s*{opt_letter}\s*[.)]\s*$', '', question_text, flags=re.IGNORECASE).strip()
                            
                        questions.append({
                            "number": int(q_num),
                            "text": question_text.strip(),
                            "options": options,
                        })
                if questions:
                    break
        return questions

    def extract_options(self, text):
        options = {}
        for pattern in OPTION_PATTERNS:
            matches = re.findall(pattern, text, re.DOTALL)
            if len(matches) >= 4:
                for letter, opt_text in matches[:4]:
                    options[letter.upper()] = opt_text.strip()
                break
        return options
        
    def save_questions(self, questions, year, paper, source_file):
        saved = 0
        subject = Subject.objects.first()
        for q in questions:
            try:
                if not q.get("text"): continue

                text_snippet = q["text"][:50]
                
                # Check if it already exists
                if not Question.objects.filter(year=year, question_text__icontains=text_snippet).exists():
                    Question.objects.create(
                        question_text=q["text"],
                        option_a=str(q.get("options", {}).get("A", "")),
                        option_b=str(q.get("options", {}).get("B", "")),
                        option_c=str(q.get("options", {}).get("C", "")),
                        option_d=str(q.get("options", {}).get("D", "")),
                        correct_answer="A", # Default
                        subject=subject,
                        year=year,
                        paper=paper,
                        difficulty="medium",
                        source=f"PDF_REGEX_{source_file}"
                    )
                    saved += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error saving Q{q.get("number", "?")}: {e}'))
        return saved
