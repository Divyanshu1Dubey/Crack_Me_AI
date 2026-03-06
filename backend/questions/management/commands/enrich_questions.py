from django.core.management.base import BaseCommand
from django.db.models import Q
from questions.models import Question, Topic, Subject
from ai_engine.services import AIService
import json
import time

class Command(BaseCommand):
    help = 'Enrich questions with missing correct_answer, topic, and explanation using AI.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100, help='Limit the number of questions to process per run.')
        parser.add_argument('--batch-size', type=int, default=10, help='AIService batch size (not used yet).')

    def handle(self, *args, **options):
        limit = options['limit']
        ai_service = AIService()
        
        # Priority 1: Missing correct_answer
        # Priority 2: Missing topic
        # Priority 3: Missing explanation
        questions = Question.objects.filter(
            Q(correct_answer='') | Q(topic__isnull=True) | Q(explanation='')
        )[:limit]

        if not questions.exists():
            self.stdout.write(self.style.SUCCESS('No questions to enrich!'))
            return

        self.stdout.write(f"Starting enrichment for {questions.count()} questions...")

        processed = 0
        for q in questions:
            try:
                self.stdout.write(f"Processing Q{q.id}: {q.question_text[:50]}...")
                
                prompt = f"""Identify the correct answer and topic for this UPSC CMS question.
Subject: {q.subject.name}
Question: {q.question_text}
Options:
  A: {q.option_a}
  B: {q.option_b}
  C: {q.option_c}
  D: {q.option_d}

Respond ONLY with raw JSON:
{{
  "correct_answer": "A/B/C/D",
  "topic_name": "Specific medical topic name",
  "difficulty": "easy/medium/hard",
  "explanation": "Brief explanation",
  "concept_tags": ["tag1", "tag2"]
}}"""

                # Call AI
                raw_res = ai_service._call_ai(prompt, system="You are a medical data entry assistant. Be precise.", temperature=0.1)
                
                # Parse JSON
                import re
                match = re.search(r'\{.*\}', raw_res, re.DOTALL)
                if not match:
                    self.stdout.write(self.style.ERROR(f"Fail to find JSON for Q{q.id}"))
                    continue
                
                data = json.loads(match.group(0))
                
                # Update Correct Answer
                if not q.correct_answer and data.get('correct_answer'):
                    q.correct_answer = data['correct_answer'].strip().upper()[:1]

                # Update Topic
                topic_name = data.get('topic_name')
                if topic_name and not q.topic:
                    topic, created = Topic.objects.get_or_create(
                        subject=q.subject,
                        name=topic_name
                    )
                    q.topic = topic
                
                # Update Explanation
                if not q.explanation and data.get('explanation'):
                    q.explanation = data['explanation']
                
                # Update difficulty
                if data.get('difficulty'):
                    q.difficulty = data['difficulty']
                    
                # Update tags
                if data.get('concept_tags'):
                    q.concept_tags = data['concept_tags']

                q.save()
                processed += 1
                self.stdout.write(self.style.SUCCESS(f"Saved Q{q.id}"))
                
                # Small sleep to be nice to APIs
                time.sleep(0.5)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error on Q{q.id}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully enriched {processed} questions."))
