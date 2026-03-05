import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
django.setup()

from questions.models import Question, Subject, Topic

print(f"Questions: {Question.objects.count()}")
print(f"Subjects: {Subject.objects.count()}")
print(f"Topics: {Topic.objects.count()}")

for s in Subject.objects.all():
    qc = Question.objects.filter(subject=s).count()
    print(f"  {s.name} ({s.code}): {qc} questions")

q = Question.objects.first()
if q:
    print(f"\nSample Q id={q.id}:")
    print(f"  text: {q.question_text[:100]}")
    print(f"  opt_a: '{q.option_a[:60]}'" if q.option_a else "  opt_a: EMPTY")
    print(f"  opt_b: '{q.option_b[:60]}'" if q.option_b else "  opt_b: EMPTY")
    print(f"  opt_c: '{q.option_c[:60]}'" if q.option_c else "  opt_c: EMPTY")
    print(f"  opt_d: '{q.option_d[:60]}'" if q.option_d else "  opt_d: EMPTY")
    print(f"  answer: {q.correct_answer}")
    print(f"  year: {q.year}, paper: {q.paper}")
else:
    print("No questions in DB")

# Check RAG stats
try:
    from ai_engine.rag_pipeline import RAGPipeline
    rag = RAGPipeline()
    stats = rag.get_stats()
    print(f"\nRAG Stats: {stats}")
except Exception as e:
    print(f"\nRAG Error: {e}")

# Check analytics model
from analytics.models import DailyActivity
print(f"\nDailyActivity fields: {[f.name for f in DailyActivity._meta.get_fields()]}")
