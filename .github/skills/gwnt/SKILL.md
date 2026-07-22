---
name: gwnt
description: 'Generate, validate, and publish new knowledge-base content for CrackCMS (Monica AI). Use this skill when adding new textbook chapters, medical notes, ontology entities, or whitelisted-source documents to backend/knowledge_base/. Triggers: "add notes for X", "ingest this MD file", "extend ontology", "add new KB source", "publish KB content". Do NOT use this skill for question-bank edits (use the QUESTION_MANAGEMENT guide instead) or for AI-engine RAG/legacy chroma_db operations.'
license: MIT
metadata:
  version: "1.0.0"
  app: "knowledge_base"
  related:
    - docs/knowledge-base/SETUP.md
    - docs/mcp/README.md
    - llms-full.txt
argument-hint: 'Optional: target topic or file path, e.g. "DKA chapter notes" or "Medura_Train/textbooks/nephrotic_syndrome.md"'
---

# Generate and Publish Knowledge Base Content (GWNT)

> Workflow skill for safely adding new content to CrackCMS Monica AI knowledge base.
> Steps: prepare → ingest → dedupe → embed → eval → publish.

This skill assumes you have:

- Backend running locally (`python manage.py runserver`)
- A `superuser` account in Django admin OR a service token
- File(s) you want to ingest (Markdown notes, plain text, or PDF under 50 MB)
- Confirmed the source is on the whitelist (UPSC, MoHFW India, NHM India, NMC India, ICMR, NCBI, WHO, NHS, CDC, NICE, OpenMD, KEGG, DrugBank) OR it is your own original notes

---

## 1. Output Contract (Required)

Before finishing, all of the following must be true:

1. New content lives under `backend/Medura_Train/textbooks/` or `backend/Medura_Train/web_knowledge/`.
2. No copyrighted textbook excerpts (Harrison's, Bailey & Love, Marrow, PrepLadder) are added — refuse if asked.
3. `python manage.py ingest_source internal-notes` ran and reported `+N added` (or `+0` if everything was a duplicate).
4. `python manage.py shell -c "from knowledge_base.services.indexer import EmbeddingIndexer; print(EmbeddingIndexer().index_pending(max_chunks=N))"` ran and reported > 0 chunks embedded (or the value is exactly 0 and you confirm there are no new chunks).
5. `python manage.py evaluate_kb` ran and the recall@k metric did not regress by more than 0.05.
6. Commit message references the topic and the source file path(s).
7. If the source is whitelisted but new (e.g. a brand-new CDC page), the connector registry at `backend/knowledge_base/connectors/__init__.py` is updated and `python manage.py ingest_source <new-name>` works.

---

## 2. Workflow

Copy and track this checklist:

```
- [ ] Phase 1: Verify content origin (whitelisted or original)
- [ ] Phase 2: Place file in Medura_Train/{textbooks,web_knowledge}/
- [ ] Phase 3: Run ingest_source internal-notes
- [ ] Phase 4: Run EmbeddingIndexer.index_pending
- [ ] Phase 5: Run evaluate_kb (compare before/after)
- [ ] Phase 6: Sample 5 kb_ask queries; verify citations include new content
- [ ] Phase 7: Commit with conventional message
```

---

## 3. Phase 1 — Verify content origin

Before adding anything, check the source:

| Source type | Allowed? | Action |
|---|---|---|
| Your own original notes (.md / .txt) | Yes | Proceed |
| Public-domain or CC-BY (WHO, CDC, NHS, OpenMD, NCBI Bookshelf, KEGG, DrugBank) | Yes | Add `source:` frontmatter |
| MoHFW / NHM / NMC / ICMR public documents | Yes | Add `source: mohfw-india` etc. |
| Harrison's, Bailey & Love, Marrow, PrepLadder | **No** | Refuse. Suggest the user paraphrase or quote briefly with attribution |
| Any other textbook with active copyright | **No** | Refuse |
| ChatGPT / Gemini / other LLM output (uncited) | Discouraged | Verify factual accuracy before ingesting |

If uncertain, ask the user before proceeding.

---

## 4. Phase 2 — Place file

Drop the file in one of these folders under `backend/`:

```
Medura_Train/
├── textbooks/        # Textbook-style material (chapters, summaries)
├── PYQ/              # Prior-year questions (use QUESTION_MANAGEMENT for these)
└── web_knowledge/    # Web-sourced material (notes, summaries, FAQs)
```

Naming convention: `snake_case_topic.md` or `snake_case_topic.txt`.

Add YAML frontmatter for traceability:

```markdown
---
title: Diabetic Ketoacidosis — Management
source: original-notes
exam_track: upsc-cms
subject: Medicine
topics: [DKA, endocrinology, acid-base]
last_reviewed: 2026-07-22
---

# Diabetic Ketoacidosis — Management

## Diagnostic criteria
- Blood glucose > 250 mg/dL
- Arterial pH < 7.3
- Serum bicarbonate < 18 mEq/L
- Positive serum/urine ketones

## Initial management
1. IV fluids — isotonic saline 15–20 mL/kg in the first hour
2. IV regular insulin 0.1 U/kg bolus, then 0.1 U/kg/hr infusion
3. Potassium replacement when K+ < 5.2 mEq/L
4. Monitor glucose hourly; anion gap every 2–4 hours
```

Frontmatter fields are picked up by `connectors/internal.py` and stored as `Entity` / `Relation` rows in the knowledge graph.

---

## 5. Phase 3 — Ingest

```bash
cd backend
python manage.py ingest_source internal-notes
```

Expected output:

```
Loaded 12 internal docs; +N added, M skipped (duplicate)
```

`+0 added` is fine — it means the file was already present (idempotent via `text_hash`). Confirm by checking `knowledge_base_source` table for the new file's `text_hash`.

---

## 6. Phase 4 — Embed

```bash
python manage.py shell -c "
from knowledge_base.services.indexer import EmbeddingIndexer
print('Indexed', EmbeddingIndexer().index_pending(max_chunks=5000), 'chunks')
"
```

If this prints 0 but you added new content, check the embedding model name in `services/embedding.py` matches `services/indexer.py` (mismatch is the most common cause of "embedded but not indexed").

---

## 7. Phase 5 — Evaluate

```bash
python manage.py evaluate_kb
```

Before/after:

```bash
python manage.py shell -c "
from knowledge_base.models import EvalResult
last = EvalResult.objects.order_by('-created_at').first()
print('recall@5:', last.recall_at_5, 'recall@10:', last.recall_at_10)
"
```

A regression of more than 0.05 in recall@5 means the new content is hurting retrieval — usually because the chunks are too short, too long, or duplicate existing high-ranked content. Roll back with:

```bash
git checkout -- backend/Medura_Train/textbooks/<file>
python manage.py ingest_source internal-notes --prune-missing
```

---

## 8. Phase 6 — Sample queries

Hit `/api/kb/ask/` with five real user-style questions covering the new topic:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"…"}' | jq -r .access)

for q in "DKA initial management" "DKA diagnostic criteria" "DKA potassium replacement threshold" "DKA pediatric vs adult" "DKA cerebral edema risk"; do
  curl -s -X POST http://localhost:8000/api/kb/ask/ \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"$q\",\"subject\":\"Medicine\"}" \
    | jq '.answer, .citations[].source'
done
```

Every answer should cite the new source. If 0/5 cite the new content, the chunking is wrong — increase `chunk_size` or break the file into smaller pieces.

---

## 9. Phase 7 — Commit

Conventional commit format:

```text
feat(kb): add DKA management notes (Medura_Train/textbooks/dka_management.md)

- ingest_source internal-notes: +1 doc, 12 chunks
- EmbeddingIndexer: +12 chunks
- evaluate_kb: recall@5 0.81 -> 0.83
```

Push branch and open PR; deploy via the standard Render pipeline (`backend/build.sh` runs `ingest_source internal-notes` automatically).

---

## 10. Adding a new whitelisted source

If the source is brand-new (e.g. a new CDC dataset), three steps:

1. Add the connector in `backend/knowledge_base/connectors/<name>.py` extending `connectors/base.py`.
2. Export it in `connectors/__init__.py`.
3. Register the source name in `management/commands/ingest_source.py` choices.

Then test locally:

```bash
python manage.py ingest_source <name> --max 10 --dry-run
python manage.py ingest_source <name> --max 50
python manage.py evaluate_kb
```

For network sources, throttle carefully — NCBI is 3 req/sec without an API key (10/sec with). Render free tier cold-starts punish burst requests; set `KB_INGEST_NETWORK=1` on a one-off deploy rather than enabling it on every build.

---

## 11. Extending the ontology

To add new entity types or relations:

1. Edit `backend/knowledge_base/ontology/data.py` — add the entity label and any relations under a section comment.
2. Run `python manage.py load_ontology --reset` to replace the ontology (only do this if you intend to fully overwrite).
3. For additive-only changes, run without `--reset` — `update_or_create` will refresh existing rows.
4. Re-run `python manage.py extract_kg` (or call `/api/kb/extract-kg/`) to populate new entity mentions from existing chunks.

---

## 12. Anti-patterns

- **Don't** ingest copyrighted textbook excerpts. Refuse and tell the user.
- **Don't** ingest ChatGPT raw output without fact-checking. Verify against at least one whitelisted source.
- **Don't** run `load_ontology --reset` after content has been ingested — it does not delete chunks but it will leave dangling relations.
- **Don't** enable `KB_INGEST_NETWORK=1` permanently on the Render service — it burns rate-limit budget on every deploy.
- **Don't** add a chunk file larger than 50 MB; the PDF splitter will skip it.
- **Don't** commit `chroma_db/rag_store.sqlite3` changes from a local branch without verifying the embeddings row count in production matches.

---

## 13. Verification checklist (run before saying "done")

```bash
# All must succeed
python manage.py check
python manage.py migrate --check
python manage.py test knowledge_base
curl -fsS http://localhost:8000/api/kb/health/ | jq .status
curl -fsS http://localhost:8000/api/kb/stats/ | jq '.chunks > 0'
```

---

## 14. See also

- `docs/knowledge-base/SETUP.md` — operator setup
- `docs/mcp/README.md` — knowledge_base MCP server card
- `llms-full.txt` §5 — full KB reference
- `.github/skills/acquire-codebase-knowledge/` — codebase onboarding