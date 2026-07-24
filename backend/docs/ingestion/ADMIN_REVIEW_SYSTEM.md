# ADMIN_REVIEW_SYSTEM.md — Phase 2 design stub

**Status**: DESIGN ONLY. No code yet. Phase 1 ships the staging table (`ingestion.StagedQuestion`); Phase 2 builds the triage UI on top of it.
**Last updated**: 2026-07-24

---

## Why Phase 2 exists

Phase 1's conservative gate writes two non-PR buckets to `ingestion.StagedQuestion`:

| Bucket | `qa_status` | `review_status` (Phase 1) | Phase 2 admin action |
|---|---|---|---|
| Needs Review (NR) | `Needs Review` | `pending` | Approve → promote to `Question`; Edit → fix payload then promote; Reject → keep as `rejected`; Merge → consolidate with adjacent question |
| Extraction Failure (EF) | `Extraction Failure` | `blocked` | Investigate via `failure_log_paths`; if salvageable, demote to NR and continue triage; otherwise keep `blocked` |

Phase 2 reads `StagedQuestion` (no new tables needed) and emits writes back to `questions.Question` for approved items, recording every action in `accounts.models.AdminAuditLog`.

---

## UI surface (`/admin/ingestion/review/`)

```
/admin/ingestion/review/
├── layout.tsx                       # server-side admin role gate (Phase 1 already provides this)
├── page.tsx                         # bucket selector + summary tiles
├── needs-review/
│   ├── page.tsx                     # paginated list (filters: subject, batch_id, failing_axis)
│   └── [staged_id]/page.tsx         # side-by-side editor (overlay image + payload JSON + axis bars)
└── extraction-failure/
    ├── page.tsx                     # blocked list with diagnostic surface
    └── [staged_id]/page.tsx         # failure analysis: overlay paths, OCR snippet, axis summary
```

Each detail page exposes the same eight action buttons (RBAC-gated):

1. **Approve** — set `review_status='approved'`, `published_question=<Q>` (writes via `DjangoWriter.write_question`); Phase 2 reuses the Phase 1 writer.
2. **Edit then approve** — opens a JSON editor over `question_payload`; on save, the editor runs `ParsedQuestion` validation, then writes via the writer.
3. **Reject** — sets `review_status='rejected'`; no `Question` write; surface stays in dashboard as "Rejected (NR)".
4. **Demote to NR** — EF only; sets `review_status='pending'` and `qa_status='Needs Review'`, copying the diagnostic surface into `failure_log_paths`.
5. **Merge with #X** — keeps `review_status='pending'`; sets `merged_into_id=<adjacent>`; resolver view renders them as one.
6. **Split** — inverse of merge; splits a payload into 2+ `StagedQuestion` rows.
7. **Replace image** — opens the media library; replaces `image_path` in `question_payload`; reviewer must re-validate.
8. **Fix answer** — opens the answer/explanation fields; saves a corrected `correct_option` and explanation; preserves original in `failing_axes[*]` for audit.

Every action emits one `AdminAuditLog` row via `ingestion.utils.audit()` reusing the existing `system_rerun_evaluation` slot (the precise verb lives in `metadata.verb`).

---

## Triage detail screen

```
┌───────────────────────────────────────────────────────────────┐
│  StagedQuestion #8412  |  job #117  |  NEET-PG-2021 page 42   │
├──────────────────────────┬────────────────────────────────────┤
│  Overlay (PNG)           │  Payload JSON  (editable textarea) │
│  /img/overlays/8412.png  │  ┌─────────────────────────────┐   │
│                          │  │ {                            │  │
│                          │  │   "stem": "...",             │  │
│                          │  │   "options": [...],          │  │
│                          │  │   "correct_option": "C",     │  │
│                          │  │   "explanation": "..."       │  │
│                          │  │ }                            │  │
│                          │  └─────────────────────────────┘   │
├──────────────────────────┴────────────────────────────────────┤
│  QA V2 axis bars (9 axes)                                       │
│  layout_pass       ████████████████ 1.0  ✓                     │
│  ocr_pass          ████████████████ 0.95 ✓                     │
│  image_mapping     ████████████░░░░ 0.78 ✓ (low-confidence)    │
│  answer_consistent ░░░░░░░░░░░░░░░░ 0.30 ✗  ← failing axis    │
│  explanation_quality ░░░░░░░░░░░░░ 0.45 ✗  ← failing axis     │
│  …                                                                │
├───────────────────────────────────────────────────────────────┤
│  [Approve] [Edit] [Reject] [Merge] [Split] [Replace image] … │
└───────────────────────────────────────────────────────────────┘
```

---

## Reader API surface (Phase 2 backend additions)

Phase 2 adds five read endpoints to `ingestion.views` (all reuse the same `IsIngestionAdmin` gate):

| Verb | Path | Purpose |
|---|---|---|
| GET | `/review/needs-review/?subject=&batch_id=&failing_axis=&page=` | Paginated NR list |
| GET | `/review/extraction-failure/?reason=` | Paginated EF list |
| GET | `/review/<staged_id>/` | Single staged row + axes + overlay paths |
| POST | `/review/<staged_id>/<action>/` | Action endpoint; emits audit; idempotent on already-terminal states |
| GET | `/review/summary/` | Counts per bucket, per failing-axis, per batch — feeds Phase 3 dashboard |

No new tables; all reads/writes target `ingestion.StagedQuestion` and `accounts.AdminAuditLog`.

---

## Writer semantics

- **Approve** → calls `importers.neetpg.db_writer.DjangoWriter.write_question(payload, recall_text_hash, exam_type)`; sets `published_question=<Q row>`; idempotent on `(recall_text_hash, exam_type)`.
- **Reject** → updates `review_status='rejected'`, `review_note=...`; never touches `Question`.
- **Edit** → updates `question_payload` JSON; preserves the prior payload in `metadata.previous_payload` for 90 days; runs the same `ParsedQuestion` validation the MCE pipeline runs.
- **Demote EF→NR** → flips `qa_status='Needs Review'`, `review_status='pending'`; copies failure paths into `failure_log_paths`; logs the demotion reason in `metadata.demote_reason`.
- **Merge / Split** → manipulates `question_payload` and `merged_into_id`; both actions logged with before/after payload hashes.

Every terminal action is wrapped in `transaction.atomic()` so a partial write is impossible.

---

## Rollout plan for Phase 2

1. Build read endpoints behind a feature flag (`ENABLE_REVIEW_UI=0` default).
2. Build the action endpoints with full audit-log integration but no UI.
3. Drop the UI behind the same flag.
4. Run the first 6-PDF NEET PG batch through Phase 1; while it imports, screenshot the Phase 2 UI against the seeded `StagedQuestion` rows.
5. Manually approve 5 NRs and 1 EF; assert `Question` rows match the payloads byte-for-byte.
6. Flip the flag on; monitor `AdminAuditLog` rows for 48 hours.

The Phase 2 review surface is additive — the existing UPSC admin and the existing `/admin/ingestion/` landing are untouched.

---

## Out of scope for Phase 2

- Bulk approve / reject (Phase 3 dashboard exposes a batch tool).
- Cross-bucket auto-routing (Phase 4 quality analytics surfaces a recommendation per failing axis).
- A/B testing of differing QA V2 thresholds (Phase 4 analytics has the comparison view).
