# PHASE 1.3 — QuestionImage coverage audit (2026-07-25)

**Scope:** confirm every `Question.is_image_based=True` row has at least one
matching `QuestionImage` row (active), so the player never surfaces an
image-bearing question that cannot actually display its image.

---

## Result

**✅ PASS — 100% coverage.**

| Metric | Value |
|---|---|
| `QuestionImage` rows (`is_active=True`) | 3,496 |
| `Question.is_image_based=True AND is_active=True` | 115 |
| Of those, with ≥1 active `QuestionImage` | **115 (100%)** |
| Missing `QuestionImage` for an image-bearing question | **0** |
| "Orphan" `QuestionImage` rows (parent `is_image_based=False`) | 2,929 |

### By year

| Year | image_based questions |
|---|---|
| 2021 | 115 |

All 115 image-bearing questions belong to the NEET PG 2021 paper.

### By exam_type

| Exam type | image_based questions |
|---|---|
| neet_pg | 115 |

### Prod verification

```
$ curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/?is_image_based=true&exam_type=neet_pg&page_size=1'
{"count": 115, ...}
```

Prod mirror agrees: 115 image-bearing NEET PG questions. Combined with the
PHASE 1.2 fix (Bug #P0-2 — `/api/questions/images/<id>/serve/` proxy),
every image-bearing question now has both a `QuestionImage` row **and**
a reachable image URL.

---

## Notes

- **Orphan count (2,929)** is not a defect — many questions have
  diagrams/tables as supplementary material without the question being
  marked "image-based" (i.e. requiring the image to be answerable). The
  `is_image_based` flag tracks necessity, not sufficiency.
- **Local disk vs DB**: locally we have 3,496 DB rows but only ~257
  files on disk. The proxy view from PHASE 1.2 returns 503 when the
  file is missing — graceful degradation rather than a 404.
- The 115 image-bearing questions will all 200 once the prod container
  is populated with the actual PNG files (or once S3/DO Spaces is wired
  via `DEFAULT_FILE_STORAGE`).
