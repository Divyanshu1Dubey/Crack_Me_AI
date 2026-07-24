import django, os, shutil
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()
from django.conf import settings
from questions.models import Question

qs = Question.objects.filter(page_screenshot__contains='recall_images/2026/07/recall_images/')
print(f'Questions with bad paths: {qs.count()}')
for q in qs:
    bad_str = str(q.page_screenshot) if q.page_screenshot else ''
    print(f'  Q{q.id} page={q.page_number} path={bad_str}')
    bad_path = Path(settings.MEDIA_ROOT) / bad_str
    fname = bad_path.name
    if bad_path.exists():
        sha16 = fname.replace('.png', '').replace('.jpeg', '').replace('.jpg', '')[:2]
        correct = Path(settings.MEDIA_ROOT) / 'recall_images' / sha16 / fname
        correct.parent.mkdir(parents=True, exist_ok=True)
        if not correct.exists():
            shutil.copy2(bad_path, correct)
            print(f'    copied -> {correct.relative_to(settings.MEDIA_ROOT)}')
        rel = str(correct.relative_to(settings.MEDIA_ROOT)).replace('\\', '/')
        q.page_screenshot = rel
        q.save(update_fields=['page_screenshot'])
        print(f'    updated page_screenshot -> {q.page_screenshot}')
print('Done.')
