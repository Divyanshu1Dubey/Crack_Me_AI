"""Export large tables using Django ORM with batch processing.

    python scripts/_export_questions.py --output-dir <directory outside the repository>

Same location rule as the other backup scripts (scripts/_safe_paths.py): the
dumps of this folder hold user data, so they never go inside the checkout
(this one used to write ../backup/db_dumps).
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _safe_paths import output_dir_from_argv  # noqa: E402

OUTPUT_DIR = output_dir_from_argv(description=__doc__.splitlines()[0])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
import django  # noqa: E402
django.setup()

from django.apps import apps  # noqa: E402

def export_model(app_label, model_name, batch_size=500):
    """Export a model in batches to avoid memory issues."""
    Model = apps.get_model(app_label, model_name)
    total = Model.objects.count()
    print(f"{app_label}.{model_name}: {total} rows", flush=True)

    all_objects = []
    offset = 0
    while offset < total:
        batch = list(Model.objects.all()[offset:offset + batch_size])
        if not batch:
            break
        all_objects.extend(batch)
        offset += batch_size
        if offset % 5000 == 0 or offset >= total:
            print(f"  ... loaded {offset}/{total}", flush=True)

    # Serialize using Django's serializers
    from django.core import serializers
    data = serializers.serialize('json', all_objects)

    fname = OUTPUT_DIR / f'{app_label}.{model_name}.json'
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(data)
    size_kb = len(data) / 1024
    print(f"  -> saved {fname} ({size_kb:.1f} KB)", flush=True)
    return total

# Export questions table (the big one - 13,788 rows)
total = export_model('questions', 'Question')
print(f"\nDone: {total} questions exported successfully")
