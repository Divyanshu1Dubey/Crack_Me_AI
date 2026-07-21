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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission, AllowAny
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
    if getattr(django_settings, "DEBUG", False):
        return [AllowAny()]
    return [IsAuthenticated()]


def _admin_perm():
    if getattr(django_settings, "DEBUG", False):
        return [AllowAny()]
    return [IsAdminUser()]


class AskMonicaView(APIView):
    """POST /api/knowledge/ask/ — citation-aware answer."""

    def get_permissions(self):
        return _public_perm()

    def post(self, request):
        question = request.data.get("question", "").strip()
        subject = request.data.get("subject") or None
        if not question:
            return Response({"error": "question is required"}, status=400)
        try:
            monica = Monica()
            result = monica.answer(question, subject=subject)
            return Response({
                "answer": result.answer,
                "citations": result.citations,
                "confidence": result.confidence,
                "used_kb": result.used_kb,
                "retrieval_count": result.retrieval_count,
                "query_expansion": result.query_expansion,
            })
        except Exception as e:
            logger.exception("Monica ask failed")
            return Response({"error": "knowledge base temporarily unavailable",
                             "detail": str(e)}, status=503)


class SearchView(APIView):
    """POST /api/knowledge/search/ — retrieval only, no LLM call."""

    def get_permissions(self):
        return _public_perm()

    def post(self, request):
        query = request.data.get("query", "").strip()
        subject = request.data.get("subject") or None
        source_slugs = request.data.get("source_slugs") or None
        top_k = int(request.data.get("top_k", 8))
        if not query:
            return Response({"error": "query is required"}, status=400)
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
                        "subject": c.subject,
                        "topic": c.topic,
                        "citation": c.citation,
                    } for c in results
                ],
            })
        except Exception as e:
            logger.exception("Search failed")
            return Response({"error": "search failed", "detail": str(e)},
                            status=503)


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


class UploadView(APIView):
    """POST /api/knowledge/upload/ — user upload with rights attestation."""

    def get_permissions(self):
        return _public_perm()

    def post(self, request):
        title = request.data.get("title", "").strip()
        source_description = request.data.get("source_description", "").strip()
        rights_attested = bool(request.data.get("rights_attested"))
        file_obj = request.FILES.get("file")
        if not title or not file_obj:
            return Response({"error": "title and file are required"}, status=400)
        if not rights_attested:
            return Response({"error": "rights_attested must be true"}, status=400)
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
        except Exception as e:
            logger.exception("Ingestion API failed")
            return Response({"error": str(e)}, status=500)

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
        except Exception as e:
            logger.exception("Indexing failed")
            return Response({"error": str(e)}, status=500)


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
        except Exception as e:
            logger.exception("KG extraction failed")
            return Response({"error": str(e)}, status=500)


class EvalView(APIView):
    """GET /api/knowledge/eval/ — run golden test set."""

    def get_permissions(self):
        return _admin_perm()

    def get(self, request):
        from knowledge_base.eval.harness import run_evaluation
        try:
            result = run_evaluation()
            return Response(result)
        except Exception as e:
            logger.exception("Eval failed")
            return Response({"error": str(e)}, status=500)


class HealthView(APIView):
    """Public health check for the KB subsystem."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "chunks": KnowledgeChunk.objects.filter(is_active=True).count(),
            "sources": KnowledgeSource.objects.filter(is_active=True).count(),
        })