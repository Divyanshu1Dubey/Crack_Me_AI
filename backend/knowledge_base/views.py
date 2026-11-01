"""
Knowledge Base API endpoints.

Public (auth-required) endpoints:
- POST /api/knowledge/ask/        — Monica with citations
- POST /api/knowledge/search/     — retrieval only (returns citations)
- GET  /api/knowledge/stats/      — counts per source
- POST /api/knowledge/upload/     — user upload with rights attestation

Admin endpoints (admin-only):
- POST /api/knowledge/ingest/     — trigger ingestion from a connector
- POST /api/knowledge/index/      — backfill embeddings
- POST /api/knowledge/extract-kg/ — run KG extractor
- GET  /api/knowledge/eval/       — run golden test set
- GET  /api/knowledge/sources/    — list whitelisted sources
"""

import logging
import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission, AllowAny
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework import status
from django.conf import settings as django_settings

from knowledge_base.models import (
    KnowledgeSource, KnowledgeChunk, KnowledgeEntity, KnowledgeRelation,
    IngestionJob, GoldenTestCase, UserUploadAttestation, EvalRun,
)
from knowledge_base.services.monica import Monica

logger = logging.getLogger(__name__)


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and
            (getattr(u, "is_admin", False) or u.is_superuser)
        )


def _public_perm():
    # Never relax auth based on DEBUG: a debug deployment reachable from the
    # internet would otherwise expose ingestion / indexing / LLM endpoints.
    return [IsAuthenticated()]


def _admin_perm():
    return [IsAdminUser()]


def _offline_kb_response(request, question: str, passages: list, *, reason: str,
                         expansion: dict, used_kb: bool):
    """Extractive answer from the retrieved passages (free), or a 503."""
    from ai_engine.offline import REASON_OFFLINE_MODE, compose_offline_answer
    from ai_engine.views import _ai_unavailable_response

    try:
        result = compose_offline_answer(question, passages=passages,
                                        user=getattr(request, "user", None), reason=reason)
    except Exception:
        logger.exception("KB offline composer failed")
        result = None
    if result is None or not result.grounded:
        return _ai_unavailable_response(offline=(reason == REASON_OFFLINE_MODE))
    return Response({
        "answer": result.answer,
        "citations": result.citations,
        "confidence": "offline",
        "used_kb": used_kb,
        "retrieval_count": len(passages),
        "query_expansion": expansion,
        "offline": True,
        "offline_reason": reason,
        "charged": False,
    })


class AskMonicaView(APIView):
    """POST /api/knowledge/ask/ — citation-aware answer.

    This calls the LLM, so it is metered exactly like the AI tutor:
    freemium daily cap, 1 token per call and the `ai_tutor` scoped throttle.
    When no provider answers, the token AND the freemium slot are given back
    and the answer is extracted from the retrieved passages (or a 503
    ``ai_unavailable``). With AI_OFFLINE_MODE on it is free and extractive.
    """
    # The default classes already include ScopedRateThrottle; appending a
    # second one recorded every request twice in the shared bucket.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_tutor"

    def get_permissions(self):
        return _public_perm()

    def post(self, request):
        from ai_engine.offline import REASON_OFFLINE_MODE, REASON_PROVIDERS_DOWN, ai_offline_mode
        from ai_engine.services import AIUnavailable
        from ai_engine.views import _charge_ai_call, _refund_ai_call
        from knowledge_base.ontology.loader import expand_query

        question = str(request.data.get("question", "") or "").strip()
        subject = str(request.data.get("subject") or "").strip()[:100] or None
        if not question:
            return Response({"error": "question is required"}, status=400)
        if len(question) > 4000:
            return Response({"error": "question is too long (max 4000 characters)"}, status=400)

        if ai_offline_mode():
            monica = Monica()
            chunks, legacy = monica.retrieve(question, subject=subject)
            return _offline_kb_response(
                request, question, Monica.offline_passages(chunks, legacy),
                reason=REASON_OFFLINE_MODE, expansion=expand_query(question), used_kb=bool(chunks),
            )

        charge_err = _charge_ai_call(request, amount=1, freemium=True)
        if charge_err is not None:
            return charge_err
        try:
            monica = Monica()
            result = monica.answer(question, subject=subject)
        except AIUnavailable as exc:
            _refund_ai_call(request, amount=1)
            return _offline_kb_response(
                request, question, exc.passages or [],
                reason=REASON_OFFLINE_MODE if exc.offline else REASON_PROVIDERS_DOWN,
                expansion=expand_query(question), used_kb=False,
            )
        except Exception:
            logger.exception("Monica ask failed")
            _refund_ai_call(request, amount=1)
            return Response({"error": "knowledge base temporarily unavailable"}, status=503)
        return Response({
            "answer": result.answer,
            "citations": result.citations,
            "confidence": result.confidence,
            "used_kb": result.used_kb,
            "retrieval_count": result.retrieval_count,
            "query_expansion": result.query_expansion,
        })


class SearchView(APIView):
    """POST /api/knowledge/search/ — retrieval only, no LLM call.

    Retrieval is CPU-heavy (BM25 + optional embedding / cross-encoder), so it
    shares the `ai_tutor` scoped rate limit instead of only the generic
    600/min user throttle.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_tutor"

    def get_permissions(self):
        return _public_perm()

    def post(self, request):
        from ai_engine.offline import public_subject

        query = str(request.data.get("query", "") or "").strip()
        subject = str(request.data.get("subject") or "").strip()[:100] or None
        source_slugs = request.data.get("source_slugs") or None
        if source_slugs is not None:
            if isinstance(source_slugs, str):
                source_slugs = [source_slugs]
            if not isinstance(source_slugs, list):
                return Response({"error": "source_slugs must be a list"}, status=400)
            source_slugs = [str(s)[:120] for s in source_slugs[:20]]
        try:
            default_top_k = int(getattr(django_settings, "KB_DEFAULT_TOP_K", 8))
            top_k = max(1, min(int(request.data.get("top_k", default_top_k)), 25))
        except (TypeError, ValueError):
            return Response({"error": "top_k must be an integer"}, status=400)
        if not query:
            return Response({"error": "query is required"}, status=400)
        if len(query) > 1000:
            return Response({"error": "query is too long (max 1000 characters)"}, status=400)
        try:
            monica = Monica()
            results = monica.retrieval.search(
                query, top_k=top_k, subject=subject, source_slugs=source_slugs,
            )
            return Response({
                "query": query,
                "results": [
                    {
                        "chunk_id": c.chunk_id,
                        "text": c.text[:500],
                        "score": round(c.final_score, 4),
                        "subject": public_subject(c.subject),
                        "topic": c.topic,
                        "citation": c.citation,
                    } for c in results
                ],
            })
        except Exception:
            logger.exception("Search failed")
            return Response({"error": "search failed"}, status=503)


class StatsView(APIView):
    """GET /api/knowledge/stats/ — dashboard counts."""

    def get_permissions(self):
        return _public_perm()

    def get(self, request):
        sources = KnowledgeSource.objects.filter(is_active=True)
        sources_data = []
        for s in sources:
            sources_data.append({
                "slug": s.slug,
                "name": s.name,
                "license": s.license,
                "attribution": s.attribution,
                "chunk_count": s.chunk_count,
                "last_ingested_at": s.last_ingested_at,
                "last_status": s.last_ingestion_status,
            })
        last_jobs = list(IngestionJob.objects.order_by("-created_at")
                         .values("id", "connector", "status",
                                 "chunks_added", "chunks_updated",
                                 "chunks_rejected", "created_at")[:10])
        last_eval = EvalRun.objects.order_by("-started_at").first()
        return Response({
            "sources": sources_data,
            "totals": {
                "sources": sources.count(),
                "chunks": KnowledgeChunk.objects.filter(is_active=True).count(),
                "chunks_approved": KnowledgeChunk.objects.filter(
                    is_active=True,
                    approval_state__in=[
                        KnowledgeChunk.APPROVAL_AUTO,
                        KnowledgeChunk.APPROVAL_ADMIN,
                    ],
                ).count(),
                "entities": KnowledgeEntity.objects.count(),
                "relations": KnowledgeRelation.objects.count(),
                "golden_tests": GoldenTestCase.objects.filter(is_active=True).count(),
            },
            "last_jobs": last_jobs,
            "last_eval": {
                "started_at": last_eval.started_at,
                "recall_at_5": last_eval.recall_at_5,
                "mrr": last_eval.mrr,
            } if last_eval else None,
        })


class SourcesView(APIView):
    def get_permissions(self):
        return _public_perm()

    def get(self, request):
        sources = KnowledgeSource.objects.filter(is_active=True).values(
            "slug", "name", "license", "attribution", "description",
            "source_url", "chunk_count",
        )
        return Response({"sources": list(sources)})


class KBUploadThrottle(UserRateThrottle):
    """Per-user cap on knowledge-base uploads (files sit on the app disk
    until an admin reviews them)."""
    scope = "kb_upload"
    rate = os.getenv("DRF_THROTTLE_KB_UPLOAD", "20/day")


def _strict_bool(value) -> bool:
    """Multipart sends strings: only an explicit yes counts ('false', '0'
    and '' are False — bool('false') is True)."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


KB_UPLOAD_MAX_BYTES = int(os.getenv("KB_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
KB_UPLOAD_TYPES = {
    ".pdf": {"application/pdf", "application/x-pdf"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain"},
    ".txt": {"text/plain"},
}


def _upload_error(file_obj):
    """Why this file cannot be accepted, or None."""
    name = (getattr(file_obj, "name", "") or "").lower()
    ext = os.path.splitext(name)[1]
    if ext not in KB_UPLOAD_TYPES:
        return "only .pdf, .md and .txt files are accepted"
    size = getattr(file_obj, "size", None) or 0
    if size <= 0:
        return "file is empty"
    if size > KB_UPLOAD_MAX_BYTES:
        return f"file is too large (max {KB_UPLOAD_MAX_BYTES // (1024 * 1024)} MB)"
    content_type = (getattr(file_obj, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/octet-stream" and content_type not in KB_UPLOAD_TYPES[ext]:
        return "file type does not match its extension"
    try:
        head = file_obj.read(2048)
        file_obj.seek(0)
    except Exception:
        return "file could not be read"
    if ext == ".pdf":
        if not head.startswith(b"%PDF-"):
            return "file is not a PDF"
    elif b"\x00" in head:
        return "text files must not contain binary data"
    return None


class UploadView(APIView):
    """POST /api/knowledge/upload/ — user upload with rights attestation.

    Accepts .pdf/.md/.txt up to KB_UPLOAD_MAX_BYTES, checks the declared type
    and the file's first bytes, parses ``rights_attested`` strictly and is
    rate-limited per user.
    """
    throttle_classes = [KBUploadThrottle]

    def get_permissions(self):
        return _public_perm()

    def post(self, request):
        title = str(request.data.get("title", "") or "").strip()
        source_description = str(request.data.get("source_description", "") or "").strip()
        rights_attested = _strict_bool(request.data.get("rights_attested"))
        file_obj = request.FILES.get("file")
        if not title or not file_obj:
            return Response({"error": "title and file are required"}, status=400)
        if not rights_attested:
            return Response({"error": "rights_attested must be true"}, status=400)
        if len(title) > 255:
            return Response({"error": "title is too long (max 255 characters)"}, status=400)
        if len(source_description) > 300:
            return Response({"error": "source_description is too long (max 300 characters)"}, status=400)
        problem = _upload_error(file_obj)
        if problem:
            return Response({"error": problem}, status=400)
        upload = UserUploadAttestation.objects.create(
            user=request.user if request.user.is_authenticated else None,
            title=title,
            source_description=source_description,
            rights_attested=rights_attested,
            file=file_obj,
            decision="pending",
        )
        return Response({
            "upload_id": upload.id,
            "title": upload.title,
            "decision": upload.decision,
            "message": "Upload received. Pending admin review.",
        }, status=201)


class IngestView(APIView):
    """POST /api/knowledge/ingest/ — admin-only ingestion trigger."""

    def get_permissions(self):
        return _admin_perm()

    def post(self, request):
        from knowledge_base.connectors import (
            InternalNotesConnector, NCBIBookshelfConnector,
            OpenStaxMicrobiologyConnector, OpenStaxPsychologyConnector,
            GovernmentGuidelinesConnector, UPSCConnector, NHMConnector,
            MoHFWConnector, ICMRConnector, NMCConnector,
            UserUploadsConnector,
        )
        connector_name = request.data.get("connector", "internal-notes")
        kwargs = {k: v for k, v in request.data.items() if k != "connector"}
        if "max_chunks" in kwargs:
            try:
                kwargs["max_chunks"] = int(kwargs["max_chunks"])
            except (TypeError, ValueError):
                pass
        # Strip unsupported keys per connector
        clean_kwargs = {}
        if connector_name == "ncbi-bookshelf":
            clean_kwargs = {k: v for k, v in kwargs.items()
                            if k in {"query", "max_records", "db"}}
        elif connector_name in {"openstax-anatomy",
                                "openstax-microbiology",
                                "openstax-psychology"}:
            clean_kwargs = {k: v for k, v in kwargs.items()
                            if k in {"max_chapters"}}
        elif connector_name in {"internal-notes",
                                "mohfw-india", "upsc", "nhm-india",
                                "icmr", "nmc-india"}:
            clean_kwargs = {}
        elif connector_name == "user-uploads":
            clean_kwargs = {}
        else:
            return Response({"error": f"unknown connector '{connector_name}'"},
                            status=400)

        connector_map = {
            "internal-notes": InternalNotesConnector(),
            "ncbi-bookshelf": NCBIBookshelfConnector(),
            "openstax-anatomy": None,  # use OpenStaxConnector directly with collection
            "openstax-microbiology": OpenStaxMicrobiologyConnector(),
            "openstax-psychology": OpenStaxPsychologyConnector(),
            "mohfw-india": MoHFWConnector(),
            "upsc": UPSCConnector(),
            "nhm-india": NHMConnector(),
            "icmr": ICMRConnector(),
            "nmc-india": NMCConnector(),
            "user-uploads": UserUploadsConnector(),
        }
        connector = connector_map.get(connector_name)
        if connector is None:
            return Response({"error": f"connector '{connector_name}' not implemented"},
                            status=400)

        from knowledge_base.services.ingestion import IngestionService
        service = IngestionService(connector, triggered_by=request.user
                                   if request.user.is_authenticated else None)
        try:
            result = service.run(**clean_kwargs)
        except Exception:
            logger.exception("Ingestion API failed")
            return Response({"error": "Operation failed; see server logs for details."}, status=500)

        return Response({
            "job_id": result.job_id,
            "source_slug": result.source_slug,
            "chunks_added": result.chunks_added,
            "chunks_updated": result.chunks_updated,
            "chunks_rejected": result.chunks_rejected,
            "status": result.status,
            "error": result.error,
        })


class IndexEmbeddingsView(APIView):
    """POST /api/knowledge/index/ — backfill embeddings."""

    def get_permissions(self):
        return _admin_perm()

    def post(self, request):
        from knowledge_base.services.indexer import EmbeddingIndexer
        try:
            max_chunks = request.data.get("max_chunks")
            max_chunks = int(max_chunks) if max_chunks else None
            n = EmbeddingIndexer().index_pending(max_chunks=max_chunks)
            return Response({"indexed": n})
        except Exception:
            logger.exception("Indexing failed")
            return Response({"error": "Operation failed; see server logs for details."}, status=500)


class ExtractKGView(APIView):
    """POST /api/knowledge/extract-kg/ — run KG extractor."""

    def get_permissions(self):
        return _admin_perm()

    def post(self, request):
        from knowledge_base.retrieval.kg_extractor import KGExtractor
        try:
            subject = request.data.get("subject") or None
            result = KGExtractor().extract_all(subject=subject)
            return Response(result)
        except Exception:
            logger.exception("KG extraction failed")
            return Response({"error": "Operation failed; see server logs for details."}, status=500)


class EvalView(APIView):
    """GET /api/knowledge/eval/ — run golden test set."""

    def get_permissions(self):
        return _admin_perm()

    def get(self, request):
        from knowledge_base.eval.harness import run_evaluation
        try:
            result = run_evaluation()
            return Response(result)
        except Exception:
            logger.exception("Eval failed")
            return Response({"error": "Operation failed; see server logs for details."}, status=500)


class HealthView(APIView):
    """Public health check for the KB subsystem."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "chunks": KnowledgeChunk.objects.filter(is_active=True).count(),
            "sources": KnowledgeSource.objects.filter(is_active=True).count(),
        })