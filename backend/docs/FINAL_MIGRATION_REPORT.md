# Final migration report — stem-structure normalization

## Summary

| Metric | Value |
|---|---|
| Migration version | `2026_07_30_apply_stem_normalization_v1` |
| Bucket applied | `auto_rewrite` (confidence ≥ 0.98) |
| Bucket count applied | 51 |
| Buckets skipped | `manual_review` (32), `skip_low_confidence` (24), `option_list` (1), `paragraph_broken` (157), `ocr_ambiguity` (7), `no_pattern` (1,165), `accepted_a` (0) |
| Transaction | `transaction.atomic()` with `select_for_update()` per row |
| Snapshot file | `docs/STEM_STRUCTURE_ROLLBACK_20260729T221756Z.json` |
| Snapshot schema | `(id, original_question_text, rewritten_question_text, score, applied_at, migration_version)` |

## Verification (pre-migration)

| Check | Result |
|---|---|
| Unit tests | 24 / 24 pass (including id=22213 regression test) |
| Inspection (auto + manual) | 83 / 83 pass (7 checks each, 100% coverage) |
| Inline-tail DB scan | 1,535 rows / 0 missed |
| Already-structured regression | 1,054 / 1,054 unchanged |
| False-positive scan (8 formats) | 0 / 1,988 false positives |

## Verification (post-migration)

| Check | Result |
|---|---|
| Updated rows | 51 (exactly matches snapshot) |
| Live text matches rewrite | 51 / 51 |
| Already-structured rows unchanged | 1,054 / 1,054 |
| Contiguous numbering `1..N` | 51 / 51 |
| No instruction became a statement | 0 violations |
| No option text entered the stem | 0 violations |
| Snapshot / already_structured overlap | 0 |

## Rollback

If a regression is detected after deployment, run:

```bash
python manage.py apply_stem_normalization --rollback docs/STEM_STRUCTURE_ROLLBACK_20260729T221756Z.json
```

This restores every row in the snapshot to its original `question_text`
inside a `transaction.atomic()` block.

## Files changed

### Production code
- `backend/questions/migrations/_statement_splitter.py` — added the
  missing `split_space_joined_stems` function referenced by migration
  `0032_split_space_joined_stems.py`. Added generalized inline-tail
  detector, confidence scoring, and `score_space_joined_stems`
  companion function. Idempotent: re-running on already-structured or
  already-rewritten rows returns the input unchanged.
- `backend/questions/management/commands/apply_stem_normalization.py`
  — new management command to apply the verified candidates inside a
  transaction, with built-in rollback mode.

### Tests
- `backend/questions/tests/test_2026_07_28_space_joined_stems.py` —
  extended with 11 new tests (negative tail-leak cases, inline-tail
  scenarios including id=22213, confidence scoring). 24 / 24 pass.

### Documentation
- `backend/docs/STEM_STRUCTURE_REVIEW.md` — per-question before/after
  with unified diffs and metadata.
- `backend/docs/STEM_STRUCTURE_INSPECTION.md` — inspection results.
- `backend/docs/FINAL_VERIFICATION_REPORT.md` — pre-migration report.

### Generated artifacts
- `docs/STEM_STRUCTURE_REVIEW.json` — bucketed probe output.
- `docs/STEM_STRUCTURE_INSPECTION.json` — inspection verdicts.
- `docs/STEM_STRUCTURE_ROLLBACK_20260729T221756Z.json` — rollback
  snapshot (51 rows).
- `docs/INLINE_TAIL_REPORT.json`, `docs/ALREADY_STRUCTURED_CHECK.json`,
  `docs/FALSE_POSITIVE_REPORT.json` — verification reports.

## Idempotency

The splitter is idempotent by construction:
- `_is_already_structured` guard rejects rows that already have list
  markers.
- `split_space_joined_stems` and `score_space_joined_stems` return the
  input unchanged when:
  - the body already contains option-prefixed rows,
  - the body is paragraph-broken,
  - the splitter confidence is below `_REVIEW_THRESHOLD`,
  - any numbered statement would start with an instruction prefix.

Re-running the migration on the already-rewritten rows will not
produce a different output.