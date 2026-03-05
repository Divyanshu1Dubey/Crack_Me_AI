import os
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from questions.models import Subject, Topic, Question
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
    help = 'Import CMS questions directly from raw text files.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to a text file containing the questions')
        parser.add_argument('--year', type=int, default=2024, help='Year of the exam')
        parser.add_argument('--paper', type=int, default=1, help='Paper number (1 or 2)')

    def handle(self, *args, **options):
        file_path = options['file']
        year = options['year']
        paper = options['paper']

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f'File not found: {file_path}'))
            return
            
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            
        self.stdout.write(self.style.SUCCESS(f'\nParsing {file_path}...'))
        questions = self.detect_questions(text)
        
        self.stdout.write(self.style.SUCCESS(f'Detected {len(questions)} questions. Saving to database...'))
        saved = self.save_questions(questions, year, paper, os.path.basename(file_path))
        self.stdout.write(self.style.SUCCESS(f'Successfully imported {saved} questions!'))
            
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
                        correct_answer="A", # Default as it's not provided
                        subject=subject,
                        year=year,
                        paper=paper,
                        difficulty="medium",
                        source=f"TEXT_IMPORT_{source_file}"
                    )
                    saved += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error saving Q{q.get("number", "?")}: {e}'))
        return saved
