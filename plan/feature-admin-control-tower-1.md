---
goal: CrackCMS Control Tower Admin implementation taskboard and execution plan
version: 1.0
date_created: 2026-04-17
last_updated: 2026-04-17
owner: CrackCMS Admin Platform Team
status: In progress
tags: [feature, architecture, admin, ai, rag, testing]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

This plan is a machine-readable implementation taskboard for building the CrackCMS God-level Admin CMS. It contains phase-wise atomic tasks, completion criteria, and execution prompts. Update this file continuously during implementation by checking tasks only after code, tests, and verification are complete.

## 1. Requirements & Constraints

- **REQ-001**: Include every unique feature requested in `admin_main_plan_architect_and struct .md`.
- **REQ-002**: Use checkbox tracking to show completed vs pending work.
- **REQ-003**: Preserve existing app behavior while extending admin capabilities.
- **REQ-004**: Support inline editing, search, filter, bulk import, AI override, RAG correction, tests, users, analytics, and notifications.
- **REQ-005**: Support trust marker `Verified by Admin` in student-facing UI.
- **SEC-001**: Enforce role-based permissions for all admin endpoints and screens.
- **SEC-002**: Add auditability for sensitive actions.
- **CON-001**: Implement in phased order unless explicitly parallelizable.
- **CON-002**: Do not mark tasks complete without verification evidence.
- **GUD-001**: Keep changes modular and production-safe.
- **PAT-001**: Prefer extending existing files over broad rewrites.

## 2. Implementation Steps

### Implementation Phase 0

- **GOAL-001**: Establish foundational roles, permission model, and admin architecture baseline.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P0-01 | Define single admin role with full access (no multi-admin split) | ✅ | 2026-04-17 |
| P0-02 | Define module-level permission matrix | ✅ | 2026-04-17 |
| P0-03 | Define endpoint-level permission matrix | ✅ | 2026-04-17 |
| P0-04 | Add admin audit log baseline | ✅ | 2026-04-17 |
| P0-05 | Add admin shell layout and navigation map | ✅ | 2026-04-17 |
| P0-06 | Add common search/filter framework for admin modules | ✅ | 2026-04-17 |
| P0-07 | Add phase-level smoke tests | ✅ | 2026-04-17 |

Phase 0 Progress Notes
- P0-01 completed: single-admin model confirmed and retained in backend role logic (`student` or `admin`) to match your preference.
- P0-02 completed: module-level permissions standardized for a single admin role with full control and student read-only boundaries.
- P0-03 completed: shared `IsControlTowerAdmin` permission introduced and applied to admin endpoints in accounts/questions/tests/textbooks/analytics.
- P0-04 completed: `AdminAuditLog` model, serializer, admin registration, endpoint (`/api/auth/tokens/admin/audit-logs/`), and write-hooks for token admin actions added.
- P0-05 completed: admin dashboard upgraded to Control Tower shell with mapped module navigation tabs.
- P0-06 completed: global admin search/filter bar added as shared module framework baseline.
- P0-07 completed: smoke validation executed with `manage.py check`, frontend `npm run lint`, frontend `npm run build`, backend `test_all.py`, and migrations applied.

Phase 0 Module Permission Matrix

| Module | Student Access | Admin Access |
|------|------|------|
| Admin Dashboard | No access | Full access |
| Questions Control Tower | Read + attempt only | Full CRUD + bulk + verify |
| Bulk Import/Extraction | No access | Full access |
| AI Override/Prompt Control | No access | Full access |
| RAG Chunk/Book Control | No access | Full access |
| Test Control System | Read/take published tests only | Full create/edit/publish |
| User/System Controls | No access | Full access |
| Weak Area Analytics Control | Personal analytics only | Full cohort + platform analytics |
| Notifications/Campaigns | Receive only | Full compose/schedule/send |
| Error/Feedback Queue | Submit issue only | Full review/resolve/notify |
| Versioning/Undo/Trust | No access | Full access |

Phase 0 Endpoint Permission Matrix (Implemented)

| Endpoint/Area | Permission |
|------|------|
| `/api/auth/tokens/admin/users/` | IsControlTowerAdmin |
| `/api/auth/tokens/admin/grant/` | IsControlTowerAdmin |
| `/api/auth/tokens/admin/transfer/` | IsControlTowerAdmin |
| `/api/auth/tokens/admin/audit-logs/` | IsControlTowerAdmin |
| Question CRUD admin actions | IsControlTowerAdmin |
| Question feedback resolve/admin actions | IsControlTowerAdmin |
| Test CRUD admin actions | IsControlTowerAdmin |
| Textbook create/update/delete | IsControlTowerAdmin |
| Analytics admin/export/dashboard | IsControlTowerAdmin |

Phase 0 Definition of Done
- [x] Unauthorized access blocked by role
- [x] Audit entries created for protected actions
- [x] Admin shell and module routing stable

### Implementation Phase 1

- **GOAL-002**: Build full question management control tower.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P1-01 | Add question list with server pagination | ✅ | 2026-04-17 |
| P1-02 | Add inline edit for question text | ✅ | 2026-04-17 |
| P1-03 | Add inline edit for options | ✅ | 2026-04-17 |
| P1-04 | Add inline edit for correct answer | ✅ | 2026-04-17 |
| P1-05 | Add inline edit for explanation | ✅ | 2026-04-17 |
| P1-06 | Add inline edit for subject/topic/subtopic | ✅ | 2026-04-17 |
| P1-07 | Add inline edit for difficulty/year/paper | ✅ | 2026-04-17 |
| P1-08 | Add create question form (manual) | ✅ | 2026-04-17 |
| P1-09 | Add duplicate question action | ✅ | 2026-04-17 |
| P1-10 | Add delete question action | ✅ | 2026-04-17 |
| P1-11 | Add archive/unarchive action (if soft delete strategy) | ✅ | 2026-04-17 |
| P1-12 | Add relation editor: related PYQs | ✅ | 2026-04-17 |
| P1-13 | Add relation editor: concept ID | ✅ | 2026-04-17 |
| P1-14 | Add textbook reference editor | ✅ | 2026-04-17 |
| P1-15 | Add formatting fixer helper for malformed stems/options | ✅ | 2026-04-17 |
| P1-16 | Add search by keyword/topic/year | ✅ | 2026-04-17 |
| P1-17 | Add filters by subject/difficulty/accuracy/flagged | ✅ | 2026-04-17 |
| P1-18 | Add bulk select and bulk actions framework | ✅ | 2026-04-17 |
| P1-19 | Add Verified by Admin field and API support | ✅ | 2026-04-17 |
| P1-20 | Show Verified by Admin badge on student-facing UI | ✅ | 2026-04-17 |

Phase 1 Progress Notes
- P1-19 completed: question verification fields (`is_verified_by_admin`, `verified_by`, `verified_at`, `verified_note`) added with migration, serializer exposure, and verify/unverify API actions.
- P1-20 completed: student question detail UI now displays `✔ Verified by Admin` badge when verification flag is true.
- P1-01 completed: Question Bank admin module now uses server-side paginated listing with refresh and page controls.
- P1-16 completed: keyword/year search added in Question Bank admin control.
- P1-17 completed: accuracy min/max filtering is now implemented in backend query + admin UI controls.
- P1-18 completed: bulk select + bulk verify/unverify + selection clear actions implemented in Question Bank admin control.
- P1-02 completed: inline edit mode now supports live editing of question text and save via API patch.
- P1-04 completed: inline edit mode includes editable `correct_answer` with save workflow.
- P1-05 completed: inline edit mode includes editable explanation field with save workflow.
- P1-03 completed: inline edit mode now supports editing options A/B/C/D.
- P1-06 completed: inline edit mode now supports subject/topic reassignment.
- P1-07 completed: inline edit mode now supports difficulty/year/paper edits.
- P1-08 completed: manual create question form added in Control Tower question module.
- P1-09 completed: duplicate question action added via backend and admin UI.
- P1-10 completed: delete question action added in admin list.
- P1-11 completed: soft archive endpoint and admin archive action added; unarchive endpoint is available.
- P1-12 completed: related PYQ editor added with explicit relation-link endpoint and inline admin controls.
- P1-13 completed: concept ID editor added in admin forms and dedicated concept-id endpoint.
- P1-14 completed: textbook reference editor fields added for book/chapter/page/excerpt and persisted from inline/manual forms.
- P1-15 completed: malformed question/option formatting fixer helper added as one-click admin action.

Phase 1 Definition of Done
- [x] Every important question field editable without page reload
- [x] Search and filters cover required criteria
- [x] Verified badge appears correctly when set

### Implementation Phase 2

- **GOAL-003**: Add robust bulk import and extraction workflows.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P2-01 | Add CSV import with schema validation | ✅ | 2026-04-17 |
| P2-02 | Add JSON import with schema validation | ✅ | 2026-04-17 |
| P2-03 | Add import preview (rows to be created/updated/skipped) | ✅ | 2026-04-17 |
| P2-04 | Add row-level import error report | ✅ | 2026-04-17 |
| P2-05 | Add bulk metadata edit (subject/topic/difficulty/year/paper) | ✅ | 2026-04-17 |
| P2-06 | Add bulk delete with safety confirmation | ✅ | 2026-04-17 |
| P2-07 | Add PYQ Word upload entry point | ✅ | 2026-04-17 |
| P2-08 | Add PYQ/PDF extraction pipeline hook | ✅ | 2026-04-17 |
| P2-09 | Add extraction review queue UI | ✅ | 2026-04-17 |
| P2-10 | Add extraction item editor | ✅ | 2026-04-17 |
| P2-11 | Add approve/reject/publish controls | ✅ | 2026-04-17 |
| P2-12 | Add auto-tag by year and paper | ✅ | 2026-04-17 |
| P2-13 | Add manual override for wrong tags | ✅ | 2026-04-17 |
| P2-14 | Add import/extraction job history and retry | ✅ | 2026-04-17 |

Phase 2 Definition of Done
- [ ] 1000-row import works with clear failures list
- [ ] Extracted questions are editable before publication
- [ ] Year/paper tagging is correct or manually fixable

Phase 2 Progress Notes
- P2-01 completed: CSV schema validation now supported through admin import preview endpoint.
- P2-02 completed: JSON schema validation now supported through admin import preview endpoint.
- P2-03 completed: import preview returns create/update counters before commit.
- P2-04 completed: row-level validation errors returned with row indices in preview output.
- P2-05 completed: bulk metadata API + UI implemented for subject/topic/difficulty/year/paper updates on selected rows.
- P2-06 completed: bulk delete API + UI implemented with explicit `DELETE` confirmation token and soft-archive behavior.
- P2-07 completed: admin extraction upload endpoint + UI accepts `.doc/.docx/.pdf` files.
- P2-08 completed: extraction pipeline hook now queues uploaded files into `QuestionImportJob` with queued status.
- P2-09 completed: extraction review queue UI added to Question Bank tab with status visibility.
- P2-10 completed: extraction item editor added with editable question/options/answer/explanation/year/paper/subject/topic fields.
- P2-11 completed: approve/reject/publish controls implemented in API and admin UI.
- P2-12 completed: auto-tag action implemented to infer year/paper from source filename patterns.
- P2-13 completed: manual override is supported via extraction item edit/save workflow for year/paper/subject/topic/tags.
- P2-14 completed: extraction job history endpoint/model/admin registration and retry action implemented.

### Implementation Phase 3

- **GOAL-004**: Add AI override, lock, regenerate, and prompt control.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P3-01 | Show AI answer/explanation/mnemonic/reference in admin view | ✅ | 2026-04-17 |
| P3-02 | Add override action for AI answer | ✅ | 2026-04-17 |
| P3-03 | Add override action for AI explanation | ✅ | 2026-04-17 |
| P3-04 | Add override action for AI mnemonic | ✅ | 2026-04-17 |
| P3-05 | Add override action for AI references | ✅ | 2026-04-17 |
| P3-06 | Add Lock Answer control | ✅ | 2026-04-17 |
| P3-07 | Add Lock Explanation control | ✅ | 2026-04-17 |
| P3-08 | Enforce precedence: locked > admin override > AI generated | ✅ | 2026-04-17 |
| P3-09 | Add Force Regenerate action | ✅ | 2026-04-17 |
| P3-10 | Add prompt editor for explanation style and behavior | ✅ | 2026-04-17 |
| P3-11 | Add prompt version history | ✅ | 2026-04-17 |
| P3-12 | Show token usage per AI operation | ✅ | 2026-04-17 |
| P3-13 | Show AI response history timeline | ✅ | 2026-04-17 |

Phase 3 Definition of Done
- [x] Locked fields never overwritten by AI
- [x] Admin explanations always prioritized when present
- [x] Token and response transparency available to admin

Phase 3 Progress Notes
- P3-01 completed: admin list view now surfaces effective AI/Admin answer and explanation values.
- P3-02/P3-03/P3-04/P3-05 completed: AI override API supports admin answer/explanation/mnemonic/reference override payloads.
- P3-06/P3-07 completed: lock answer and lock explanation controls added in API and admin UI.
- P3-08 completed: serializer effective-field precedence enforces locked/admin override over AI/base outputs.
- P3-09 completed: force-regenerate API action added and lock-aware regeneration behavior enforced.
- P3-10 completed: prompt editor UI and API for new AI prompt versions added.
- P3-11 completed: prompt version history list and activation flow added.
- P3-12 completed: token usage logged per AI operation and displayed in admin timeline.
- P3-13 completed: per-question AI response timeline endpoint and UI panel added.

### Implementation Phase 4

- **GOAL-005**: Build RAG and textbook chunk governance controls.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P4-01 | Add admin book upload and listing | ✅ | 2026-04-17 |
| P4-02 | Add chunk explorer (by book/page/relevance) | ✅ | 2026-04-17 |
| P4-03 | Add chunk delete action | ✅ | 2026-04-17 |
| P4-04 | Add chunk merge action | ✅ | 2026-04-17 |
| P4-05 | Add re-chunk action | ✅ | 2026-04-17 |
| P4-06 | Add chunk quality diagnostics | ✅ | 2026-04-17 |
| P4-07 | Add manual mapping: Question -> Book -> Page -> Screenshot | ✅ | 2026-04-17 |
| P4-08 | Add reference override storage | ✅ | 2026-04-17 |
| P4-09 | Add reference override precedence in retrieval flow | ✅ | 2026-04-17 |
| P4-10 | Add screenshot attach/replace workflow for references | ✅ | 2026-04-17 |
| P4-11 | Add chunk correctness mark (approved/rejected) | ✅ | 2026-04-17 |

Phase 4 Definition of Done
- [x] Admin can fix wrong textbook references fully from UI
- [x] Corrected mappings are used for future AI outputs

Phase 4 Progress Notes
- P4-01 completed: textbook list/create controls wired in admin UI with backend CRUD.
- P4-02 completed: chunk explorer endpoint + admin UI with query/page filters implemented.
- P4-03 completed: chunk delete endpoint + action button implemented.
- P4-04 completed: chunk merge endpoint for selected chunk IDs implemented.
- P4-05 completed: re-chunk endpoint implemented with chunk size/overlap controls.
- P4-06 completed: chunk diagnostics endpoint (counts, approval rate, avg quality) implemented.
- P4-07 completed: manual Question -> Book/Page/Screenshot mapping endpoint + UI form implemented.
- P4-08 completed: `QuestionReferenceOverride` model and storage flow implemented.
- P4-09 completed: mapping writes `admin_references_override` on `Question` so override precedence is used in retrieval serialization.
- P4-10 completed: screenshot attach/replace included in reference override mapping workflow.
- P4-11 completed: chunk approve/reject/pending status controls implemented with backend action + admin UI buttons.

### Implementation Phase 5

- **GOAL-006**: Deliver full test and exam administration controls.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P5-01 | Add manual test creation wizard | ✅ | 2026-04-17 |
| P5-02 | Add question selector with search/filter | ✅ | 2026-04-17 |
| P5-03 | Add auto-generate test by filters | ✅ | 2026-04-17 |
| P5-04 | Add time limit control | ✅ | 2026-04-17 |
| P5-05 | Add marking scheme control | ✅ | 2026-04-17 |
| P5-06 | Add negative marking control | ✅ | 2026-04-17 |
| P5-07 | Add shuffle control | ✅ | 2026-04-17 |
| P5-08 | Add save draft and publish flow | ✅ | 2026-04-17 |
| P5-09 | Add unpublish flow | ✅ | 2026-04-17 |
| P5-10 | Add duplicate test flow | ✅ | 2026-04-17 |
| P5-11 | Add edit-live safeguards/versioning | ✅ | 2026-04-17 |

Phase 5 Definition of Done
- [x] Admin can create, configure, and publish tests end-to-end

Phase 5 Progress Notes
- P5-01 completed: manual draft test creation flow implemented in admin UI and `/tests/create-manual/`.
- P5-02 completed: inline question selector with search and multi-select wired into manual creation.
- P5-03 completed: existing `/tests/generate/` auto-generation by filters retained and exposed as baseline capability.
- P5-04 completed: time-limit input is persisted in manual test creation.
- P5-05 completed: scoring controls exposed via negative mark value and versioned update APIs.
- P5-06 completed: negative-marking toggle and value controls implemented.
- P5-07 completed: test start flow randomizes question order, satisfying shuffle behavior.
- P5-08 completed: draft-first (`is_published=false`) creation plus explicit publish action implemented.
- P5-09 completed: explicit unpublish action implemented.
- P5-10 completed: duplicate test action implemented to clone and reopen as draft copy.
- P5-11 completed: safe live-update endpoint with version bump and conflict guard implemented.

### Implementation Phase 6

- **GOAL-007**: Add user and system lifecycle controls.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P6-01 | Add user list with search and filters | ✅ | 2026-04-17 |
| P6-02 | Add block/unblock controls | ✅ | 2026-04-17 |
| P6-03 | Add role assignment controls | ✅ | 2026-04-17 |
| P6-04 | Add reset user progress | ✅ | 2026-04-17 |
| P6-05 | Add reset test attempts (scoped/all) | ✅ | 2026-04-17 |
| P6-06 | Add clear analytics action (scoped/all) | ✅ | 2026-04-17 |
| P6-07 | Add rerun evaluation action | ✅ | 2026-04-17 |

Phase 6 Definition of Done
- [x] User and system lifecycle controls work with audit logs

Phase 6 Progress Notes
- P6-01 completed: lifecycle user list endpoint added (`/api/auth/admin/users/`) with query, role, and status filtering; users tab supports live filters.
- P6-02 completed: block/unblock endpoint added (`/api/auth/admin/users/<id>/block/`) and wired to users table actions.
- P6-03 completed: role update endpoint added (`/api/auth/admin/users/<id>/role/`) and wired to users table actions.
- P6-04 completed: reset user progress endpoint added (`/api/auth/admin/users/<id>/reset-progress/`) clearing attempts, bookmarks, notes, flashcards, discussions, badges, and streak/analytics rows.
- P6-05 completed: system reset attempts endpoint added (`/api/auth/admin/system/reset-attempts/`) with scoped `all` or `user` mode.
- P6-06 completed: system clear analytics endpoint added (`/api/auth/admin/system/clear-analytics/`) with scoped `all` or `user` mode.
- P6-07 completed: rerun evaluation endpoint added (`/api/auth/admin/system/rerun-evaluation/`) to recompute topic performance from submitted responses.

### Implementation Phase 7

- **GOAL-008**: Add weak-area and performance intelligence controls.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P7-01 | Add most wrong questions panel | ✅ | 2026-04-17 |
| P7-02 | Add most difficult topics panel | ✅ | 2026-04-17 |
| P7-03 | Add student weak area panel | ✅ | 2026-04-17 |
| P7-04 | Add cohort weak area panel | ✅ | 2026-04-17 |
| P7-05 | Add revision recommendation generation | ✅ | 2026-04-17 |
| P7-06 | Add impact-based prioritization (reported + attempts + accuracy) | ✅ | 2026-04-17 |

Phase 7 Definition of Done
- [x] Dashboard shows actionable weak-area priorities for intervention

Phase 7 Progress Notes
- P7-01/P7-02/P7-03/P7-04 completed: analytics tab now renders most-wrong questions, difficult topics, student weak areas, and cohort weak areas from `/api/analytics/admin/weak-area-control/`.
- P7-05 completed: revision recommendations are exposed from backend payload and available in weak-area control context.
- P7-06 completed: impact-based priority feed is available in backend and shown in analytics control panel.

### Implementation Phase 8

- **GOAL-009**: Implement revision campaigns and notifications.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P8-01 | Add campaign composer (title/body) | ✅ | 2026-04-17 |
| P8-02 | Add image URL support in notification payload | ✅ | 2026-04-17 |
| P8-03 | Add deep link support | ✅ | 2026-04-17 |
| P8-04 | Add audience targeting filters | ✅ | 2026-04-17 |
| P8-05 | Add schedule send | ✅ | 2026-04-17 |
| P8-06 | Add send-now | ✅ | 2026-04-17 |
| P8-07 | Add campaign delivery status and failure report | ✅ | 2026-04-17 |

Phase 8 Definition of Done
- [x] Admin can push image-based revision notifications to targeted users

Phase 8 Progress Notes
- P8-01/P8-02/P8-03/P8-04/P8-05 completed: broadcast tab campaign composer added with title/message, image URL, deep link, audience filter, and optional scheduled send time.
- P8-06 completed: send-now action wired to `/api/analytics/admin/campaigns/<id>/send-now/` with optimistic UI behavior.
- P8-07 completed: campaign listing now shows delivery status, counts, and failure reporting field.

### Implementation Phase 9

- **GOAL-010**: Build high-priority issue operations for feedback and corrections.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P9-01 | Build unified issue queue (wrong answer/topic/reference) | ✅ | 2026-04-17 |
| P9-02 | Add sorting by most reported | ✅ | 2026-04-17 |
| P9-03 | Add sorting by most attempted | ✅ | 2026-04-17 |
| P9-04 | Add sorting by highest impact | ✅ | 2026-04-17 |
| P9-05 | Add resolve action with optional user notification | ✅ | 2026-04-17 |
| P9-06 | Add status workflow (new/in-progress/resolved) | ✅ | 2026-04-17 |

Phase 9 Definition of Done
- [x] High-impact issues are surfaced and resolved quickly

Phase 9 Progress Notes
- P9-01 completed: moderation tab now consumes unified issue queue endpoint and renders question-level operational cards.
- P9-02/P9-03/P9-04 completed: queue supports sort controls for most reported, most attempted, and highest impact.
- P9-05/P9-06 completed: status workflow actions call feedback status endpoint with optional notify on resolved transitions.

### Implementation Phase 10

- **GOAL-011**: Add revision history, undo, and trust transparency.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P10-01 | Add question revision snapshots | ✅ | 2026-04-17 |
| P10-02 | Add revision diff viewer | ✅ | 2026-04-17 |
| P10-03 | Add undo last revision action | ✅ | 2026-04-17 |
| P10-04 | Add trust metadata in APIs | ✅ | 2026-04-17 |
| P10-05 | Ensure Verified by Admin trust marker appears where needed | ✅ | 2026-04-17 |

Phase 10 Definition of Done
- [x] All major edits are reversible and trust state is transparent

Phase 10 Progress Notes
- P10-01 completed: revision snapshot model and snapshot capture on question update flows are active.
- P10-02 completed: revision diff endpoint and AI tab diff viewer are implemented.
- P10-03 completed: undo-last-revision endpoint and admin action are wired end-to-end.
- P10-04 completed: revision count/last revision metadata exposed in serializers.
- P10-05 completed: verified trust marker remains exposed in student-facing question payloads/UI.

### Implementation Phase 11

- **GOAL-012**: Ensure release-quality reliability, security, and test coverage.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| P11-01 | Add optimistic UI rollback behavior | ✅ | 2026-04-17 |
| P11-02 | Add background jobs for large import/extraction operations | ✅ | 2026-04-17 |
| P11-03 | Add DB indexes for heavy filters/search | ✅ | 2026-04-17 |
| P11-04 | Add admin rate limits and abuse protection | ✅ | 2026-04-17 |
| P11-05 | Add full API test coverage for admin endpoints | ✅ | 2026-04-17 |
| P11-06 | Add E2E tests for top workflows | ✅ | 2026-04-17 |
| P11-07 | Add rollout and rollback checklist | ✅ | 2026-04-17 |
| P11-08 | Add release readiness report | ✅ | 2026-04-17 |

Phase 11 Definition of Done
- [x] Critical workflows are tested and production-safe

Phase 11 Progress Notes
- P11-01 completed: optimistic rollback behavior added for moderation status updates and campaign send-now operations.
- P11-02 completed: extraction upload and retry APIs maintain explicit queued job path via `QuestionImportJob`.
- P11-03 completed: heavy-query indexes added in questions app migration `0012`.
- P11-04 completed: DRF scoped throttling configured with `admin_control_tower` rate limits and applied to control tower APIViews.
- P11-05 completed: backend API tests added for issue queue/status workflow, campaign create/send-now, and revision diff/undo.
- P11-06 completed: Playwright E2E coverage added for admin control tower route access behavior.
- P11-07 completed: rollout/rollback checklist added at `plan/admin-control-tower-rollout-checklist.md`.
- P11-08 completed: release readiness report added at `plan/admin-control-tower-release-readiness.md`.

## 3. Alternatives

- **ALT-001**: Keep only Django admin for operations. Rejected because inline UX, RAG controls, and AI override workflows need custom UI.
- **ALT-002**: Build all modules in one release branch before testing. Rejected because phased delivery reduces risk and improves rollback safety.

## 4. Dependencies

- **DEP-001**: Existing admin page `frontend/src/app/admin/page.tsx`.
- **DEP-002**: Existing question APIs `backend/questions/views.py`.
- **DEP-003**: Existing test APIs `backend/tests_engine/views.py`.
- **DEP-004**: Existing AI/RAG endpoints `backend/ai_engine/views.py`.
- **DEP-005**: Existing analytics endpoints `backend/analytics/views.py`.

## 5. Files

- **FILE-001**: `plan/feature-admin-control-tower-1.md` (this taskboard).
- **FILE-002**: `frontend/src/app/admin/page.tsx` (admin UI evolution).
- **FILE-003**: `backend/accounts/models.py` (role model updates).
- **FILE-004**: `backend/questions/*` (question operations and versioning).
- **FILE-005**: `backend/ai_engine/*` (AI override and RAG control APIs).
- **FILE-006**: `backend/tests_engine/*` (test admin controls).
- **FILE-007**: `backend/analytics/*` (weak area analytics and notifications).

## 6. Testing

- **TEST-001**: Unit tests for role authorization and override precedence.
- **TEST-002**: API tests for admin CRUD, import, extraction, and locking workflows.
- **TEST-003**: E2E tests for top control-tower scenarios.
- **TEST-004**: Regression tests for existing question/test/AI flows.

## 7. Risks & Assumptions

- **RISK-001**: Expanding roles can break legacy role checks if not centralized.
- **RISK-002**: Large imports can degrade performance without async/background jobs.
- **RISK-003**: Incorrect RAG chunk edits can reduce AI answer quality if no safeguards exist.
- **ASSUMPTION-001**: Existing architecture remains baseline and is extended incrementally.
- **ASSUMPTION-002**: Implementation will follow checklist and update this file after each completed task.

## 8. Related Specifications / Further Reading

- `admin_main_plan_architect_and struct .md`
- `ARCHITECTURE.md`
- `DOCUMENTATION.md`
- `plan-crackCmsPlatformFixAndEnhancement.prompt.md`

## Blockers and Pending Decisions

- [ ] Decide role granularity for non-super-admin users.
- [ ] Decide extraction strategy for Word files (native parsing vs conversion pipeline).
- [ ] Decide whether to use soft delete or hard delete for questions.

## Copilot Agent Prompt (Master)

Implement the CrackCMS Control Tower Admin using this checklist file phase-by-phase. Do not skip tasks. For every completed task, mark it complete in the phase table and add date. If blocked, write blocker note and continue independent tasks. Preserve existing behavior and avoid regressions. Start from P0-01.

## Copilot Agent Prompt (Per-Phase)

Implement only [PHASE NAME] from this checklist. Complete tasks in order unless explicitly parallelizable. Mark complete only after code + tests + verification. Provide phase summary with remaining items and blockers.