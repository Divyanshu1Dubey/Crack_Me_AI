import os
from pathlib import Path
from django.core.management.base import BaseCommand
from questions.models import Subject, Topic, Question
from ai_engine.rag_pipeline import RAGPipeline
from ai_engine.pyq_extractor import PYQExtractor
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process CMS PYQ PDFs: extract text for RAG and parse questions for DB.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Path to a specific PDF file')
        parser.add_argument('--dir', type=str, help='Directory containing PDF files')

    def handle(self, *args, **options):
        file_path = options.get('file')
        dir_path = options.get('dir')

        if not file_path and not dir_path:
            self.stderr.write(self.style.ERROR('Please provide either --file or --dir'))
            return
            
        files_to_process = []
        if file_path:
            files_to_process.append(file_path)
        if dir_path:
            for f in os.listdir(dir_path):
                if f.endswith('.pdf'):
                    files_to_process.append(os.path.join(dir_path, f))
                    
        rag = RAGPipeline()
        extractor = PYQExtractor()

        for pdf_path in files_to_process:
            self.stdout.write(self.style.SUCCESS(f'\nProcessing {pdf_path}...'))
            
            # 1. RAG Ingestion
            self.stdout.write('Step 1: Ingesting into Knowledge Base (RAG)...')
            try:
                chunks = rag.index_textbook(pdf_path, chunk_size=300)
                self.stdout.write(self.style.SUCCESS(f'Successfully indexed {chunks} chunks into RAG.'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'RAG Error: {e}'))
                
            # 2. Extract Questions
            self.stdout.write('Step 2: Extracting multiple-choice questions...')
            try:
                questions = extractor.extract_from_pdf(pdf_path)
                saved = self._save_questions(questions, Path(pdf_path).name)
                self.stdout.write(self.style.SUCCESS(f'Successfully saved {saved} questions to Question Bank.'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Extraction Error: {e}'))
                
    def _save_questions(self, questions, source_name):
        saved = 0
        for q in questions:
            try:
                subject_name = q.get("subject", "General Medicine")
                subject = Subject.objects.filter(name__icontains=subject_name).first()
                if not subject:
                    subject = Subject.objects.first()

                topic = None
                topic_name = q.get("topic", "General")
                if topic_name and subject:
                    topic, _ = Topic.objects.get_or_create(
                        name=topic_name[:100], subject=subject
                    )

                if not q.get("question_text"): continue

                text_snippet = q["question_text"][:50]
                year = q.get("year", 2024)
                
                # Deduplication logic
                if not Question.objects.filter(year=year, question_text__icontains=text_snippet).exists():
                    Question.objects.create(
                        question_text=q["question_text"],
                        option_a=str(q.get("option_a", "")),
                        option_b=str(q.get("option_b", "")),
                        option_c=str(q.get("option_c", "")),
                        option_d=str(q.get("option_d", "")),
                        correct_answer=q.get("correct_answer", "A"),
                        subject=subject,
                        topic=topic,
                        year=year,
                        paper=q.get("paper", 1),
                        difficulty=q.get("difficulty", "medium"),
                        explanation=q.get("explanation", ""),
                        source=source_name
                    )
                    saved += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error saving Q{q.get("number", "?")}: {e}'))
        return saved
