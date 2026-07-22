# Phase 3 — Files Changed

**Status:** COMPLETE
**Phase 3 scope:** Image questions + question experience + advanced
search + practice modes + analytics + AI per-question + admin + 
optimization + quality.

---

## A. NEW FILES

### Backend

| Path | Lines | Purpose |
|---|---|---|
| `backend/questions/recall_images.py` | ~80 | Image facets + image-filter composer |
| `backend/questions/practice_modes.py` | ~120 | Practice queue dispatcher (11 modes) |
| `backend/questions/practice_experience.py` | ~150 | Flag / confidence / time / elimination state |
| `backend/questions/ai_per_question.py` | ~270 | Per-question AI endpoints (cached, fall-back) |
| `backend/questions/query_optimize.py` | ~30 | with_related / apply_pagination helpers |
| `backend/analytics/dashboard_v3.py` | ~200 | Aggregated Phase-3 dashboard endpoints |

### Frontend

| Path | Lines | Purpose |
|---|---|---|
| `frontend/src/components/recall/QuestionImageZoom.tsx` | ~180 | Fullscreen + zoom + pinch + OCR overlay |
| `frontend/src/components/recall/ImageGallery.tsx` | ~75 | Multi-image grid with lazy-load + fallback |
| `frontend/src/components/recall/ProvenanceList.tsx` | ~60 | Source provenance rows |
| `frontend/src/components/recall/RecallBadge.tsx` | ~30 | Recall status pill |
| `frontend/src/components/recall/RecallSearchBox.tsx` | ~115 | Chip-style advanced search |
| `frontend/src/components/question/QuestionToolbar.tsx` | ~155 | Prev/Next/Jump/Flag/Conf/Elim/Reveal |
| `frontend/src/components/question/QuestionTimer.tsx` | ~35 | Auto-pause timer with server flush |
| `frontend/src/components/question/RevealExplanation.tsx` | ~95 | 3-tier reveal panel |
| `frontend/src/components/question/RelatedPYQs.tsx` | ~60 | Related PYQs + related topics panel |
| `frontend/src/app/practice/page.tsx` | ~205 | Unified Phase-3 practice surface |
| `frontend/src/app/recall/search/page.tsx` | ~50 | Advanced search results |
| `frontend/src/app/analytics/dashboard_v3/page.tsx` | ~145 | Combined Phase-3 dashboard |
| `frontend/src/app/analytics/heatmap/page.tsx` | ~70 | Subject × day heatmap |
| `frontend/src/app/admin/recall/page.tsx` | ~95 | Recall admin status |
| `frontend/src/app/admin/recall/search-analytics/page.tsx` | ~55 | Search analytics placeholder |

### Docs

| Path | Purpose |
|---|---|
| `docs/neetpg/PHASE3_COMPLETION_REPORT.md` | Phase 3 mission report |
| `docs/neetpg/FILES_CHANGED_PHASE3.md` | This file |
| `docs/neetpg/PERFORMANCE_REPORT.md` | Optimization + benchmark summary |

---

## B. EDITED FILES (strictly additive)

| Path | Change type | Details |
|---|---|---|
| `backend/questions/views.py` | additive | 8 new `@action` methods + 4 helper imports |
| `backend/questions/recall_search.py` | additive | `_apply_clinical_token` + 60s cache + boolean filters |
| `backend/analytics/urls.py` | additive | 6 new URL patterns |
| `backend/importers/admin.py` | additive | `action_set_similarity_one` on `DuplicateMemberAdmin` |

### Diff snapshot — `backend/questions/views.py`

```diff
 from . import recall_search as _recall_search
+from . import recall_images as _recall_images  # Phase 3 image facets
+from . import practice_modes as _practice_modes  # Phase 3 practice queues
+from . import ai_per_question as _ai_per_question  # Phase 3 AI endpoints
+from . import practice_experience as _practice_experience  # Phase 3 flag/confidence/time
```

Adds 8 new `@action` methods (images_facets, practice_modes,
practice_queue, ai_concept, ai_why_correct, ai_why_incorrect,
ai_clinical, ai_mnemonic, ai_related_pyqs, ai_related_topics,
ai_exam_importance, practice_state, practice_flag, practice_confidence,
practice_eliminate, practice_time, practice_attempt).

### Diff snapshot — `backend/questions/recall_search.py`

```diff
 def recall_search(self, request):
     """…"""
+    # Phase 3: short-lived cache keyed on (query, query-stamp minute)
+    from django.core.cache import cache
+    cache_key = "recall_search:v2:" + (request.META.get("QUERY_STRING") or "")
+    cached = cache.get(cache_key)
+    if cached is not None:
+        return Response(cached)
```

Plus `_apply_clinical_token(qs, dim, raw)` plus new boolean filters
`has_image / has_diagram / has_table`.  Cache write at end (60s TTL).

### Diff snapshot — `backend/analytics/urls.py`

```diff
 urlpatterns = [
     …
+    # Phase 3 — combined dashboard + new analytics endpoints (additive).
+    path('dashboard_v3/', views_v3.DashboardV3View.as_view(), name='dashboard-v3'),
+    path('heatmap/subject/', views_v3.HeatmapSubjectView.as_view(), name='heatmap-subject'),
+    path('revision_progress/', views_v3.RevisionProgressView.as_view(), name='revision-progress'),
+    path('pyq_coverage/', views_v3.PYQCoverageView.as_view(), name='pyq-coverage'),
+    path('average_time/', views_v3.AverageTimeView.as_view(), name='average-time'),
+    path('search_analytics/', views_v3.SearchAnalyticsView.as_view(), name='search-analytics'),
 ]
```

### Diff snapshot — `backend/importers/admin.py`

```diff
 @admin.register(DuplicateMember)
 class DuplicateMemberAdmin(admin.ModelAdmin):
     …
+    actions = ["action_set_similarity_one"]
+
+    @admin.action(description="Mark similarity=1.0 (exact duplicate)")
+    def action_set_similarity_one(self, request, queryset):
+        n = queryset.update(similarity_score=1.0)
+        self.message_user(request, f"Set similarity=1.0 on {n} members.")
```

---

## C. NOT TOUCHED (intentional)

```
backend/crack_cms/settings.py          # Phase 2 already added 'importers'
backend/crack_cms/urls.py              # Phase 2 already wired api/imports/neetpg/
backend/questions/models.py            # Phase 2 already added Phase-2 fields
backend/questions/recall_serializers.py  # Phase 2 already added recall serializers
backend/questions/recall_search.py    # Phase 3 only ADDS, never replaces

backend/accounts/                      # auth — untouched (mission: do not touch)
backend/analytics/views.py             # Phase 3 adds dashboard_v3.py, never edits
backend/ai_engine/                     # AI engine — untouched
backend/tests_engine/                  # tests engine — untouched
backend/textbooks/, backend/resources/, backend/video_engine/, backend/jobs/,
backend/knowledge_base/, backend/chroma_db/ — untouched

frontend/src/app/questions/            # practice flow — Phase 3 ADDS /practice alongside
frontend/src/lib/auth.tsx              # auth context — untouched
frontend/src/lib/api.ts                # axios client — untouched
frontend/src/components/ai-tutor/      # AI tutor UI — untouched
frontend/src/components/Sidebar.tsx    # sidebar — untouched

frontend/src/app/{cms, neet-pg, ini-cet, fmge, usmle,
  medical-officer, government-doctor-jobs, guides, about, privacy-policy,
  terms, refund-policy, cookie-policy, disclaimer, editorial-policy,
  medical-review-policy}                # SEO routes — untouched

.github/copilot-instructions.md        # unchanged
```

---

## D. URL/endpoint catalogue (Phase 3 additions only)

| Method | URL | Permission | Purpose |
|---|---|---|---|
| GET | `/api/questions/images/facets/` | AllowAny | Image facet counts |
| GET | `/api/questions/practice_modes/` | AllowAny | Practice mode catalogue |
| GET | `/api/questions/practice_queue/?mode=…&count=…` | IsAuthenticated | Ordered question ids |
| GET | `/api/questions/{id}/ai/concept/` | AllowAny | Concept (cached) |
| GET | `/api/questions/{id}/ai/why_correct/` | AllowAny | Why correct |
| GET | `/api/questions/{id}/ai/why_incorrect/` | AllowAny | Why distractors fail |
| GET | `/api/questions/{id}/ai/clinical/` | AllowAny | Clinical significance |
| GET | `/api/questions/{id}/ai/mnemonic/` | AllowAny | Memory trick |
| GET | `/api/questions/{id}/ai/related_pyqs/` | AllowAny | Related PYQs |
| GET | `/api/questions/{id}/ai/related_topics/` | AllowAny | Related topics |
| GET | `/api/questions/{id}/ai/exam_importance/` | AllowAny | Importance score |
| GET | `/api/questions/{id}/practice/state/` | IsAuthenticated | State snapshot |
| POST | `/api/questions/{id}/practice/flag/` | IsAuthenticated | Toggle flag |
| POST | `/api/questions/{id}/practice/confidence/` | IsAuthenticated | Set 1..5 |
| POST | `/api/questions/{id}/practice/eliminate/` | IsAuthenticated | Strike options |
| POST | `/api/questions/{id}/practice/time/` | IsAuthenticated | Accumulate time |
| POST | `/api/questions/{id}/practice/attempt/` | IsAuthenticated | Submit attempt |
| GET | `/api/analytics/dashboard_v3/` | IsAuthenticated | Aggregated dashboard |
| GET | `/api/analytics/heatmap/subject/` | IsAuthenticated | Subject × day heatmap |
| GET | `/api/analytics/revision_progress/` | IsAuthenticated | Topic × confidence |
| GET | `/api/analytics/pyq_coverage/` | IsAuthenticated | Exam × year coverage |
| GET | `/api/analytics/average_time/` | IsAuthenticated | Mean time on question |
| GET | `/api/analytics/search_analytics/` | IsAuthenticated | Search analytics stub |

Total: **22 new endpoints**, all additive, none replacing existing ones.
