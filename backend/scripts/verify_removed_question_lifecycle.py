"""Smoke-test the full RemovedQuestion lifecycle.

Run with:
    cd backend && python manage.py shell < scripts/verify_removed_question_lifecycle.py

Asserts:
  - remove_from_bank creates exactly one RemovedQuestion row per stem hash
  - id is idempotent on repeated remove (no duplicate tombstones)
  - unremove_from_bank deletes the tombstone AND restores the Question flags
  - A new question create with the same stem is BLOCKED by the import
    guard (is_removed) while the tombstone exists
  - After unremove, the import guard lets the question through again
"""
from django.contrib.auth import get_user_model

from questions.import_protection import is_removed
from questions.models import Question, RemovedQuestion, Subject, Topic, compute_stem_hash

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
if admin is None:
    raise SystemExit("No superuser found — create one first.")

print("=" * 60)
print("RemovedQuestion lifecycle smoke test")
print("=" * 60)

# Setup: create a disposable question.
subject = Subject.objects.first()
topic = Topic.objects.first()
stem = f"LIFECYCLE TEST {__import__('uuid').uuid4().hex[:12]}"
question = Question.objects.create(
    question_text=stem,
    option_a="A) foo",
    option_b="B) bar",
    option_c="C) baz",
    option_d="D) qux",
    correct_answer="A",
    subject=subject,
    topic=topic,
    year=2099,
    paper=99,
    difficulty="medium",
    exam_source="LIFECYCLE TEST",
    is_active=True,
)
print(f"Created Q{question.id}: stem={stem!r}")

stem_hash = compute_stem_hash(stem)
print(f"  stem_hash = {stem_hash[:16]}")

assert not is_removed(stem), "freshly-created question must NOT match tombstone"
print("  [OK] fresh question not in tombstones")

# Remove #1 — creates tombstone.
from questions.views import QuestionViewSet
view = QuestionViewSet()
view.kwargs = {}
view.request = type("R", (), {"user": admin, "data": {"reason": "lifecycle test"}})()
view.format_kwarg = None
view.get_object = lambda: question
removed1 = view.remove_from_bank(view.request, pk=question.id)
print(f"  remove_from_bank #1: {removed1.data}")
assert removed1.data["was_already_removed"] is False
assert question.is_active is False
assert question.is_dropped is True
assert question.admin_edited is True
print("  [OK] Q is_active=False, is_dropped=True, admin_edited=True")

# Tombstone exists
tombs = RemovedQuestion.objects.filter(question_text_hash=stem_hash)
assert tombs.count() == 1, f"expected 1 tombstone, got {tombs.count()}"
print(f"  [OK] 1 tombstone exists (id={tombs.first().id})")

# import guard blocks re-create
assert is_removed(stem), "import guard must block re-create of removed stem"
print("  [OK] is_removed() blocks re-import")

# Remove #2 — idempotent (returns same tombstone, flags unchanged)
question.refresh_from_db()
removed2 = view.remove_from_bank(view.request, pk=question.id)
print(f"  remove_from_bank #2: {removed2.data}")
assert removed2.data["was_already_removed"] is True
assert RemovedQuestion.objects.filter(question_text_hash=stem_hash).count() == 1, \
    "duplicate tombstones must NOT be created on repeated remove"
print("  [OK] repeated remove is idempotent")

# Unremove — deletes tombstone AND restores flags
question.refresh_from_db()
unremoved = view.unremove_from_bank(view.request, pk=question.id)
print(f"  unremove_from_bank: {unremoved.data}")
question.refresh_from_db()
assert question.is_active is True
assert question.is_dropped is False
assert question.admin_edited is False
assert RemovedQuestion.objects.filter(question_text_hash=stem_hash).count() == 0
assert not is_removed(stem), "after unremove, import guard must allow re-import"
print("  [OK] unremove restored flags and cleared tombstone")

# Re-remove to verify the round-trip
question.refresh_from_db()
view.get_object = lambda: question
removed3 = view.remove_from_bank(view.request, pk=question.id)
assert removed3.data["was_already_removed"] is False, \
    "after unremove, a fresh remove must create a NEW tombstone (not reuse old)"
print("  [OK] remove → unremove → remove round-trip works")

# Cleanup
RemovedQuestion.objects.filter(question_text_hash=stem_hash).delete()
question.delete()
print()
print("All lifecycle checks PASSED ✓")