# Knowledge Base MCP Server Card — Monica AI

> Model Context Protocol server descriptor for the CrackCMS `knowledge_base` app. Use this card to register Monica AI as a tool provider for LLM clients (Claude Desktop, MCP-aware agents, custom clients).

- Module: `backend/knowledge_base/`
- Protocol: MCP (Model Context Protocol) v1 — JSON-RPC over HTTP
- Transport: HTTP (default) or stdio (when launched as a subprocess)
- Auth: Bearer JWT (user) or service token (admin/ingest)
- Rate limit: 60 req/min/user, 600 req/min/service token
- Spec version: 2025-06-18

---

## 1. Server identity

```json
{
  "name": "crackcms-knowledge-base",
  "version": "1.0.0",
  "vendor": "CrackLabs",
  "description": "Monica AI — hybrid BM25 + dense vector + knowledge-graph retrieval over whitelisted medical sources (UPSC, MoHFW, NHM, NMC, ICMR, NCBI, WHO, NHS, CDC, NICE, OpenMD, KEGG, DrugBank). All answers carry [Source — Page] citations. Refuses copyrighted ingestion (Harrison, Bailey & Love, Marrow, PrepLadder).",
  "homepage": "https://cracklabs.app",
  "repository": "https://github.com/Divyanshu-Dubey/crack_cms",
  "license": "see LICENSE in repo",
  "capabilities": {
    "tools": true,
    "resources": true,
    "prompts": false,
    "sampling": false,
    "logging": true
  }
}
```

---

## 2. Tools exposed

Each tool maps to a DRF endpoint under `/api/kb/`. All tools accept `bearer_token` (Supabase access token or Django JWT) in their `meta.auth` envelope; service tokens bypass per-user rate limits.

| Tool | Method/Path | Description |
|---|---|---|
| `kb_ask` | POST /api/kb/ask/ | Ask Monica a medical question; returns grounded answer + citations |
| `kb_search` | POST /api/kb/search/ | Hybrid retrieval over chunks (BM25 + dense + KG + RRF) |
| `kb_stats` | GET /api/kb/stats/ | Counts of sources, documents, chunks, entities, relations |
| `kb_sources` | GET /api/kb/sources/ | Whitelisted source catalog with permission flags |
| `kb_upload` | POST /api/kb/upload/ | Upload a user document (PDF/MD/TXT) — attested non-copyrighted |
| `kb_ingest` | POST /api/kb/ingest/ | Trigger ingestion for a named source (admin/service only) |
| `kb_index` | POST /api/kb/index/ | Rebuild embeddings for chunks missing them |
| `kb_extract_kg` | POST /api/kb/extract-kg/ | Extract entities + relations from chunks (service only) |
| `kb_eval` | POST /api/kb/eval/ | Run retrieval evaluation harness (service only) |
| `kb_health` | GET /api/kb/health/ | Liveness + last-ingest timestamp |

### 2.1 `kb_ask` — input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["query"],
  "properties": {
    "query":       { "type": "string", "minLength": 3, "maxLength": 2000 },
    "subject":     { "type": "string", "description": "Optional exam-track subject (Medicine, Surgery, …)" },
    "topic":       { "type": "string", "description": "Optional topic slug" },
    "max_chunks":  { "type": "integer", "minimum": 1, "maximum": 20, "default": 8 },
    "temperature": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.2 },
    "provider":    { "type": "string", "enum": ["auto","groq","cerebras","gemini","cohere","openrouter","github","huggingface","mistral","nvidia","deepseek","ollama"], "default": "auto" }
  }
}
```

### 2.2 `kb_ask` — output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["answer", "citations"],
  "properties": {
    "answer":      { "type": "string" },
    "citations":   { "type": "array", "items": { "$ref": "#/definitions/citation" } },
    "entities":    { "type": "array", "items": { "type": "string" } },
    "provider":    { "type": "string" },
    "tokens_used": { "type": "integer" },
    "cached":      { "type": "boolean" }
  },
  "definitions": {
    "citation": {
      "type": "object",
      "required": ["source", "page"],
      "properties": {
        "source": { "type": "string" },
        "title":  { "type": "string" },
        "page":   { "type": "string" },
        "url":    { "type": "string", "format": "uri" }
      }
    }
  }
}
```

### 2.3 `kb_search` — input schema

```json
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query":      { "type": "string", "minLength": 3 },
    "top_k":      { "type": "integer", "minimum": 1, "maximum": 50, "default": 8 },
    "retrievers": { "type": "array", "items": { "type": "string", "enum": ["bm25","dense","kg"] }, "default": ["bm25","dense","kg"] },
    "min_score":  { "type": "number", "minimum": 0, "maximum": 1, "default": 0.0 }
  }
}
```

### 2.4 `kb_search` — output schema

```json
{
  "type": "object",
  "properties": {
    "chunks": { "type": "array", "items": { "$ref": "#/definitions/chunk" } }
  },
  "definitions": {
    "chunk": {
      "type": "object",
      "properties": {
        "id":        { "type": "integer" },
        "source":    { "type": "string" },
        "title":     { "type": "string" },
        "page":      { "type": "string" },
        "text":      { "type": "string" },
        "score":     { "type": "number" },
        "retriever": { "type": "string" }
      }
    }
  }
}
```

---

## 3. Resources exposed

Resources are read-only views into the KB.

| URI | Description |
|---|---|
| `kb://sources` | Whitelisted source catalog |
| `kb://stats` | Live counts |
| `kb://ontology/entities` | Entity catalog (paginated) |
| `kb://ontology/relations` | Relation catalog (paginated) |
| `kb://chunks/{id}` | Single chunk with text + citations |

---

## 4. Prompts

None. Monica AI is a single-shot answering surface; prompts are managed internally by `services/monica.py`.

---

## 5. Error model

| HTTP | Code | When |
|---|---|---|
| 400 | invalid_input | Schema violation |
| 401 | unauthorized | Missing / expired bearer token |
| 402 | payment_required | Token balance exhausted |
| 403 | forbidden | Provider not allowlisted for plan |
| 404 | not_found | Source or chunk missing |
| 409 | ingestion_conflict | Same text_hash already present |
| 422 | refusal | Source not whitelisted (copyright) |
| 429 | rate_limited | Per-user / per-IP quota exceeded |
| 500 | provider_error | All AI providers failed; check Sentry |
| 503 | index_unavailable | Embeddings index not built yet |

---

## 6. Configuration (.mcp.json)

A working client configuration is committed at the repo root as `.mcp.json`. See that file for the exact transport/auth settings.

```json
{
  "mcpServers": {
    "crackcms-kb": {
      "command": "python",
      "args": ["-m", "knowledge_base.mcp_server"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "crack_cms.settings",
        "KB_MCP_TRANSPORT": "stdio",
        "KB_MCP_AUTH": "django"
      }
    }
  }
}
```

For HTTP transport, set `KB_MCP_TRANSPORT=http` and `KB_MCP_HTTP_PORT=8765`.

---

## 7. Usage from an LLM client

```text
Tool: kb_ask
Input: { "query": "First-line treatment for acute migraine in adults?", "subject": "Medicine" }
```

Monica will retrieve top-K chunks from whitelisted sources, prompt the AI provider pool with the chunk context, and return a grounded answer plus inline citations. If the question references copyrighted material that is not in the KB, Monica returns `422 refusal` with a helpful suggestion.

---

## 8. Self-test

```bash
# Backend must be running locally
curl -s http://localhost:8000/api/kb/health/ | jq .

# Ask a question
curl -s -X POST http://localhost:8000/api/kb/ask/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "treatment of DKA", "subject": "Medicine"}' | jq .
```

---

## 9. Whitelist enforcement

Connector layer rejects ingestion of any source not in the allowlist. Currently allowed:

| Region | Sources |
|---|---|
| Indian | UPSC, MoHFW India, NHM India, NMC India, ICMR |
| International | NCBI, WHO, NHS, CDC, NICE, OpenMD, KEGG, DrugBank |

Refused: Harrison's Principles of Internal Medicine, Bailey & Love, Marrow, PrepLadder, and any other copyrighted textbook.

---

## 10. See also

- `docs/knowledge-base/SETUP.md` — operator setup guide
- `docs/PROJECT_OVERVIEW.md` — product context
- `docs/ARCHITECTURE.md` — system architecture
- `llms-full.txt` — full platform reference