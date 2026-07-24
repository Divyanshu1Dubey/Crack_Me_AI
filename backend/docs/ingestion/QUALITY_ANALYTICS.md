# QUALITY_ANALYTICS.md — Phase 4 design stub

**Status**: DESIGN ONLY. No code yet. Phase 1 emits the underlying artefacts; Phase 4 reads them.
**Last updated**: 2026-07-24

---

## Why Phase 4 exists

MCE Stage 8 writes two JSON artefacts per job:

- `<artefact_root>/<sha16>/08_qa/summary.json` — aggregate stats (PR/NR/EF counts, mean axis scores, ocr confidence distribution).
- `<artefact_root>/<sha16>/08_qa/per_question_qa.json` — per-question `{status, axes, failing_axes, ocr_confidence, ...}`.

Phase 1 surfaces them through `ImportArtifact` (pointer rows) and `StagedQuestion` (the NR + EF subsets). Phase 4 builds analytics over both — top failure reasons, OCR confidence regression, answer-accuracy delta vs the benchmark, explanation-length distribution, per-PDF PR%.

---

## Analytics surface (`/admin/ingestion/analytics/`)

```
/admin/ingestion/analytics/
├── layout.tsx                       # server-side admin role gate (Phase 1 provides)
├── page.tsx                         # failure-reason leaderboard + axis score trend
├── ocr/page.tsx                     # low-confidence OCR samples (sortable)
├── answers/page.tsx                 # answer-correct vs benchmark delta
└── trends/page.tsx                  # 30-day per-axis trend lines
```

### Failure-reason leaderboard

The single highest-value screen. Reads `StagedQuestion.failing_axes` (Phase 1 JSON) and counts distinct axes:

```
Axis 4 — answer_consistent       ██████████████████ 412 questions  (24% of NR)
Axis 6 — image_mapping             ████████████████   328            (19%)
Axis 7 — explanation_quality       ██████████         201            (12%)
Axis 1 — layout_geometry           ████                87            (5%)
…
```

Clicking a row drills into a paginated list of `StagedQuestion` rows filtered by that axis, sorted by descending axis score (lowest first). Each row links to the Phase 2 review page.

### OCR confidence distribution

Reads `per_question_qa.json` ocr_confidence field. Histogram (recharts BarChart) bucketed by 0.05 intervals. Surfaces the long tail below 0.7 (which the MCE `axis 2 ocr_pass` flags as failing).

Hover = the actual OCR snippet. Click = Phase 2 review page.

### Answer-correct delta vs benchmark

Each NEET PG PDF has a known answer key embedded in the solutions PDF. For every QA V2 PR question we assert that the extracted `correct_option` matches the key. The per-PDF delta (`actual_correct − benchmark_correct`) is rendered as a bar chart per batch. Negative deltas trigger a review-task; positive deltas confirm MCE is healthy.

### Explanation-length distribution

`per_question_qa.json` carries explanation word-count. Histogram; outliers (very short = truncated, very long = extracted footer) are listed below.

### Per-PDF PR%

Stacked bar of `{PR, NR, EF} %` per PDF. Side-by-side comparison to the 2021 benchmark (65.5/29.1/5.3) makes a regression immediately obvious.

### 30-day trend

`line chart x = day, y = mean axis score, one line per axis`. The Phase 1 `ImportJob.completed_at` index makes the query cheap.

---

## Reader API surface (Phase 4 backend additions)

| Verb | Path | Purpose |
|---|---|---|
| GET | `/analytics/failure-reasons/?days=30` | Top failing axes + counts |
| GET | `/analytics/ocr/?threshold=0.7` | Below-threshold OCR samples |
| GET | `/analytics/answer-delta/?batch_id=` | Answer-correct delta per PDF |
| GET | `/analytics/explanation-length/?days=30` | Distribution + outliers |
| GET | `/analytics/pr-distribution/?days=30` | Per-PDF PR/NR/EF % |
| GET | `/analytics/trend/?axis=&days=30` | Per-axis time series |

All endpoints cached at 60 s per request. No new tables — every endpoint reads existing Phase 1 tables + the on-disk JSON.

---

## Alerting (built but never auto-paged)

Phase 4 emits synthetic alerts (the dashboard highlights a red tile) when:

- Per-PDF PR% drops more than 15 pp below the 2021 baseline.
- Mean `answer_consistent` axis score drops more than 0.1 below the trailing 7-day average.
- An OCR bucket (e.g. page 30-40) shows >40% confidence < 0.6 — likely a font/encoding regression in the source PDF.

Alerts are visual only in Phase 4; an email/Slack integration is Phase 7 scope.

---

## Out of scope

- Threshold tuning UI. The QA V2 thresholds are frozen; Phase 4 reports the existing behaviour, doesn't tune it.
- Custom failure taxonomies. We use MCE's axis taxonomy as-is.
- A/B testing of differing QA V2 thresholds. The dashboard can compare two batches side-by-side; that's enough.
