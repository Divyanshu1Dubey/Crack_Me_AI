# Textbook RAG — retrieval benchmark (2026-11-01)

Everything below was measured on this machine by `backend/ai_eval/rag_benchmark.py` (raw output: [`rag/benchmark_results.json`](rag/benchmark_results.json), evaluation set: [`rag/eval_set_ANS.jsonl`](rag/eval_set_ANS.jsonl)). No number in this file was estimated or typed by hand from memory; re-run with

```bash
cd backend
DJANGO_ENV_FILE=.env.localdev python -m ai_eval.rag_benchmark --out ../docs/audit/rag
```

(needs the restored question bank in the local database; reads the RAG store read-only; makes no LLM calls; ~5 minutes).

## What was wrong (verified before changing anything)

| Problem in the old `RAGPipeline.search` | Effect |
|---|---|
| Stopped after the first `RAG_MAX_SEARCH_CHUNKS` = 2,000 rows in rowid order | 74 % of the 7,823 chunks (267 of 274 books, every topic note) were never searched; results came almost only from the two copies of the Ghai paediatrics PDF |
| IDF fetched with one SQL query per term per chunk | ~3.5 s per search on this machine (measured below) |
| Same files indexed under 2–3 book names with different chunk sizes | a third of every top 5 was a duplicate passage |
| Tokenizer dropped every non-ASCII character | `β-blocker` → `-blocker`, `Sjögren` → `sj gren` |
| Personal/administrative PDFs and an internal business document in the store | retrievable by any student query (now excluded; owner review still needed, see below) |
| Pipeline constructor ran `PRAGMA journal_mode=WAL`, DDL and `COMMIT` on the git-tracked store on every request | — |
| Total provider failure returned *"AI answer generation is unavailable. Please configure API keys."* as the answer | operator text shown to students |

## What ships now

`backend/ai_engine/lexical_index.py` + `RAGPipeline.search`:

* **Okapi BM25 over the whole store** from an in-memory inverted index (built once per process in ~3–5 s, rebuilt automatically when the store file changes).
* **Tokenizer**: NFKC/NFKD folding, Greek letters → names (`β` → `beta`), diacritics stripped, hyphens/slashes split, stopwords, conservative plural stemmer (Harman).
* **Corpus policy**: one indexing pass per source file (keeps the finest chunking; 3,327 alias copies dropped), exact-duplicate content dropped (10), personal/administrative documents and the internal business document never returned (60 chunks), raw question papers returned only when a caller asks for that book (they are question text and answer keys, not explanations).
* **No writes on construction**; AI clients created lazily.
* **Offline / failure path**: with `AI_OFFLINE_MODE=1`, or when every provider fails, `rag_answer` returns an *extractive* answer — the passage sentences that best match the question, each with its `[book p.page]` citation, flagged `generated: false` so callers can avoid charging for it.
* **Confidence label** from the top hit's score normalised by the query's maximum possible score (see calibration).

Regression tests: `backend/ai_eval/tests_rag_retrieval.py` (14 tests: whole-store reach past row 2,000, corpus policy, Greek/diacritics, read-only constructor, rebuild on change, offline and total-failure answers, `n_results` clamping).

## Results

### Answer-bearing retrieval (ANS) — held-out test split (UPSC CMS PYQs 2022–2025, n = 117)

| Retriever | success@1 | success@5 | success@10 | precision@5 | MRR@10 | nDCG@10 | dup in top 5 | question-paper share of top 5 | median latency |
|---|---|---|---|---|---|---|---|---|---|
| **Old production** (`prod_tfidf_cap2000`) | 0.128 | 0.239 | 0.248 | 0.075 | 0.168 | 0.110 | 33 % | 11 % | **3,454 ms** (p95 5,757 ms)¹ |
| Old scoring, whole store (`tfidf_nocap`) | 0.180 | 0.316 | 0.333 | 0.099 | 0.229 | 0.162 | 44 % | 48 % | 30 ms² |
| BM25, whole store, no corpus policy | 0.188 | 0.444 | 0.504 | 0.156 | 0.301 | 0.250 | 47 % | 57 % | 12 ms |
| **BM25 + corpus policy (shipped)** | **0.333** | **0.547** | **0.607** | **0.179** | **0.431** | **0.318** | **0 %** | **0 %** | **2.0 ms** (p95 4.9 ms) |
| ablation: no plural stemming | 0.325 | 0.556 | 0.607 | 0.176 | 0.420 | 0.314 | 0 % | 0 % | 1.7 ms |
| ablation: BM25 k1 1.5, b 0.6 | 0.350 | 0.547 | 0.607 | 0.181 | 0.440 | 0.319 | 0 % | 0 % | 2.8 ms |
| SQLite FTS5 `bm25()` (porter, unicode61) + policy | 0.385 | 0.530 | 0.641 | 0.183 | 0.454 | 0.336 | 0 % | 0 % | 3.0 ms |

¹ The real old code path (IDF fetched with one SQL query per term), measured on 25 test queries. ² The other old-scoring rows use a faithful replica with IDF in a dict (identical scores, much faster) so the whole set could be evaluated.

**Paired bootstrap, shipped vs old production (test, 1,000 resamples, 95 % CI of the difference):** success@5 **+0.31** [+0.21, +0.41]; MRR **+0.26** [+0.19, +0.34]; nDCG@10 **+0.21** [+0.16, +0.26]. Removing the cap alone (`tfidf_nocap`) is *not* significant on this set (success@5 CI [−0.03, +0.18]); the gains come from BM25, the tokenizer and the corpus policy together.

### Topic-note retrieval (TOPIC, silver labels) — test split (n = 132)

| Retriever | success@1 | success@5 | MRR@10 | nDCG@10 |
|---|---|---|---|---|
| Old production | **0.000** | **0.000** | **0.000** | **0.000** |
| Old scoring, whole store | 0.220 | 0.439 | 0.310 | 0.200 |
| **Shipped** | **0.311** | **0.629** | **0.435** | **0.308** |
| FTS5 + policy | 0.303 | 0.591 | 0.419 | 0.296 |

The old production retriever scored zero because every topic note sits beyond row 2,000.

### Coverage smoke test (KNOWN) — all dated CMS stems found in a question paper (n = 1,306)

| Retriever | success@1 | success@5 | MRR |
|---|---|---|---|
| Old production | 0.039 | 0.048 | 0.042 |
| Old scoring, whole store | 0.635 | 0.832 | 0.714 |
| **Shipped (question papers included on request)** | **0.885** | **0.981** | **0.926** |

### Choosing the configuration (dev split 2018–2021, n = 146 ANS / 126 TOPIC)

| | ANS MRR | ANS success@5 | TOPIC MRR | TOPIC success@5 |
|---|---|---|---|---|
| **Shipped (k1 1.2, b 0.75, stemming)** | **0.374** | 0.507 | 0.504 | 0.627 |
| no stemming | 0.360 | 0.520 | 0.488 | 0.635 |
| k1 1.5, b 0.6 | 0.364 | 0.493 | 0.519 | 0.651 |
| FTS5 | 0.359 | 0.541 | 0.447 | 0.564 |

Decisions were made on dev only. The BM25 variants are within noise of each other (test CIs overlap almost completely); the default parameters had the best answer-retrieval MRR on dev and were kept. FTS5 was not better on dev MRR or on topics, so the dependency-free index was kept.

### Offline (no-LLM) answers — test split

| Retrieval feeding the extractive composer | answered | answer contains the correct option | verbatim-faithful answers |
|---|---|---|---|
| Old production | 105 / 117 | 14 (12.0 %) | 105 / 105 |
| **Shipped** | 114 / 117 | **43 (36.8 %)** | 114 / 114 |
| BM25 without corpus policy | 116 / 117 | 56 (47.9 %) | 116 / 116 |

"Faithful" = every answer sentence occurs verbatim in the passage it cites (true by construction; checked programmatically). The no-policy row looks better only because it retrieves raw question papers, which contain the same questions *with their answer keys* — leakage, not knowledge. Correct-option containment is a coarse proxy for correctness; offline answers are labelled as extracts, never as AI answers.

### Confidence calibration (dev split)

Raw BM25 top scores did **not** predict relevance (top-1 precision ≈ 0.29 at every threshold; longer stems simply score higher). The top score divided by the query's maximum possible score does somewhat: at ≥ 0.3 a relevant passage is in the top 5 for 64 % of dev queries (51 % overall) and the top hit is relevant 42 % of the time. No threshold is reliable enough to justify "high", so the label is `medium` (≥ 0.3) or `low` (`RAG_CONFIDENCE_MEDIUM_NORM`).

## Methodology

**Corpus.** `backend/chroma_db/rag_store.sqlite3` as committed (7,823 chunks, 274 book names), opened read-only. No re-chunking, so every retriever sees exactly the text the product serves.

**Datasets** — built from the restored production question bank; no relevance judgement was written by hand or by an LLM:

* **ANS — answer-bearing passage retrieval (primary).** Dated UPSC CMS PYQs 2018–2025, one copy per stem (1,876 candidates). Query = the cleaned stem (numbering, options and answer lines removed). A chunk is relevant when it is study material (not a raw question paper, not an excluded document), contains the *full text of the correct option*, and contains at least one *distinctive stem term* (document frequency ≤ 2 %). Dropped: 543 generic options ("all of the above", bare numbers), 2 stems already containing the option (leakage), 73 stems without a distinctive term, and **995 questions whose answer text appears in no study-material chunk** — the corpus simply does not cover them. 263 queries remain: dev 146 (2018–2021), test 117 (2022–2025).
* **TOPIC (silver).** Stems that mention the subject of one of 40 topic notes (e.g. "malaria" → `med_malaria.md`); relevant = every chunk of that note under any alias. Silver: mentioning a topic is not the same as the note answering the question.
* **KNOWN (coverage smoke test).** Dated CMS stems whose first 60 normalised characters occur in a question-paper chunk; relevant = those chunks. Only checks that the whole store is reachable.

**Metrics.** Rankings are de-duplicated by chunk content before scoring. success@k = a relevant chunk in the top k (Recall@k for answer-bearing retrieval); precision@5; MRR@10; nDCG@10 with binary gains; raw top-5 duplicate rate and question-paper share; median / p95 latency per query on this machine; 95 % bootstrap CIs (1,000 resamples, paired with the old production retriever).

## Limitations — read before quoting these numbers

* **Coverage, not ranking, is now the main limit.** Only 263 of 1,876 dated CMS PYQs have their answer text anywhere in the study material; the store is dominated by one paediatrics textbook and short notes. Better retrieval cannot fix missing content.
* Sample sizes are modest (117 / 132 test queries); CIs are wide and reported.
* Labels are proxies: answer-text containment can miss paraphrased answers (under-counting every retriever equally) and the TOPIC set is silver.
* Lexical self-similarity favours lexical retrievers; there is no dense baseline (below).

## Not done (and why)

* **Dense / hybrid retrieval and cross-encoder re-ranking were not benchmarked.** No embedding model can run here without new heavy dependencies (no torch, sentence-transformers or fastembed; the cached MiniLM models have no ONNX export), and whether the production host could run one is unverified. The knowledge-base app's existing "hybrid" search silently replaces query embeddings with SHA-256 pseudo-random vectors when sentence-transformers is missing (reported to the AI fix group).
* **Answer generation quality (LLM faithfulness)** was not measured — that would require calling external LLM providers, which this local run deliberately avoids.

## Needs the owner

* Store contents: personal/administrative PDFs (affidavit, disability certificate, application form, caste/EWS proformas, travel-allowance forms) and an internal business document were indexed and are tracked in git under `backend/Medura_Train/`. They are now never retrieved, but they should be reviewed and removed from the repository and its history.
* Licensing: ~2,000 chunks come from full copies of a commercial paediatrics textbook (and `final (1).pdf`, a 371-page document of unknown origin). The project's own knowledge-base licence policy disallows such sources.
