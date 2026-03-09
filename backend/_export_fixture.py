"""Export questions app data to a UTF-8 JSON fixture."""
import os
import sys

import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.core import serializers

from questions.models import Subject, Topic, Question

# Serialize all objects required for question bank runtime.
subjects = list(Subject.objects.all())
topics = list(Topic.objects.all())
questions = list(Question.objects.all())

all_objects = subjects + topics + questions
data = serializers.serialize('json', all_objects, indent=2)

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'questions_fixture.json')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(data)

print(f"Exported {len(subjects)} subjects, {len(topics)} topics, {len(questions)} questions")
print(f"Saved to {output_path}")
