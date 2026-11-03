# Medical accuracy mission — integration contract (2026-11-01)

The binding contract between the implementation groups of the medical-accuracy mission. The plan is
`MEDICAL_ACCURACY_MISSION_PLAN.md`; the discovery maps (one per area: `rag-ai`, `editor-workflow`,
`images-evidence`, `pyq-notes-study`, `auth-recovery`, `performance`) hold the detailed designs. Where a
map and this file disagree, **this file wins** (it resolves the overlaps between the maps).

## 1. Ground rules (enforced in code and tests)

1. **No automatic key changes.** Only `questions.editorial.change_answer_key()` assigns `correct_answer`
   on an existing row (creates and importers excepted). A grep-based test keeps it that way. It records an
   immutable `AnswerKeyChange` (old key, new key, who, why ≥ 10 chars, evidence, revision snapshot).
   `verify_answers --fix`, `import_neet_pg` and every other AI-vote path stop writing keys.
2. **AI output is never a source.** Model-written book / chapter / page / edition / quote text is discarded.
   A citation is stored only if it resolves to a stored passage (source sha256 + page + verbatim quote).
   AI verdicts are stored as review signals labelled `claude-subagent (review signal)` or
   `llm:<provider>:<model>`.
3. **Evidence first, key second.** Answering decides what the evidence supports without seeing the stored
   or selected key, then compares. On disagreement it returns a conflict (never a justification of the
   key); when evidence is weak it abstains.
4. **Students never see full copyrighted pages.** They see accepted citations (title, edition, chapter,
   page label) and snippets of at most `EVIDENCE_SNIPPET_MAX_CHARS` (240). Full pages and figure tools are
   admin-only.
5. **Default behaviour is unchanged until switched on.** `AUTH_PROVIDER=supabase`, `RAG_STORE=legacy`,
   `EVIDENCE_FIRST=0` are the defaults; every new path is behind its flag and has tests in both states.
6. **Local only.** No production credentials, no network calls to external services (tests mock them),
   `AI_OFFLINE_MODE=1`, the pristine restore `crack_restore` is never written, `crack_local` only through
   commands with a dry-run default. Never print personal data (emails, names, phone numbers): counts only.

## 2. Shared definitions (already in the code — use them, do not re-implement)

| What | Where |
|---|---|
| Content hash of stem + options (staleness) | `questions.content_hashes.stem_hash(question_or_dict)` |
| Valid key or `''` | `questions.content_hashes.valid_key(value)` |
| After any change of key / stem / options | `questions.content_hooks.on_question_changed(question, old_key=, old_stem_hash=, reason=, actor=)` — call it in `transaction.on_commit`. Each group implements its reaction as `on_question_changed(question, **kw)` in its own module (`evidence.services`, `key_audit.services`, `questions.notes_builder`). |
| Pages | **1-based physical page number of the file** (`page_no`, what a PDF viewer calls page N). The printed number is `page_label` (blank when unknown; the UI then shows "PDF p. N"). DOCX: section ordinal, label blank, locator = section heading. |
| Evidence tiers | 1 official answer key / errata, 2 guideline, 3 standard textbook, 4 notes / coaching compilations (secondary, often the *same source* as the question), 5 question papers / question sets / workbooks (never evidence of a fact). |
| AI reviewer label | `claude-subagent (review signal)` |

## 3. Schema (wave 0, migrated on crack_local; do not edit these models' fields without the main session)

* `questions` (migration `0042_medical_accuracy_schema`): Question provenance fields (`explanation_status`,
  `explanation_status_reason`, `explanation_for_key`, `explanation_stem_hash`, `explanation_hash`,
  `explanation_origin`, `explanation_suggestion`, `explanation_reviewed_by/at/hash`, `verified_hash`,
  `answer_key_status`); `AnswerKeyChange` (immutable); `ExplanationSuggestion`; `TopicNote` builder fields +
  `exam_type='all'`; `TopicNoteSource`; `QuestionAttemptLog` (+ backfill from `QuestionAttempt`);
  `QuestionImage.alt_text / caption_reveals_answer / option_label / role_source`;
  `QuestionAIOperationLog.meta` + new operation choices. The **editor group** owns the only further
  `questions` migration: `0043_backfill_editorial_provenance` (data only).
* `reference_corpus` (`0001_initial`): `EvidenceRun`.
* `evidence` (`0001_initial`): `EvidenceSource`, `EvidenceFigure`, `QuestionEvidence`, `EvidenceReviewLog`.
* `key_audit` (`0001_initial`): `QuestionAudit`, `AuditResolution` (immutable), `ReviewClaim`.
* `accounts`: the **auth group** owns `0028_native_auth` (and adds the AdminAuditLog action choices
  `identity_import`, `identity_link`, `recovery_link`, `email_change`, `session_revoke`,
  `answer_key_change`, `evidence_review`, `audit_resolution`).

## 4. Interfaces between groups

### reference_corpus (RAG-core group)
```python
from reference_corpus import api
api.store_available() -> bool
api.search(query: str, *, k=8, tiers=(1, 2, 3, 4), kinds=None, exclude_question_id=None,
           mode='auto') -> list[Hit]          # Hit is a dict, see below
api.decide(question, *, stored_key='', selected_key='', purpose='audit', allow_llm=False,
           save=False, actor=None) -> dict    # EvidenceDecision, see below
api.verify_citations(text: str, allowed: dict[str, Hit]) -> dict   # {valid, invalid_ids, quote_mismatches, uncited_sentences, cleaned_text}
api.page_text(source_sha256: str, page_no: int) -> dict | None     # admin tools: {text, page_label, chapter}
api.render_page_png(source_sha256: str, page_no: int, dpi=110) -> bytes | None  # admin only (needs the file)
api.sources() -> list[dict]                   # registry rows for evidence.EvidenceSource sync
```
`Hit = {chunk_key, source: {sha256, title, edition, year, tier, kind, licence, student_display},
page_start, page_end, page_label, section, kind, text, score, ranks: {bm25, dense, rerank}, retrieval_mode}`.

`EvidenceDecision = {status: supported|conflict|insufficient_evidence|contradictory_sources|
image_context_missing|invalid_key, evidence_answer, stored_key, selected_key, confidence, margin, polarity,
question_type, per_option: {A: {support, contradiction, citations: [...]}}, citations: [verified only],
retrieval_mode, store_build_id, config_hash, run_id (when save=True)}`. The `independence filter` drops
chunks that are copies of the question itself (≥ 40 % of the stem's distinctive 4-grams); such copies are
reported separately as `copies: [{source, page, key_in_copy}]` — an audit signal, not evidence.

With no store (`REFERENCE_STORE_PATH` empty or missing) every function degrades: `store_available()` is
False, `search` falls back to the legacy BM25 store with `retrieval_mode='legacy'`, `decide` returns
`insufficient_evidence` with `retrieval_mode='none'`.

### evidence (images / evidence group)
```python
from evidence import services
services.sync_sources(rows) -> dict                       # upsert EvidenceSource from reference_corpus.api.sources()
services.record_passage_evidence(question, *, sha256, page_start, page_end, text, option_letter, stance,
        origin, score=None, method='', run_ref='', created_by=None, question_image=None, bbox=None) -> QuestionEvidence
services.review(evidence, *, actor, status, stance=None, option_letter=None, student_visible=None, note='')
services.mark_stale(question, reason='')                  # also exposed as on_question_changed(question, **kw)
services.student_citations(question, *, revealed: bool) -> list[dict]   # accepted, visible, non-stale; capped
services.citation_label(row) -> str                       # 'Title, edition, p. <label>' / 'PDF p. N' / 'section N'
```
`questions.image_context`: `image_context(question, draft=None) -> {required, available, missing_reason}`,
`prompt_text(question)`, `serialize_image_for_student(img, *, revealed)`.

### questions.editorial (editor group)
```python
change_answer_key(question, new_key, *, actor, reason, evidence, source, suggestion=None,
                  explanation_fields=None, request_id='') -> AnswerKeyChange
save_explanation(question, fields, *, actor, for_key, suggestion=None, accepted_fields=())
compute_explanation_status(question, suggestion=None) -> tuple[str, str]
mark_explanation_reviewed(...), verify_question(...), unverify_question(...)
rescore_key_change(change, *, actor, apply=False) -> dict
```
`questions.explain_option.explain_selected_option(question, *, selected, draft=None, actor,
acknowledge_conflict=False) -> ExplanationSuggestion` (uses `reference_corpus.api.decide` + optional LLM).

### key_audit (answer-key audit group)
```python
from key_audit import services
services.queue_question_audit(question_id, reason='')     # marks the audit stale; re-audits in the background
services.on_question_changed(question, **kw)
services.audit_question(question, *, reviews=None, run_evidence=False) -> QuestionAudit
services.key_status_for(question_ids) -> dict[int, str]   # used by questions.key_status (notes builder)
```
Review-queue API under `/api/key-audit/` (list with filters, detail with evidence + reviews, claim, resolve).
Resolving with a key change calls `questions.editorial.change_answer_key(..., source='review_queue')`.

### questions.key_status (notes group)
`key_statuses(questions) -> dict[int, KeyStatus(status, reason)]` with status `verified|provisional|excluded`;
reads `QuestionAudit` / `answer_key_status` when present (rules in the pyq-notes map, A1).

## 5. File ownership (exclusive unless a region is named)

| Group | Owns |
|---|---|
| **AUTH** | `accounts/**` (models, migration 0028, hashers, `supabase_import.py`, `import_supabase_auth`, native auth, Google identity, device-limit mixin, axes fix); `crack_cms/settings.py` **auth regions only** (authentication classes, SIMPLE_JWT, PASSWORD_HASHERS, AXES_*, auth throttle rates, AUTH_PROVIDER, GOOGLE_OAUTH_CLIENT_IDS); `requirements.txt` (pins for bcrypt, google-auth); frontend `src/lib/api.ts`, `src/lib/auth.tsx`, `src/lib/localAuth.ts`, `src/lib/localSession.ts`, `src/lib/supabase.ts`, `src/middleware.ts`, auth pages (`app/login`, `app/register`, `app/reset-password`, `app/verify-email`, `app/forgot-password`, auth sections of `app/settings`), `next.config.*` / `vercel.json` CSP for Google. Keeps per-request auth DB work minimal (perf map item 1). |
| **RAG-CORE** | `reference_corpus/**` except `models.py` / migrations; `ai_eval/reference_benchmark.py`, `ai_eval/answer_benchmark.py`, `ai_eval/common.py`, `ai_eval/build_reference_corpus.py`, `ai_engine/reference_corpus.py`; `requirements-reference.txt`; docs `docs/audit/RAG_BENCHMARK.md` (new section). |
| **RAG-INT** | `ai_engine/services.py`, `ai_engine/views.py` (incl. `PageScreenshotView`: admin-only, via `reference_corpus.api.render_page_png`), `ai_engine/offline.py`, `ai_engine/rag_pipeline.py`, `ai_engine/lexical_index.py`, `questions/ai_per_question.py`, `questions/tasks.py`; the backend reveal-panel bundle endpoint (perf map: 6 GETs → 1, old endpoints kept). **Backend only in wave 1**: switching the frontend to the bundle and showing the student conflict notice is wave-2 work (those components are owned by IMAGES / NOTES in wave 1). |
| **EDITOR** | `questions/editorial.py`, `questions/explain_option.py`, `questions/urls.py`, `questions/urls_editorial.py`, `questions/serializers.py` (effective_* order, provenance; image dicts via `questions.image_context.serialize_image_for_student`, references via `evidence.services.student_citations`), `questions/views.py` editor regions (`get_permissions` admin list, `update`/`partial_update`, `resolve_dispute`, `generate_explanation`, `force_regenerate`, verify/unverify, revision snapshot/undo, new editor actions), migration `0043_backfill_editorial_provenance`; frontend `app/admin/questions-editor/**` (QuestionEditModal, KeyChangeBox, ExplanationSuggestionPanel, ProvenancePanel), `src/lib/api/editorial.ts`. |
| **AUDIT** | `key_audit/**` except models / migrations; `questions/management/commands/verify_answers.py`, `questions/management/commands/import_neet_pg.py` (key-writing paths only), `ai_engine` vote parser **only via** a new `key_audit/votes.py` (RAG-INT removes the old writer); frontend `app/admin/review-queue/**`, `src/lib/api/keyAudit.ts`. |
| **IMAGES** | `evidence/**` except models / migrations; `questions/image_context.py`, `ai_engine/vision.py`, `questions/serializers_question_image.py`, `questions/image_upload.py`, `questions/recall_search.py`, `questions/recall_serializers.py`, `questions/views.py` image regions (`QuestionImageViewSet`, the image serve view), `tests_engine/views.py` (`EXAM_HIDDEN_FIELDS` region only), `textbooks/views.py`; frontend `components/evidence/**`, `components/question/QuestionFigures.tsx`, `app/admin/evidence/**`, `src/lib/evidence.ts`, `src/lib/imageTokens.ts`, `components/FormattedText.tsx`, `components/image/ImageViewer.tsx`, `components/recall/**`, `components/question/ExamQuestionBank.tsx`, `app/questions/practice/page.tsx`, `app/tests/[id]/page.tsx`, `app/practice/page.tsx`, `app/mistake-notebook/page.tsx`. |
| **NOTES** | `questions/key_status.py`, `questions/notes_builder.py`, `questions/answer_insights.py`, `questions/views_notes.py`, `questions/views_insights.py`, `questions/serializers_notes.py`, `questions/urls_notes.py`, `questions/tasks_notes.py`, `questions/management/commands/build_topic_notes.py`, `questions/practice_experience.py`, `questions/views.py` regions `attempt` and `practice_attempt` (one call to `answer_insights.log_answer`) and the old TopicNote views (repoint or delegate); frontend `app/topic-notes/**`, `app/admin/notes/**`, `components/notes/**`, `components/question/QuestionInsights.tsx`, `components/question/RevealExplanation.tsx`, `src/lib/api/notes.ts`; one mount line for `QuestionInsights` in `ExamQuestionBank.tsx` (after the reveal block). |
| **PERF** | `ai_eval/perf_probe.py`; `tests_engine/scoring_writes.py` (new: bulk analytics / mistake / study-time writes) + the call-site lines in the submit view; `analytics/views.py` dashboard paths; `questions/views.py` regions `retrieve` and `similar`; cache settings (`CACHE_MAX_ENTRIES` etc. — ask the main session); frontend `app/layout.tsx`, `components/providers/**` (lazy Datadog / analytics), `next.config` bundle settings that are not CSP. |

Rules for shared files: edit only your named regions with small, anchored edits (never rewrite a file you
do not own); if you need something in a file you do not own, put the exact request in your result's
`requests` list instead of editing it.

## 6. Verification for every group

* Backend tests through the memory-limited wrapper (this machine has ~6 GB RAM):
  `C:\Users\DIVYANSHU\Desktop\crack_cms\.venv\Scripts\python.exe -I C:\Users\DIVYANSHU\.claude\jobs\0201e27b\tmp\heavy.py test <labels>`
  (hermetic env, `--parallel 1`). Frontend: `heavy.py tsc`, `heavy.py eslint <files>`, `heavy.py unit [files]`.
  Any other heavy process also takes a slot: `heavy.py run manage.py <command> ...` (management-command
  dry runs against crack_local need `DJANGO_ENV_FILE=.env.localdev` in the environment), `heavy.py run -m
  ai_eval.<module> ...`, `heavy.py npm run build`.
* New behaviour needs tests: positive, negative, permission (anonymous / student / admin), and the flag-off
  path. Tests never call external services.
* No git commands (the main session commits per group). Never read or edit `backend/.env*`.
