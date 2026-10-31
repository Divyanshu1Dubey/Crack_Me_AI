# Question-bank data quality (restored backup, 2026-11-01)

Measured on the local restore of the production database (`crack_local`). Nothing here was changed in production.

## 1. NEET PG subject tags are unreliable — measured

* 3,372 active NEET PG questions come from per-subject PYQ compilations whose file name states the subject (`Medicine pyqs.pdf`, `PSM pyqs.pdf`, `Anatomy pyqs.pdf`, …). Their stored subject agrees with that file-level subject for only **1,679 (49.8 %)**. The stored tags look like the output of a keyword heuristic: e.g. all 159 tagged-Anaesthesia questions from `PSM pyqs.pdf` are community-medicine questions (clinical-trial statistics, Pap-smear screening, Global Hunger Index…).
* Full papers were tagged the same way: the 2021 paper has 199 of its 510 questions tagged Anaesthesia, 2018 has 74 of 321.
* A TF-IDF + logistic-regression classifier trained on the file-level labels reaches **63.1 % accuracy / 0.60 macro-F1** in 5-fold cross-validation (15 subjects, one copy per stem). Medical subjects overlap heavily, so its 2,079 suggestions for questions without a file-level subject are mostly low-confidence (1,769 below 0.7; 71 at ≥ 0.9) — they are for human review only.

**Tool:** `backend/ai_eval/subject_audit.py` — writes `docs/audit/data_quality/subject_audit.json` (metrics) and a review CSV (question id, current → suggested subject, confidence, method, stem preview). `--apply-local` (refused unless `DEBUG`) applies **only** the 1,693 deterministic file-level corrections.

**Local database:** the 1,693 file-level corrections were applied to `crack_local` (original values preserved in `C:\Users\DIVYANSHU\crack_local\data_quality\subject_suggestions_before_apply.csv`). Largest moves: Anaesthesia → Community Medicine 159, ENT → OBG 96, ENT → General Medicine 95, Radiodiagnosis → General Medicine 57.

**Production:** owner decision. Apply the same file-level corrections (deterministic) after a spot check; route classifier suggestions through admin review.

## 2. Placeholder subjects

1,285 CMS questions sit in the subject "Expert Curated" and 541 in "Imported" — import buckets, not subjects. They do not appear in subject-wise practice or analytics as real subjects. The audit CSV includes classifier suggestions for them (same caveats as above).

## 3. Other issues found during the audit

| Issue | Evidence | Status |
|---|---|---|
| Deploy-time `import_neet_pg` deleted and re-created its rows on every deploy, defaulting unknown answers to "A" and creating them with `exam_type='cms'` | `backend/questions/management/commands/import_neet_pg.py`; only 3 such rows exist in the restored data, so production probably no longer runs `build.sh` | being made non-destructive and removed from `build.sh` (fix wave 1, infra group) |
| Duplicate merge keyed only on the normalised stem | 64 merged pairs share ≤ 1 answer option (distinct questions soft-dropped from the bank); 444 clusters have conflicting answer text | reversible (soft-drop); review CSV recommended |
| 7,266 rows flagged `needs_review`, 19 `is_disputed` | `questions_question` | unchanged |
| 5,318 CMS rows have `year = 0` | mostly "Expert Curated"; 768 of the year-0 stems near-duplicate dated PYQs | unchanged |
| Stems keep source numbering ("37. A child…") and stray punctuation ("; The presence…") | visible in the question bank and Mistake Notebook | display unchanged (the bank shows them too) |
| 27,055-type rows: an AI outage message stored as a question's explanation | Q27055 holds "All AI services are temporarily unavailable…" | the code path is being fixed (AI group); the row needs a manual clear |
