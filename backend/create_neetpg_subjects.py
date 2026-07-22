"""One-shot: create missing Subject rows for NEET PG subject catalogue.

The CMS-only Subject list has 5 rows. NEET PG needs 19. We add the
missing 14 (Anatomy, Physiology, Biochemistry, Pathology, Microbiology,
Pharmacology, FMT, Ophthalmology, ENT, Dermatology, Orthopaedics,
Anaesthesia, Radiodiagnosis, Psychiatry) and leave the existing 5
untouched.

Idempotent: skips rows that already exist by name.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Subject

# (Display name, code, exam_track)
NEET_SUBJECTS = [
    ("Anatomy", "ANA"),
    ("Physiology", "PHY"),
    ("Biochemistry", "BCH"),
    ("Pathology", "PTH"),
    ("Microbiology", "MIC"),
    ("Pharmacology", "PHM"),
    ("Forensic Medicine", "FMT"),
    ("Ophthalmology", "OPH"),
    ("ENT", "ENT"),
    ("Dermatology", "DER"),
    ("Orthopaedics", "ORT"),
    ("Anaesthesia", "ANS"),
    ("Radiodiagnosis", "RAD"),
    ("Psychiatry", "PSY"),
]

created = 0
skipped = 0
for name, code in NEET_SUBJECTS:
    obj, was_created = Subject.objects.get_or_create(
        name=name,
        defaults={"code": code, "exam_type": "neet_pg"},
    )
    if was_created:
        created += 1
        print(f"  + Created: id={obj.id} {name} ({code})")
    else:
        skipped += 1
        print(f"  - Exists:  id={obj.id} {name} ({code})")

print(f"\nCreated {created} subjects, {skipped} already existed")
print(f"Total Subject rows: {Subject.objects.count()}")