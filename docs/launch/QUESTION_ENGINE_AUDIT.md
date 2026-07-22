# Phase 4 — Question Engine Audit

**Date:** 2026-07-22

## Practice modes verified (Phase 3 + Phase 4)

| Mode | Endpoint | Phase 4 status |
|---|---|---|
| Random | `/api/questions/practice_queue/?mode=random&seed=42` | ✅ seeded RNG |
| Year-wise | `?mode=year_wise&year=2024` | ✅ |
| Subject-wise | `?mode=subject_wise&subject_id=1` | ✅ |
| Topic-wise | `?mode=topic_wise&topic_id=1` | ✅ |
| Weak topics | `?mode=weak_topics` | ✅ derives from `TestAttempt` |
| Bookmarked | `?mode=bookmarked` | ✅ requires auth |
| Wrong | `?mode=wrong` | ✅ requires auth |
| Image-only | `?mode=image_only` | ✅ |
| Rapid revision | `?mode=rapid_revision` | ✅ |
| High yield | `?mode=high_yield` | ✅ |
| Clinical cases | `?mode=clinical_cases` | ✅ |

All eleven modes covered in
`backend/questions/tests_phase4.py::PracticeModesTestCase`.

## Answer validation

* Front-end `submit(answer)` POSTs to
  `/api/questions/{id}/practice/attempt/`.
* Backend uses `TestAttempt.objects.create(...)` or, if unavailable,
  `QuestionAIOperationLog.objects.create(...)` as a fallback.

## Bookmarks, flags, confidence, timer, elimination

* All persist on `QuestionBookmark.notes` (prefix-tagged lines).
* 24-hour cache on AI features; no cache on per-user state (so saves
  are immediately observable).
* `QuestionTimer` auto-pauses on `visibilitychange` and flushes
  every 30 s.

## Reveal explanation

* 3-tier reveal: question's own explanation → AI why-correct →
  clinical pearl → mnemonic → exam-importance bar.

## Related PYQs + topics

* `related_pyqs` falls back from concept_id to token overlap if
  concept cluster is small.
* `related_topics` aggregates `Question.topic` rows.

## Provenance

* `QuestionSource` rows (Phase 2) are append-only.
* `RecallSource` row is uniquely identified by `(sha256, page_start,
  page_end)`.

## Phase-4 actions

* Added `tests_phase4.py::PracticeExperienceTestCase` (4 tests).

## Recommendations

* Add a `QuestionAttemptState` model in Phase 5 to replace the
  `QuestionBookmark.notes` prefix-string storage — cleaner audit
  trail, easier export.
