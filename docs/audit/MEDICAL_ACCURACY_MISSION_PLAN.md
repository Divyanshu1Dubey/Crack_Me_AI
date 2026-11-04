# Medical accuracy mission — plan (2026-11-01)

Branch `medical-accuracy` (from `overnight-mission` @ `9a9643b`, tag `medical-accuracy-start`), worktree `C:\Users\DIVYANSHU\Desktop\crack_cms\.claude\worktrees\full-audit-fixes`. Nothing is pushed or deployed; no production credentials are used; no real user is contacted. Local data: the isolated PostgreSQL restore (`crack_restore` pristine, `crack_local` working copy, 127.0.0.1:55432).

## Ground rules for medical content

1. **An answer key is never changed automatically.** The audit only classifies (VERIFIED, LIKELY CORRECT, NEEDS REVIEW, CONTRADICTORY SOURCES, INSUFFICIENT EVIDENCE, IMAGE CONTEXT MISSING) and stores evidence. Changing a key is an explicit admin action that keeps the original key, who changed it, why, and the evidence (revision snapshot + audit trail).
2. **AI output is never a source.** AI reviewers produce verdicts with reasoning; only passages from reference documents (book, edition, page) count as evidence. No invented titles, editions, pages or quotations: every citation must resolve to a stored passage.
3. **The AI may abstain.** When retrieved evidence does not establish the answer, the system says so instead of producing a justification.
4. **Explanations must not defend a key the evidence contradicts.** Generation answers from evidence first and reports a conflict with the stored/selected key instead of explaining it away.
5. **Copyrighted books are for internal retrieval and verification.** Students see citations (book, edition, chapter, page) and short snippets; full page images are admin-only.
6. **No external LLM calls with production keys** in this run (`AI_OFFLINE_MODE=1`). Where an LLM is needed for evaluation or review, independent Claude subagents are used and labelled as such; their verdicts are review signals, not sources. A `--live` path lets the owner run the same evaluation with the production providers.

## Baseline (measured before any change)

| | |
|---|---|
| Supabase Auth in the restored backup | complete: 147 users (all emails confirmed), 77 email/password users with bcrypt hashes, 78 Google identities with the Google account id (`sub`), 8 users with both; 125 of 127 Django users match an auth user by email; 22 auth users have no Django row |
| Question bank (active) | 10,013 (CMS 5,523, NEET PG 4,389, INI-CET 101); 380 without a valid A–D key; 4,858 with no explanation; 0 with structured references; 1 verified by an admin; 4,894 flagged `needs_review`; 19 disputed |
| Answer-key risk signals | 425 of 2,819 duplicate clusters disagree on the key; 21 questions whose key differs from an earlier revision; 12 open "wrong answer" reports from students; 744 questions with answer labels / ticks inside the question text (20 tick-vs-key conflicts) |
| Images | 756 questions with 4,135 images; 569 questions that mention an image but have none attached; 82 flagged image-based |
| Local medical sources | 539 documents (~57,000 pages): Harrison 17e, Nelson Pediatrics, Ghai 9e, Park PSM (scanned: needs OCR), ~100 UPSC CMS unit notes (DOCX), INI-CET / NEET PG material, UPSC CMS papers 2018–2024 |
| Current RAG store | 7,823 chunks; only 263 of 1,876 dated CMS PYQs have their answer text anywhere in it (`docs/audit/RAG_BENCHMARK.md`) |

## Phases, in priority order

| # | Phase | Deliverable | How it is verified |
|---|---|---|---|
| 1 | Plan + discovery | this plan; code maps of auth, RAG/AI, editor, images, PYQ notes, study features, performance (read-only agents) | progress log |
| 2 | **User and OAuth recovery** | recovery report; `import_supabase_auth` command (dry run by default) that links Django users to their Supabase identity, creates the 22 missing users with their original ids, keeps bcrypt hashes usable, and records Google `sub`s; Django-native sign-in (email/password + Google ID token matched on `sub`, never on email alone) behind `AUTH_PROVIDER=django`, default unchanged | unit tests (no duplicates, no email takeover, password and Google paths), dry run against the restore, E2E |
| 3 | **Answer-key audit** | `audit_answer_keys` command + `QuestionAudit` records: deterministic signals for every question, evidence retrieval per option, independent AI review of the flagged set (2 reviewers where they disagree with the key), classification; admin review queue | counts reproducible from the command; sample checks; regression tests for the known bad keys |
| 4 | **Reference corpus** | source registry (title, edition, year, tier, licence, file hash); page-aware ingestion of the local textbooks and notes incl. OCR for scanned books and DOCX notes; page images available to admins | per-source page coverage report; no invented metadata |
| 5–6 | **RAG accuracy** | hybrid retrieval (BM25 + dense embeddings, fused) with optional reranking, chosen on a dev split and reported on a held-out split; evidence-first answering with citation verification, key-conflict detection and abstention; benchmark incl. abstention and image cases | Recall@k, MRR, nDCG, answer correctness, faithfulness, citation correctness, abstention accuracy, latency — real data only |
| 7 | **Editor workflow** | select option → AI Explain for that option → cited explanation (or a conflict warning) → edit → save → next; provenance status (AI-generated, human-edited, source-verified, reviewed, pending) | backend tests + E2E |
| 8 | **Images + evidence pages** | question → evidence (book, chapter, page, figure) records; page/figure viewer (admin full, student citation + snippet); zoom; image-aware explanation path for vision-capable providers | tests + E2E |
| 9 | **PYQ-first notes** | high-yield topic notes built from verified PYQs with question and source references; provisional marking when keys are unverified | tests |
| 10 | Study features | inventory; only small, high-value gaps (e.g. option distribution, attempt history) | tests |
| 11 | **Performance** | measured backend latencies, query counts, bundle sizes; root-cause fixes; before/after | numbers from real runs |
| 12–13 | UI + QA | evidence presentation, editor polish; full backend/frontend suites; Playwright on 3 viewports | test output |
| 15 | Report | `MEDICAL_ACCURACY_MISSION_FINAL_REPORT.md` | — |

Work runs in file-disjoint agent groups with independent reviewers (as in the previous mission), heavy commands through the memory-limited wrapper, commits per group.
