# Mock Test Architecture — CrackLabs

> Authoritative design doc for the entire mock-test system. Combines the existing `tests_engine` Django app with the new `material_importer.mock_test_builder` pipeline and outlines the missing pieces.

---

## 1. Goals

1. **Auto-tests** for every imported material batch (subject/topic/PYQ/mixed). — *shipped via `mock_test_builder.build_for_batch()`.*
2. **Admin-curated tests** for grand tests, institute exams, image-only tests. — *partial; see §4.*
3. **Scheduled tests** that fire on a calendar (daily, weekly, exam window). — *gap; design in §5.*
4. **Adaptive tests** that re-rank remaining questions by student weakness. — *gap; design in §6.*
5. **Leaderboard + rank** with anti-cheat heuristics. — *partial; see §7.*
6. **AI-generated mock tests** for any (subject, topic, count) tuple. — *gap; design in §8.*
7. **Per-folder mock tests** so DOCX folders create tests automatically. — *shipped via DOCX path; see §9.*

---

## 2. Current state of `tests_engine` (verified)

The `tests_engine` Django app already provides:

| Test type (`test_type` enum) | Status |
|---|---|
| `subject`, `topic`, `mixed`, `paper1`, `paper2`, `daily`, `pyq_year`, `weak`, `adaptive` | All listed in `tests_engine.models.Test.test_type` |
| `TestAttempt`, `QuestionResponse` | Present; one-active-attempt constraint + resume in-flight (commit `2c66939`) |
| `negative_marking`, `time_limit_minutes` | Implemented |
| `is_published`, `version` | Implemented; respect the `is_published` overwrite fix (BUG-001) when re-running `mock_test_builder` |

`mock_test_builder.build_for_batch(batch_id)` produces:

- One `subject`-typed Test per inferred subject
- One `topic`-typed Test per (subject, topic)
- One `pyq_year`-typed Test per PYQ year found in filenames
- One `mixed`-typed Test omnibus

All seeded with at most `max_per_test` (default 100) `published_question`-linked rows.

---

## 3. Folder → mock pipeline (recommended)

```
+-------------------------------------+
| Admin drag-and-drops a folder of    |
|   <exam>/<subject>/<topic>/*.docx   |
+--------------------+----------------+
                     v
        material_importer.ingest_path()
                     |
                     v
   +-----------------+-----------------+
   | ImportBatch, ImportMaterial       |
   | ExtractedQuestion (pending/...)   |
   +-----------------+-----------------+
                     |
                     v
   +-----------+ admin curate +----------+
   | mark approved, publish_to_questions |
   +-----------------+-------------------+
                     |
                     v
   mock_test_builder.build_for_batch()
                     |
                     v
   +-----------+ auto-generated Test rows
```

**Future**: add a `--auto-build-tests` flag to `ingest_cms_material` so a single CLI command goes end-to-end (parse → dedup → admin queue → auto-test).

---

## 4. Admin-curated tests (current)

Existing `TestAdmin` allows manual creation. To reduce friction:

- **Lazy auto-fill**: when admin selects `test_type='subject'`, pre-fill `question_count=100`, `time_limit_minutes=60`, `negative_marking=True/False` based on exam track defaults.
- **Bulk-import from JSON**: support a "paste questions from NEET PG textbook" modal that runs through `_safe_set_questions`.
- **Bulk-import from CSV**: already supported via the existing `_import_neet_pg` workflow.

## 5. Scheduled mocks (gap)

**Target**: `CronJob` model + management command `manage.py run_scheduled_tests` polled by django-q2 daily at 06:00 IST.

Schema sketch:

```python
class ScheduledTest(models.Model):
    KIND = (("daily", "Daily"), ("weekly", "Weekly"), ("grand", "Grand"))
    kind = models.CharField(choices=KIND)
    title = models.CharField(max_length=200)
    run_at = models.DateTimeField()                  # next firing
    recur_every_days = models.IntegerField(default=0) # 0 means one-shot
    exam_type = models.CharField(max_length=20, default="cms")
    question_count = models.IntegerField(default=100)
    time_limit_minutes = models.IntegerField(default=60)
    auto_pick = models.CharField(
        max_length=32,
        choices=[
            ("recent_pyqs", "Recent PYQs only"),
            ("weak_topics", "Student's weakest topics"),
            ("mixed_random", "Mixed random across subjects"),
        ],
    )
    target_groups = models.JSONField(default=list)   # [{scholarship: true}]
    is_active = models.BooleanField(default=True)
```

Implementation plan:
1. Models + migration (Phase 17 HIGH priority).
2. `pick_questions(strategy, exam_type, count)` helper that wraps `Question.objects.filter(exam_type=...).order_by('?')[:count]`.
3. `run_scheduled_tests` management command (idempotent, marks the run on the scheduled row, kicks off via `django-q2`).
4. UI on admin: cron-like calendar view.

## 6. Adaptive mocks (gap)

The `test_type='adaptive'` already exists in the schema but no orchestrator. Design:

1. Start with `pick_questions(strategy='mixed_random', count=20)`.
2. After every 5 questions, compute `UserTopicPerformance.accuracy` for the topics answered so far.
3. Replace the *next* 5-question block with questions from the user's weakest topics (`accuracy < 0.55`).
4. End the test when the total score stabilizes (3 consecutive blocks with <5% score change).

Implementation steps:

- Add `tests_engine.adaptive.next_block(user, current_block_size)` returning a list of question IDs.
- Frontend `tests/[id]/page.tsx` already posts per-question responses; add a "Block complete" signal that calls the next-block endpoint.

## 7. Leaderboard + rank (partial)

`analytics` app already exposes `leaderboard` (per memory: today-score / streak / badge views). To improve:

- **Anti-cheat signals**: detect submissions faster than humanly possible (e.g. avg answer time < 1.5 s/question for > 50% of questions) and silently demote to "unranked".
- **Subject-wise ranks**: separate CMS / NEET PG / INI-CET leaderboards.
- **Weekly reset cron**: roll over every Sunday 00:00 IST.

## 8. AI-generated mocks (gap)

Workflow:

1. Admin picks "Generate mock" → chooses (exam_type, subject?, topic?, question_count, difficulty_mix).
2. Front-end calls `POST /api/tests/ai-generate/` (new endpoint) with payload.
3. Backend picks most-common keywords for the (subject, topic) from existing questions and calls RoundRobin AI (`ask(prompt, mode='mock_test')`).
4. AI returns `{questions: [...], mnemonic_hints: [...]}` and we persist them as `ExtractedQuestion(status='pending')`. Admin still has to approve/publish before they reach students.
5. Iterative rejection loop: if AI-generated questions are flagged `needs_review=True` (e.g. wrong answer / poor explanation), the next call gets a stricter system prompt.

Required infra:
- One AI prompt template in `ai_engine/services.py:AI_PROMPTS['mock_test']`.
- A `_build_mock_test_payload(exam_type, subject, topic, count)` in `tests_engine.builder` (reuse `mock_test_builder`).
- Confidence floor: if AI returns a question with any `confidence < 0.6`, mark `needs_review=True`.

## 9. Per-folder / DOCX-driven tests (current)

The importer already routes:
- `cms_exclusive_material/<subject>/<topic>/*.docx` → parses → publishes → `mock_test_builder` generates auto-tests.
- PYQ files (filename contains "PYQ") → grouped by year.

Add: a `--publish-and-build-tests` flag on `ingest_cms_material` so admins skip the manual admin step.

---

## 10. Image-only tests (gap)

A subset of NEET PG + INI-CET questions are 100% image-based (CT scans, fundus photos). Design:

- Tag questions with `is_image_based=True` (already in `material_importer.parser.dataclasses.ParsedQuestion`).
- A `mock_test_builder.build_image_only_test(subject, count)` that picks N most-frequently-flagged image-based questions.
- Frontend already has a zoomable image viewer in `tests/[id]/page.tsx`; that's reusable.

---

## 11. Performance budget for the pipeline

| Step | Time | Notes |
|---|---|---|
| `ingest_path` parse | < 5 s/100 files | Heuristic parser, no AI |
| `_seed_existing_dedup` (cold) | 2-4 s | First batch of session |
| `_seed_existing_dedup` (warm cache hit) | ~50 ms | After H4 lands |
| `mock_test_builder.build_for_batch` | 1-3 s | Subject+topic grouping |
| AI classification per Q (opt-in) | 5-20 s | Round-robin 9 providers, 120 s total budget |
| AI enrichment per Q | 5-20 s | Same |

Reaching the AI backfill of the 480 Batch-13 questions needs ~80 minutes of AI time (480 × 10 s) and ~480 tokens. Best-effort estimate; actual ratio depends on provider availability.

---

## 12. Open tasks (already in TASKS.md)

- ARCH-1: this doc (✅ shipped).
- ARCH-2: implement "admin Publish single batch → tests" REST endpoint (next session).
- CONTENT-1: identify the 480 Batch #13 questions missing `correct_answer` (likely image-based; can be auto-filtered by `is_image_based=True`).

---

## 13. Decision record (mirrored in DECISIONS.md)

- `is_published` semantics on Test, not a separate flag (DECISION-005).
- Idempotency over concatenation: re-running build must NOT duplicate rows (preserved via pre-delete by `title__icontains=f"batch {batch_id}"`).
- Student workflow: explicit "Start Test" tap; the loader must NOT auto-publish (admin gate intact).
