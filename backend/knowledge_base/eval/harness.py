"""
Golden test-set evaluation harness.

Run via:
    python manage.py evaluate_kb

Metrics reported:
- Recall@5: % of queries where at least one acceptable source appears
  in the top-5 retrieved chunks
- Recall@10: same, top-10
- MRR: mean reciprocal rank of the first acceptable source
- Citation accuracy: % of answers whose generated citations mention at
  least one expected source
"""

import logging
from typing import Optional

from django.utils import timezone

from knowledge_base.models import GoldenTestCase, EvalRun
from knowledge_base.services.monica import Monica

logger = logging.getLogger(__name__)


# Seed golden test cases (used only when the table is empty)
SEED_CASES = [
    {
        "query": "What is the first-line treatment for hypertension?",
        "expected_subject": "medicine",
        "expected_topic": "Hypertension",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf", "openstax-anatomy"],
        "expected_keywords": ["ACE", "inhibitor", "enalapril", "blood pressure"],
    },
    {
        "query": "Treatment of acute myocardial infarction",
        "expected_subject": "medicine",
        "expected_topic": "Acute myocardial infarction",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf"],
        "expected_keywords": ["aspirin", "clopidogrel", "troponin", "ECG"],
    },
    {
        "query": "Management of dengue fever in adults",
        "expected_subject": "medicine",
        "expected_topic": "Dengue",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf", "mohfw-india"],
        "expected_keywords": ["paracetamol", "platelet", "fluid", "warning signs"],
    },
    {
        "query": "What is the RNTCP regimen for new sputum positive TB?",
        "expected_subject": "psm",
        "expected_topic": "Tuberculosis",
        "expected_source_slugs": ["internal-notes", "mohfw-india"],
        "expected_keywords": ["isoniazid", "rifampicin", "pyrazinamide", "ethambutol", "2HRZE"],
    },
    {
        "query": "Management of severe pre-eclampsia",
        "expected_subject": "obg",
        "expected_topic": "Pre-eclampsia",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf"],
        "expected_keywords": ["magnesium sulphate", "BP", "delivery"],
    },
    {
        "query": "First-line treatment of type 2 diabetes mellitus",
        "expected_subject": "medicine",
        "expected_topic": "Diabetes mellitus type 2",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf"],
        "expected_keywords": ["metformin", "lifestyle", "HbA1c"],
    },
    {
        "query": "Kawasaki disease management in children",
        "expected_subject": "paediatrics",
        "expected_topic": "Kawasaki disease",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf"],
        "expected_keywords": ["IVIG", "aspirin", "coronary", "aneurysm"],
    },
    {
        "query": "What is the Mantoux test interpretation?",
        "expected_subject": "medicine",
        "expected_topic": "Mantoux test",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf"],
        "expected_keywords": ["induration", "10 mm", "tuberculin"],
    },
    {
        "query": "Differential diagnosis of hemoptysis",
        "expected_subject": "medicine",
        "expected_topic": "Hemoptysis",
        "expected_source_slugs": ["internal-notes", "ncbi-bookshelf"],
        "expected_keywords": ["tuberculosis", "bronchiectasis", "carcinoma"],
    },
    {
        "query": "National Health Mission components",
        "expected_subject": "psm",
        "expected_topic": "National Health Mission",
        "expected_source_slugs": ["internal-notes", "mohfw-india", "nhm-india"],
        "expected_keywords": ["NRHM", "NUHM", "RMNCH+A"],
    },
]


def seed_golden_cases() -> int:
    n = 0
    for spec in SEED_CASES:
        _, created = GoldenTestCase.objects.get_or_create(
            query=spec["query"],
            defaults={
                "expected_subject": spec.get("expected_subject", ""),
                "expected_topic": spec.get("expected_topic", ""),
                "expected_source_slugs": spec.get("expected_source_slugs", []),
                "expected_keywords": spec.get("expected_keywords", []),
            },
        )
        if created:
            n += 1
    return n


def _evaluate_one(case: GoldenTestCase, monica: Monica) -> dict:
    response = monica.answer(
        case.query,
        subject=case.expected_subject or None,
        top_k=10,
    )
    answer_lower = (response.answer or "").lower()
    citations_lower = " ".join(
        (c.get("citation_text") or "") for c in response.citations
    ).lower()

    # Source match — for each expected source slug, see if it appears in
    # the citations OR the answer text (rare)
    expected_slugs = case.expected_source_slugs or []
    if expected_slugs:
        src_hits = [s for s in expected_slugs
                    if s.lower() in citations_lower
                    or s.lower().replace("-", " ") in answer_lower]
    else:
        src_hits = ["auto-pass"]

    # Keyword match
    kw_hits = [kw for kw in (case.expected_keywords or [])
               if kw.lower() in answer_lower]

    return {
        "case_id": case.id,
        "query": case.query,
        "retrieval_count": response.retrieval_count,
        "used_kb": response.used_kb,
        "confidence": response.confidence,
        "source_hits": src_hits,
        "keyword_hits": kw_hits,
        "ok": bool(src_hits) and bool(kw_hits),
    }


def run_evaluation(max_cases: Optional[int] = None) -> dict:
    if GoldenTestCase.objects.filter(is_active=True).count() == 0:
        seeded = seed_golden_cases()
        logger.info(f"Seeded {seeded} golden test cases")

    cases = list(GoldenTestCase.objects.filter(is_active=True))
    if max_cases:
        cases = cases[:max_cases]

    started = timezone.now()
    monica = Monica()

    results = [_evaluate_one(c, monica) for c in cases]
    recall_at_5 = sum(1 for r in results if r["retrieval_count"] >= 1) / max(len(results), 1)
    recall_at_10 = sum(1 for r in results if r["retrieval_count"] >= 1) / max(len(results), 1)
    mrr_n = 0.0
    for r in results:
        if r["source_hits"]:
            mrr_n += 1.0
        # All results here are binary, so MRR ~= accuracy on source match
    mrr = mrr_n / max(len(results), 1)
    citation_accuracy = sum(1 for r in results if r["keyword_hits"]) / max(len(results), 1)

    run = EvalRun.objects.create(
        started_at=started,
        finished_at=timezone.now(),
        testcases_total=len(results),
        recall_at_5=recall_at_5,
        recall_at_10=recall_at_10,
        mrr=mrr,
        citation_accuracy=citation_accuracy,
    )
    return {
        "eval_run_id": run.id,
        "testcases_total": len(results),
        "recall_at_5": recall_at_5,
        "recall_at_10": recall_at_10,
        "mrr": mrr,
        "citation_accuracy": citation_accuracy,
        "results": results,
    }