# Answer-key audit and review queue

_Verified against the code on 2026-11-03 (branch `medical-accuracy-2`). Contract:
[`audit/MEDICAL_ACCURACY_DESIGN.md`](./audit/MEDICAL_ACCURACY_DESIGN.md)._

The audit classifies every question's answer key from what the database knows and lists the risky ones,
highest priority first, in the admin review queue (`/admin/review-queue`). **It never changes a key.** A
key changes only through an admin decision (`questions.editorial.change_answer_key`), which records the
old key, who changed it, why and the evidence (`questions.AnswerKeyChange`, immutable).

## 1. Ground rules

1. No automatic key changes: the audit, the importers and the AI reviews only produce signals.
2. AI output is a review signal, never evidence. Reviews carry their reviewer label
   (`claude-subagent (review signal)`, `llm:<provider>:<model>`) and the queue shows them as
   "AI review signal (not evidence)". One AI opinion is never enough for "likely correct".
3. "Verified" needs an official answer key, or an admin decision that cites strong evidence
   (official key, errata, guideline link, a page-cited passage with the quoted sentence). A printed
   source key (tier 4) or a note gives "likely correct".
4. Every imported signal is tied to the content it was made for (`questions.content_hashes.stem_hash`).
   After a stem / option edit it no longer counts; a stem edit also voids earlier human decisions
   (`QuestionAudit.content_changed_at`).
5. Commands are dry runs by default; `--apply` writes. Nothing reads local file paths at run time, so
   the audit gives the same result on every deployment.

## 2. Statuses (`key_audit/classify.py`)

The first rule that applies:

| Status | When |
|---|---|
| `needs_review` / `invalid_or_missing_key` | the stored key is not A-D |
| `needs_review` / `official_key_disagrees`, `verified` / `official_key_match` | an official answer key names another / the stored option |
| after the latest human decision for the current content | `verified` (strong evidence), `likely_correct` / `human_confirmed` (none), `needs_review` / `new_signal_after_review` (a risk signal recorded after it), `human_requested_review` (unverify / defer), `key_changed_after_review` |
| `contradictory_sources` | verified passages, or two confident printed keys, back different options |
| `needs_review` / *strongest open signal* | any signal that opens a review (table below) |
| `image_context_missing` | the question needs a figure that is not attached |
| `verified` / `evidence_verified` | verified tier <= 3 passages support the key and two other independent signals agree |
| `likely_correct` / `evidence_supported` or `independent_agreement` | verified passages support the key, or two independent signals agree (an AI-chosen key needs one that is not an AI review) |
| `insufficient_evidence` | anything else |

Priority (queue order) = the strongest open signal + 0.5 per further open signal (at most 5).
`suggested_key` comes from the strongest signal that names a letter (official key, key changed after a
decision, evidence conflict, confident printed key, explanation, answer label, unchecked printed key, AI
review) and is never applied.

### Signals that open a review

| Signal | Priority | Source |
|---|---|---|
| `official_key_disagrees` | 100 | imported official key (`import_review_signals`) |
| `source_key_mismatch` | 95 | confident printed key (stem found in the source, option text matched) |
| `evidence_conflict` | 92 | latest audit `EvidenceRun` made after the last edit |
| `invalid_or_missing_key`, `explanation_states_other` | 90 | the question (`key_audit.explanation_check`) |
| `label_key_conflict`, `human_requested_review` | 85 | answer label / tick in the text; an admin |
| `open_wrong_answer_report`, `key_changed_after_review` | 80 | `QuestionFeedback` (`wrong_answer`, open); history |
| `source_key_mismatch_unverified` | 75 | printed key whose stem or option order was not confirmed |
| `ai_review_disagrees` | 70 / 55 / 40 | AI review, by its confidence |
| `duplicate_key_conflict` | 65 | duplicate cluster with another answer text |
| `skewed_key_distribution` | 60 | one letter holds >= 60 % of >= 50 active questions of an exam year (importer default), unless a confident printed key agrees |
| `is_disputed` | 60 | the flag |
| `ai_no_correct_option`, `label_hold`, `ai_content_defect`, `ai_ambiguous` | 55-35 | AI-reported content problems; text holding an answer label |

Shown but not opening a review: `image_context_missing` (gives its own status), `ai_chosen_key` (legacy
CMS importers stored an LLM's pick), `source_year_differs`, `needs_review_flag`, `ai_answer_in_text`,
`ai_wrong_subject`, `explanation_conflicts_with_reviewed_key`, `stale_reviews_ignored`.

## 3. Data and commands

| Model (`key_audit`) | Holds |
|---|---|
| `QuestionAudit` | one row per question: status, reason, stored / original key, key provenance, suggested key, priority, signals, imported reviews, evidence summary, `content_changed_at` |
| `SourceKey` | the key a source document prints for a question: file name (+ sha256), PDF page, question number, answer page, chapter, printed letter, letter in the bank's option order, `option_order`, `method`, `located`, `stem_hash` |
| `AuditResolution` | an admin decision (immutable): resolution, reason, evidence, key change, the key and `stem_hash` it was made for |
| `ReviewClaim` | a 15-minute claim on a question by one reviewer |

```bash
# where the source documents are (the local corpus): recover the printed keys (read-only)
DJANGO_ENV_FILE=.env.localdev python -m ai_eval.recover_source_keys \
    --registry <reference_corpus>/registry.json --inventory <pdf_inventory.json> --out source_keys.jsonl

# anywhere: load signals (dry run first; lines made for other content are skipped and counted)
python manage.py import_source_keys source_keys.jsonl            # then --apply
python manage.py import_review_signals reviews.jsonl --source <label>   # then --apply

# classify (dry run by default; --apply writes QuestionAudit and mirrors Question.answer_key_status)
python manage.py audit_answer_keys [--exam neet_pg] [--ids 1,2] [--stale-only] [--run-evidence] [--json]
```

`import_review_signals` takes AI reviews and official keys in the `key_audit.reviews` format plus
`question_id` and `stem_hash`; human decisions cannot be imported. A re-imported review with the same
verdict keeps its first timestamp, so importing a file again does not reopen decided questions.
Every key / stem / option change re-audits the question (`key_audit.services.on_question_changed`).

**UPSC CMS 2014–2025 official keys (2026-11-07 / 08).** `questions.0047` made the bank match the official papers
and UPSC answer keys for 2018–2025 (`docs/audit/CMS_OFFICIAL_2018_2025.md`), `questions.0049` completed 2014–2017
from the same PDF (`docs/audit/CMS_OFFICIAL_2014_2017.md`); key changes are `AnswerKeyChange` rows with
`source='official_key'` and `official_key` evidence (PDF, sha256, key page, cell). The release step
`python manage.py record_official_cms_keys --apply` then records UPSC's key as an `official_key` review for every
active question of those papers (found by year, paper and `display_number`; none for a question UPSC dropped, none
for a key the data file holds for review: 2015 Paper II Q60, printed "Dc"), so they are `verified` /
`official_key_match`, and an admin change away from the official key becomes `needs_review` /
`official_key_disagrees`. It records only what is missing; a dry run reports the counts. 2026 has no official key
yet (`docs/audit/CMS_OFFICIAL_2026.md`).

## 4. Review queue

Page: `/admin/review-queue` (admin role). API under `/api/key-audit/` (`IsControlTowerAdmin`, throttle
scope `review_queue`):

| Method | Path | |
|---|---|---|
| GET | `queue/` | audits by priority; `status` (comma list), `reason`, `exam`, `year`, `suggested_from`, `has_suggestion=true`, `unclaimed=true` (hides other reviewers' claims), `q` (question id), `include_inactive=true` |
| GET | `queue/summary/` | counts by status, reason, open signal (cached 1 min), suggestion source |
| GET | `queue/<id>/` | question, signals, printed source keys, reviews (labelled), decisions, key history, claim |
| POST / DELETE | `queue/<id>/claim/` | claim for 15 minutes (409 if another reviewer holds it) / release |
| POST | `queue/<id>/resolve/` | `{resolution, reason (>= 10), new_key?, expected_key?, evidence[], explanation_fields?}`; 409 when claimed by someone else or when the key changed since `expected_key` was loaded |
| POST | `queue/accept-source-keys/` | `{reason, items: [{question_id, expected_key, source_key_id}]}` (<= 25): each ticked question whose confident printed key was recovered for its current content becomes its own key change (result "likely correct") |

Resolutions: `key_confirmed`, `key_changed` (through `change_answer_key`), `deferred`, `image_requested`,
`explanation_fixed` (explanation / concept explanation / mnemonic only), `dropped` (`is_dropped`),
`question_deactivated`. Evidence kinds: `official_key`, `errata`, `guideline_url` (http/https),
`passage` (title, page, quoted sentence), `source_key` (a `SourceKey` of this question), `note`. Every
decision is also an `AdminAuditLog` row (`audit_resolution`). The editor's Verify / Unverify record a
`key_confirmed` / `deferred` decision too (without evidence: "likely correct").

## 5. Results on the local restore (`crack_local`, 2026-11-03)

Measured with the commands above; every number is reproducible from them.

* Printed keys: `recover_source_keys` read 64 source files for 6,490 questions: 5,085 with one printed
  letter (1,276 without one, 129 ambiguous). Against the stored keys: 2,045 confident mismatches,
  1,407 confident matches, 561 unchecked mismatches, 1,072 unchecked matches. Compared with the
  2026-11-02 prototype run, 1,140 more keys come from DOCX files the corpus builder now reads; where both
  runs found a letter they agree for 3,813 questions and differ for 102 (newer glyph repair and option
  mapping; not adjudicated).
* AI first pass: 2,634 reviews imported (agree 1,121, unanswerable 1,043, disagree 416, uncertain 54),
  all for unchanged content.
* Audit of the 10,013 active questions: `needs_review` 3,829, `insufficient_evidence` 5,952,
  `likely_correct` 170, `image_context_missing` 62, `verified` 0, `contradictory_sources` 0. Main reasons
  in review: confident printed-key mismatch 1,934, unchecked printed-key mismatch 526, skewed key
  distribution 520, invalid key 380, AI-reported content defect 246. Suggested keys: 2,685.
* Skewed exam years (share keyed `A`): NEET PG 2025 90.8 % of 3,540, NEET PG 2018 95.9 % of 244,
  NEET PG 2020 95.5 % of 88, NEET PG 2021 70.2 % of 332, INI-CET 2025 92.9 % of 98.
* 1,810 CMS questions come from `PYQ_<year>_Paper<n>.txt` imports whose keys an LLM chose.
* Spot check of three confident mismatches against the PDFs: the answer-key table on the recorded page
  prints the recovered letter each time; in the two cases checkable from the text alone the printed key
  is the medically correct answer and the stored `A` is not.
* Import defects seen in the queue (not repaired yet): 135 questions (NEET PG 2025: 124, INI-CET 2025:
  11) whose option D holds the source's answer-key table instead of the option (113 with the real
  option text before the table, 22 with nothing else); 515 NEET PG 2025 stems that start with ":".
  The existing `fix_answer_label_leaks` covers the first kind; its dry run on the restore: 758 questions
  with answer labels in the text, 673 to repair (245 empty keys filled from the printed label, now
  through `change_answer_key`, source `management_command`; 33 conflicts with the stored key kept), 85 to
  deactivate for manual review. A repair changes the content hash: repair first, then recover and import
  the signals again.
* Reviewed one-off repairs (2026-11-07): `questions/content_repairs.py`, applied once per database by
  migration `questions.0045`. A repair names one question, the key it must still hold and the defect text
  it must still contain (an admin's later edit wins; a second run changes nothing), stores a
  `QuestionRevisionSnapshot` first (the editor shows it and can undo it) and never changes a key.
  - #2058, #2065, #2103, #2113 (CMS 2025 Paper I): the key had been corrected (`key_changed` B->C, A->C,
    B->D, A->D) but the locked explanation still argued for the old key. The explanations were rewritten
    for the current keys, which standard teaching supports (pellagra and maize; osteoarthritis spares the
    ankle and involves C5-C6; CHIPES radiopaque poisons; the RBSK "Deficiencies" group). The new text is
    AI-written: `explanation_origin` `ai`, `explanation_status` `ai_generated` until an admin reviews it.
  - #22462 (CMS 2022 Paper II Q118): the five Apgar observations were missing from the stem; restored
    from `Medura_Train/PYQ/2022paper2.txt` (they score 3, the stored key C) with the worked score added to
    the explanation (`explanation_origin` `mixed`). The stem hash changed: its source-key signals are
    re-read on the next `recover_source_keys` run.
* Hidden questions (2026-11-07, migration `questions.0046`, `content_repairs.HIDES_2026_11_07`). The owner's
  rule: a question is never hidden or deleted unless it is a duplicate or wrong; a question that says "shown in
  the image" gets its figure, it is not hidden. Hidden after the owner's approval:
  - three duplicates (#12605 of #12321; #22456 of #6477 and #22631 of #2210, both without their data table);
  - two seed demo questions whose image never existed (#26454, #26451);
  - two NEET PG questions whose source book omits the data they ask about (#15370, #15618).
  Each is hidden only while it still holds the content it was judged on, a duplicate only while its kept copy
  is live with the same key, after a revision snapshot; nothing is deleted.
* Figure audit (2026-11-07): 540 active or held-back questions said a figure is shown but had none. 511
  figures were extracted from their source PDFs, each checked against the question's own options and by eye,
  and are attached by the owner's command (`prod_attach_figures.py`; the bytes go through `ops_media_transfer`).
  The 14 CMS 2026 figure questions wait for the official UPSC paper (the solution PDFs only describe the
  figures). Bank-wide, 589 groups of active duplicates remain (533 extra copies with the same key, 72 whose
  copies disagree on the key): an owner decision, because hiding them changes the bank counts the site shows.

## 6. Production rollout (`cracklabs`)

Nothing of this runs on its own: the deploy does not run migrations yet (see `DEPLOY_RAILWAY.md`).

1. Merge the branch and deploy.
2. Migrate `cracklabs`: `questions.0042_medical_accuracy_schema` (adds the provenance fields; backfills one
   `QuestionAttemptLog` row per existing `QuestionAttempt` and files combined topic notes under
   `exam_type='all'`), `evidence.0001`, `reference_corpus.0001`, `key_audit.0001`, `key_audit.0002`.
   Check first with `python manage.py migrate --plan`.
3. Optional, an owner decision: `fix_answer_label_leaks` (dry run, then `--apply`) on the restore and on
   `cracklabs` alike. It hides the 85 rows it cannot repair from students until they are fixed. Because
   it changes the content, run `ai_eval.recover_source_keys` on the restore again afterwards (the printed
   keys are re-read against the repaired text); the AI reviews of repaired questions were made on the
   old text and are skipped by the hash check, as they should be.
4. Dry-run, then apply, the imports against `cracklabs` with the files made on the local restore
   (`source_keys_v2.jsonl`, `pass1_reviews_hashed.jsonl`): lines whose question changed in production
   since the restore are skipped by the hash check.
5. `audit_answer_keys` (dry run), then `--apply`.
6. Review in `/admin/review-queue`: start with "Printed key differs".
