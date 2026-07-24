# IMPORT_DASHBOARD.md — Phase 3 design stub

**Status**: DESIGN ONLY. No code yet. Phase 1 ships the data; Phase 3 builds the dashboard.
**Last updated**: 2026-07-24

---

## Why Phase 3 exists

Phase 1's `ImportJob`, `ImportJobStage`, and `ImportCheckpoint` rows are the canonical source of truth for every import attempt. The dashboard reads them directly — no new tables, no new aggregation job. The data is there from day one; the dashboard is a focused presentation layer.

---

## Dashboard surface (`/admin/ingestion/dashboard/`)

```
/admin/ingestion/dashboard/
├── layout.tsx                       # server-side admin role gate (Phase 1 provides)
├── page.tsx                         # tiles row + charts grid
├── throughput/page.tsx              # daily throughput over 30 days
└── pipeline-funnel/page.tsx         # drop-off across PIPELINE_ORDER stages
```

### Tile row (top of dashboard)

| Tile | Source | Refresh |
|---|---|---|
| Queue depth | `ImportJob.objects.filter(status='queued').count()` | 5 s |
| Running jobs | `ImportJob.objects.filter(status='processing').count()` | 5 s |
| Completed today | `ImportJob.objects.filter(status='completed', completed_at__date=today).count()` | 30 s |
| Failed today | `ImportJob.objects.filter(status__in=['failed','crashed'], completed_at__date=today).count()` | 30 s |
| Questions auto-imported today | `ImportJob.objects.filter(...).aggregate(Sum('questions_imported'))` | 30 s |
| Pending review count | `StagedQuestion.objects.filter(review_status='pending').count()` | 30 s |
| Extraction failures | `StagedQuestion.objects.filter(qa_status='Extraction Failure', review_status='blocked').count()` | 30 s |
| Avg PR % (last 7 days) | `ImportJob.objects.filter(completed_at__gte=...).aggregate(Avg('qa_v2_production_ready_pct'))` | 60 s |

### Charts grid (recharts)

1. **Stage pipeline funnel** — bar chart; one bar per stage in `PIPELINE_ORDER`; bar height = total `pages_processed` across all jobs in last 7 days. Drop-off points (e.g. Stage 5 → Stage 6) immediately visible.
2. **PR/NR/EF distribution** — stacked area chart; one stack per verdict; X = day, Y = question count. Shows convergence on the 2021 baseline (65.5/29.1/5.3).
3. **Daily throughput** — line chart; dual-axis (PR count + total elapsed time). Surfaces ingest speed regressions.
4. **Per-job speed** — gantt-like chart; horizontal bars = each job's wall-clock span; colour by status. Hover = full stage timeline.
5. **PR % heatmap** — grid of (PDF sha16) × (day); used to spot content-dependent regressions.

All charts read from the same Phase 1 tables; refresh is done via SWR (stale-while-revalidate) on the client side, no background polling worker.

---

## Reader API surface (Phase 3 backend additions)

| Verb | Path | Purpose |
|---|---|---|
| GET | `/dashboard/tiles/` | The 8 tiles above as a single JSON |
| GET | `/dashboard/funnel/?days=7` | Stage pipeline funnel rows |
| GET | `/dashboard/distribution/?days=30` | PR/NR/EF time series |
| GET | `/dashboard/throughput/?days=30` | Daily throughput |
| GET | `/dashboard/jobs/?days=7` | Per-job wall-clock sums for the gantt |
| GET | `/dashboard/pr-heatmap/?days=30` | sha16 × day PR% |

Endpoints are auth-gated by `IsIngestionAdmin`, return aggregates only (no PII), and cache via Django's per-view cache for 30 s.

---

## Refresh cadence

| Surface | Cadence | Why |
|---|---|---|
| Tiles | 5 s+30 s | Operations tiles need real-time; counts can lag |
| Funnel/distribution | 60 s | Charts are trend-only; overpolling wastes DB |
| Heatmap | 5 min | Once per shift is enough |

Phase 3 writes nothing back to the DB. The dashboard is read-only.

---

## Cross-bucket tool (the "bulk approve" affordance)

A single tile on the dashboard ("Bulk action: 60 NR pending") opens a sub-panel listing rows filtered by `failing_axis` + `subject`. Selecting N rows and clicking "Approve all" is a thin facade over `POST /api/ingestion/review/<staged_id>/approve/` issued N times in parallel via axios.all. The Phase 2 reader/writer pair handles the audit per row.

---

## Out of scope

- Real-time WebSocket push (SSE fallback acceptable if dashboard feels slow during peak).
- Cross-exam analytics (NEET PG vs INI-CET side-by-side). Phase 3 only surveys within one parent_exam; the cross-exam view is deferred to Phase 7.
- Forecasting / anomaly detection. Phase 4 trends are read-only.
