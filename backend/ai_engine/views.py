"""
Enhanced AI Engine API Views with RAG integration.

Token System Integration:
- Every AI call consumes 1 token (checked via consume_ai_token()).
- Admins (user.is_admin) bypass token limits entirely.
- Students get free daily/weekly tokens; after exhaustion, they must buy tokens.
- Token config is managed via Django Admin > Token Configuration.
"""
import json
import logging
import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import status
from django.conf import settings as django_settings
from django.db.utils import OperationalError, ProgrammingError

from .services import AIService
from accounts.models import TokenBalance

logger = logging.getLogger(__name__)


class IsAdminUser(BasePermission):
    """Custom permission to only allow admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (hasattr(request.user, 'is_admin') and request.user.is_admin or request.user.is_superuser)
        )


def _get_permission():
    """Allow unauthenticated access in DEBUG mode for development."""
    if getattr(django_settings, 'DEBUG', False):
        return [AllowAny()]
    return [IsAuthenticated()]


def _get_admin_permission():
    """Only allow admin users (for upload/train features)."""
    if getattr(django_settings, 'DEBUG', False):
        return [AllowAny()]  # Allow in debug for testing
    return [IsAdminUser()]


class AITutorThrottleMixin:
    """Apply the 'ai_tutor' scoped rate limit (30/min default — see settings.REST_FRAMEWORK).

    Mix in on any AI tutor / RAG / generation endpoint to defend against
    runaway agent loops or scripts that hammer the LLM round-robin.
    Admins inherit the auth permission; the throttle layer lives independently.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_tutor'


def consume_ai_token(request):
    """
    Check and consume 1 AI token for the requesting user.

    Returns:
        (True, None) — token consumed successfully (or bypassed), proceed with AI call.
        (False, Response) — insufficient tokens, return the error response.

    Bypass rules (in priority order):
      1. Unauthenticated in DEBUG mode → bypass (dev only).
      2. Admin (`user.is_admin`) → unlimited.
      3. Active subscription with `unlimited_ai=True` (1_year / legacy / admin_grant)
         → unlimited, no token deducted. THIS IS THE FIX FOR:
         "I paid for Premium but tokens keep decreasing."
      4. Otherwise → consume 1 token. If insufficient, return 402.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        if getattr(django_settings, 'DEBUG', False):
            return True, None
        return False, Response({'error': 'Authentication required'}, status=401)

    # 1. Admins have unlimited tokens
    if user.is_admin:
        return True, None

    # 2. Active subscription bypass (the critical fix)
    try:
        from accounts.models import Subscription
        sub = Subscription.get_active_subscription(user)
        if sub and sub.is_active and sub.unlimited_ai:
            return True, None
    except Exception:
        # If subscription lookup fails for any reason, fall through to token
        # metering rather than letting a transient DB error lock the user out.
        logger.exception('consume_ai_token: subscription lookup failed; falling back to token metering')

    balance, _ = TokenBalance.objects.get_or_create(user=user)
    if balance.consume_token(amount=1):
        return True, None

    return False, Response({
        'error': 'insufficient_tokens',
        'message': 'You have exhausted your AI tokens. Subscribe for unlimited usage or purchase more tokens.',
        'available': balance.available_tokens,
    }, status=429)


def refund_ai_token(request):
    """Refund AI tokens if the AI call fails after token was consumed.

    The prior implementation only refunded daily/weekly counters and never
    restored feedback_credits or purchased_tokens — meaning every AI failure
    silently cost the user 1 paid token. We now write a 'consume' transaction
    on success and a matching 'refund' on failure so the source pool is
    reversed exactly.
    """
    from accounts.models import TokenBalance, TokenTransaction

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_admin:
        return

    try:
        balance = TokenBalance.objects.get(user=user)
        balance.refund_token(amount=1)
        # Audit log so refunds are visible in transaction history
        TokenTransaction.objects.create(
            user=user,
            transaction_type='refund',
            amount=1,
            price_paid=0,
            note='AI call failed — token refunded',
        )
        logger.info(f"Refunded 1 AI token for user {user.username}")
    except TokenBalance.DoesNotExist:
        pass


class AskTutorView(AITutorThrottleMixin, APIView):
    """AI Tutor — RAG-grounded medical Q&A."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question = request.data.get('question', '')
        context = request.data.get('context', '')
        if not question:
            return Response({'error': 'Question is required'}, status=400)

        # Token check — admins bypass
        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            response = service.ask_tutor(question, context)
            return Response({'response': response})
        except Exception as e:
            logger.error(f"AskTutor failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class GenerateMnemonicView(AITutorThrottleMixin, APIView):
    """Generate memory tricks for medical topics."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        topic = request.data.get('topic', '')
        concept = request.data.get('concept', '')
        if not topic:
            return Response({'error': 'Topic is required'}, status=400)

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            mnemonic = service.generate_mnemonic(topic, concept)
            return Response({'mnemonic': mnemonic})
        except Exception as e:
            logger.error(f"GenerateMnemonic failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class ExplainConceptView(AITutorThrottleMixin, APIView):
    """Explain medical concepts from basics."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        concept = request.data.get('concept', '')
        level = request.data.get('level', 'basic')
        if not concept:
            return Response({'error': 'Concept is required'}, status=400)

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            explanation = service.explain_concept(concept, level)
            return Response({'explanation': explanation})
        except Exception as e:
            logger.error(f"ExplainConcept failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class AnalyzeQuestionView(AITutorThrottleMixin, APIView):
    """Analyze a CMS question — concepts, reasoning, strategy."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question_text = request.data.get('question_text', '')
        options = request.data.get('options', {})
        correct_answer = request.data.get('correct_answer', '')
        if not question_text:
            return Response({'error': 'question_text is required'}, status=400)

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            analysis = service.analyze_question(question_text, options, correct_answer)
            return Response({'analysis': analysis})
        except Exception as e:
            logger.error(f"AnalyzeQuestion failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class ExplainAfterAnswerView(AITutorThrottleMixin, APIView):
    """Rich AI explanation after answering a question — textbook refs, mnemonics, related concepts."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question_id = request.data.get('question_id')
        question_text = request.data.get('question_text', '')
        
        from questions.models import Question
        from django.utils import timezone
        import json
        
        db_question = None
        if question_id:
            db_question = Question.objects.filter(id=question_id).first()
        elif question_text:
            db_question = Question.objects.filter(question_text=question_text).first()
            
        if db_question and db_question.ai_generated_at:
            is_correct = request.data.get('selected_answer') == request.data.get('correct_answer')
            try:
                cached_json = json.loads(db_question.ai_explanation)
                # BUG FIX (2026-07-26): ExplainQuestionView stores its
                # result as `{"analysis": "<markdown>", "context": {...}}`
                # while ExplainAfterAnswerView returns the rich shape with
                # `core_concept`, `why_correct`, `mnemonic`, etc. If we
                # hand the ExplainQuestionView shape back to a client
                # expecting the rich keys, every Deep-Analysis panel
                # disappears (only the header renders) — the user sees
                # an empty "AI-Powered Deep Analysis" block and reports
                # the button is broken.
                # Detect the wrong-shape cache and fall through to
                # regenerate the rich payload.
                if not isinstance(cached_json, dict):
                    raise ValueError("cached ai_explanation is not a JSON object")
                if 'analysis' in cached_json and 'context' in cached_json and 'core_concept' not in cached_json:
                    raise ValueError("cached ai_explanation is ExplainQuestionView shape, regenerating as rich")
                cached_json['is_correct'] = is_correct
                return Response(cached_json)
            except Exception:
                pass # Fallback to regenerate if parsing fails
        
        if not question_text and db_question:
            question_text = db_question.question_text

        if not question_text:
            return Response({'error': 'question_text is required'}, status=400)

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        options = request.data.get('options', {})
        correct_answer = request.data.get('correct_answer', '')
        selected_answer = request.data.get('selected_answer', '')
        subject = request.data.get('subject', '')
        topic = request.data.get('topic', '')

        try:
            service = AIService()
            result = service.explain_after_answer(
                question_text, options, correct_answer, selected_answer, subject, topic
            )
            
            if db_question:
                db_question.ai_explanation = json.dumps(result)
                db_question.ai_mnemonic = result.get('mnemonic', '')
                db_question.ai_clinical_pearl = result.get('clinical_pearl', '')
                db_question.learning_technique = result.get('exam_tip', '')
                db_question.ai_references = [result.get('textbook_reference', {})]
                db_question.concept_keywords = result.get('around_concepts', [])
                db_question.ai_generated_at = timezone.now()
                db_question.ai_model = 'RoundRobin-11'
                db_question.ai_version = 'v2-verify'
                
                # Auto-flag questions where AI disagrees with stored answer
                ai_verified = result.get('ai_verified_answer', '').strip().upper()[:1]
                answer_mismatch = result.get('answer_mismatch', False)
                if answer_mismatch and ai_verified in ('A', 'B', 'C', 'D') and ai_verified != correct_answer:
                    db_question.needs_review = True
                    db_question.is_disputed = True
                    logger.warning(
                        f"ANSWER MISMATCH Q#{db_question.id}: DB says {correct_answer}, "
                        f"AI says {ai_verified}. Reason: {result.get('confidence_note', 'N/A')[:200]}"
                    )
                
                db_question.save()
                
            return Response(result)
        except Exception as e:
            logger.error(f"ExplainAfterAnswer failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class ExplainQuestionView(AITutorThrottleMixin, APIView):
    """Get an AI explanation for a question by its DB id.

    The frontend player (`NeetPgPlayer.tsx`) calls
    `aiAPI.explainQuestion(questionId, {selected_answer, ...})` and expects
    `{explanation: <markdown>}`. This view:
      1. Loads the Question by id (404 if missing).
      2. Reuses the cached `ai_explanation` JSON if it's <24h old.
      3. Otherwise calls `AIService.analyze_question(...)` and returns
         the markdown wrapped as `{explanation, cached, question_id}`.

    Cost: 1 token (admins bypass). Refunded on AI failure.
    """

    def get_permissions(self):
        return _get_permission()

    def post(self, request, question_id: int):
        from django.utils import timezone
        from datetime import timedelta

        from questions.models import Question

        q = (
            Question.objects.filter(id=question_id)
            .select_related("subject", "topic")
            .first()
        )
        if not q:
            return Response({'error': f'Question {question_id} not found'}, status=404)

        # Cache hit: reuse the cached ai_explanation within 24h
        # unless the client asked for a custom prompt (different output)
        # or forced regeneration (e.g. user clicked "Regenerate").
        client_prompt = (request.data.get("prompt") or "").strip()
        force_regen = bool(request.data.get("force_regenerate"))
        if not client_prompt and not force_regen:
            if q.ai_explanation and q.ai_generated_at and timezone.now() - q.ai_generated_at < timedelta(hours=24):
                try:
                    cached = json.loads(q.ai_explanation) if isinstance(q.ai_explanation, str) else q.ai_explanation
                    # Frontend expects `explanation` key (markdown); explain_after_answer
                    # stores rich JSON with multiple fields. Stitch a markdown body so
                    # the player UI gets a single text blob.
                    explanation = _stitch_explanation_markdown(cached, q)
                    return Response({
                        'explanation': explanation,
                        'cached': True,
                        'question_id': q.id,
                        'ai_model': q.ai_model,
                        'ai_generated_at': q.ai_generated_at.isoformat(),
                    })
                except (ValueError, TypeError):
                    pass  # corrupt cache → fall through to regenerate

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            subject_name = q.subject.name if hasattr(q.subject, "name") else (q.subject or "")
            topic_name = q.topic.name if hasattr(q.topic, "name") else (q.topic or "")
            selected_answer = (request.data.get("selected_answer") or "").strip()

            prompt_ctx = {
                "selected_answer": selected_answer,
                "subject": subject_name,
                "topic": topic_name,
                "year": q.year,
                "exam_type": q.exam_type,
                "exam_source": q.exam_source,
            }

            analysis = service.analyze_question(
                q.question_text,
                {
                    "A": q.option_a,
                    "B": q.option_b,
                    "C": q.option_c,
                    "D": q.option_d,
                },
                q.correct_answer or "",
                user_prompt=client_prompt,
            )

            # Persist for next-time cache hit (best-effort)
            try:
                q.ai_explanation = json.dumps({
                    "analysis": analysis,
                    "context": prompt_ctx,
                })
                q.ai_model = "RoundRobin-11"
                q.ai_generated_at = timezone.now()
                q.ai_version = "explain-question-v1"
                q.save(update_fields=["ai_explanation", "ai_model", "ai_generated_at", "ai_version"])
            except Exception as save_exc:  # noqa: BLE001
                logger.warning("ExplainQuestion: cache write failed for Q%s: %s", q.id, save_exc)

            return Response({
                'explanation': analysis,
                'cached': False,
                'question_id': q.id,
                'ai_model': 'RoundRobin-11',
            })
        except Exception as e:
            logger.error(f"ExplainQuestion failed for Q{question_id}: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


def _stitch_explanation_markdown(cached: dict, q) -> str:
    """Convert cached explain_after_answer JSON into a single markdown blob.

    `ExplainAfterAnswerView` stores rich structured JSON (why_correct,
    mnemonic, clinical_pearl, etc.). The player UI wants one text field.

    `ExplainQuestionView` stores `{"analysis": "<markdown>", "context": {...}}`
    — in that case the `analysis` value IS the final markdown.
    """
    # Fast-path: ExplainQuestionView cache format — the "analysis" key
    # holds the complete markdown string produced by analyze_question().
    analysis_val = cached.get("analysis")
    if analysis_val and isinstance(analysis_val, str):
        # If the analysis value itself is a JSON string, try parsing it
        # and recursively extracting structured fields from it.
        stripped = analysis_val.strip()
        if stripped.startswith('{'):
            try:
                inner = json.loads(stripped)
                if isinstance(inner, dict):
                    return _stitch_explanation_markdown(inner, q)
            except (json.JSONDecodeError, ValueError):
                pass
        # Plain markdown — use directly (this is the normal case for
        # ExplainQuestionView responses).
        return analysis_val

    parts: list[str] = []
    core = cached.get("core_concept") or cached.get("ai_verified_answer")
    if core:
        parts.append(f"**Core concept:** {core}")
    why_correct = cached.get("why_correct")
    if why_correct:
        parts.append(f"\n**Why the correct answer is right:**\n{why_correct}")
    why_wrong = cached.get("why_wrong")
    if why_wrong:
        parts.append(f"\n**Why other options are wrong:**\n{why_wrong}")
    pearl = cached.get("clinical_pearl")
    if pearl:
        parts.append(f"\n**Clinical pearl:** {pearl}")
    high_yield = cached.get("high_yield_points") or []
    if high_yield:
        if isinstance(high_yield, list):
            parts.append("\n**High-yield points:**\n" + "\n".join(f"- {p}" for p in high_yield))
        else:
            parts.append(f"\n**High-yield points:**\n{high_yield}")
    mnemonic = cached.get("mnemonic")
    if mnemonic:
        parts.append(f"\n**Mnemonic:** {mnemonic}")
    tip = cached.get("exam_tip")
    if tip:
        parts.append(f"\n**Exam tip:** {tip}")
    ref = cached.get("textbook_reference")
    if ref:
        parts.append(f"\n**Textbook reference:** {ref}")
    if not parts:
        # Last resort: if the cached dict has no known keys, dump as JSON
        # so we at least surface *something* (shouldn't normally happen).
        parts.append(json.dumps(cached, indent=2, ensure_ascii=False))
    return "\n".join(parts)


class RAGSearchView(AITutorThrottleMixin, APIView):
    """Semantic search across indexed textbooks.

    Auth + token-cost: RAG search is a free (no-token) lookup, but it still
    requires authentication. Anonymous callers (including the DEBUG-mode
    allow-list) are rejected so a single attacker can't amplify compute
    against the TF-IDF store. The `ai_tutor` throttle cap (30/min) gives
    a per-user rate ceiling.
    """

    def get_permissions(self):
        return [IsAuthenticated()]

    def post(self, request):
        query = request.data.get('query', '')
        book_filter = request.data.get('book', None)
        n_results = min(int(request.data.get('n_results', 5)), 20)
        if not query:
            return Response({'error': 'Query is required'}, status=400)

        try:
            service = AIService()
            results = service.rag_search(query, book_filter, n_results)
            # Translate the legacy "RAG pipeline not initialized" payload
            # into a 503 the frontend can render as a friendly error
            # instead of surfacing a developer-only remediation string.
            if isinstance(results, dict) and results.get('error') == 'RAG pipeline not initialized':
                logger.warning("Textbook search requested but RAG is disabled (DISABLE_RAG=1)")
                return Response(
                    {
                        'error': 'textbook_search_unavailable',
                        'message': (
                            'Textbook search is temporarily unavailable. '
                            'Please switch to AI Tutor mode or try again later.'
                        ),
                    },
                    status=503,
                )
            return Response(results)
        except Exception as e:
            logger.error(f"RAGSearch failed: {e}")
            return Response(
                {
                    'error': 'textbook_search_unavailable',
                    'message': 'Textbook search is temporarily unavailable. Please try again shortly.',
                },
                status=503,
            )


class RAGAnswerView(AITutorThrottleMixin, APIView):
    """Get a textbook-grounded answer with citations."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question = request.data.get('question', '')
        if not question:
            return Response({'error': 'Question is required'}, status=400)

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            result = service.rag_answer(question)
            # If the RAG store is empty, the backend returns the legacy
            # "RAG pipeline not initialized" reminder that leaks an
            # operator-only command. Translate it into a user-facing
            # fallback: still answer with the general AI model so the
            # student gets *something* useful, and refund the token
            # because we didn't actually do a textbook-grounded answer.
            if (
                isinstance(result, dict)
                and 'RAG pipeline not initialized' in str(result.get('answer', ''))
            ):
                logger.warning("Textbook-mode answer requested but RAG is disabled (DISABLE_RAG=1)")
                refund_ai_token(request)
                return Response(
                    {
                        'answer': (
                            'Textbook search is temporarily unavailable right now. '
                            'Please switch to AI Tutor mode for a general answer, '
                            'or try again in a few minutes.'
                        ),
                        'citations': [],
                        'error': 'textbook_search_unavailable',
                    },
                    status=200,
                )
            return Response(result)
        except Exception as e:
            logger.error(f"RAGAnswer failed: {e}")
            refund_ai_token(request)
            return Response(
                {
                    'answer': (
                        'Textbook search is temporarily unavailable right now. '
                        'Please try again shortly.'
                    ),
                    'citations': [],
                    'error': 'textbook_search_unavailable',
                },
                status=503,
            )


class TextbookReferenceView(AITutorThrottleMixin, APIView):
    """Find textbook references for a question or topic.

    Auth required even in DEBUG: textbook-reference lookups drive real
    RAG cost and must not be reachable by anonymous callers.
    """

    def get_permissions(self):
        return [IsAuthenticated()]

    def post(self, request):
        question_text = request.data.get('question_text', '')
        if not question_text:
            return Response({'error': 'question_text is required'}, status=400)

        service = AIService()
        references = service.find_textbook_reference(question_text)
        return Response({'references': references})


class StudyPlanView(AITutorThrottleMixin, APIView):
    """Generate personalized study plan."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        weak_topics = request.data.get('weak_topics', [])
        days_remaining = request.data.get('days_remaining', 60)
        user_analytics = request.data.get('analytics', None)

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            plan = service.generate_study_plan(weak_topics, days_remaining, user_analytics)
            return Response({'study_plan': plan})
        except Exception as e:
            logger.error(f"StudyPlan failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class HighYieldTopicsView(AITutorThrottleMixin, APIView):
    """Get AI-predicted high-yield topics for CMS exam."""

    def get_permissions(self):
        return _get_permission()

    def get(self, request):
        service = AIService()
        predictions = service.predict_high_yield_topics()
        return Response({'predictions': predictions})


class KnowledgeUploadView(APIView):
    """Upload a file (PDF/MD/TXT) to add to AI knowledge base. Admin only."""

    def get_permissions(self):
        return _get_admin_permission()

    def post(self, request):
        from .auto_ingest import AutoIngestService

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'No file provided'}, status=400)

        book_name = request.data.get('book_name', '')
        ingest = AutoIngestService()
        result = ingest.ingest_uploaded_file(uploaded_file, book_name or None)
        return Response(result)


class KnowledgeScanView(APIView):
    """Scan for new files in Medura_Train and auto-index them. Admin only."""

    def get_permissions(self):
        return _get_admin_permission()

    def post(self, request):
        from .auto_ingest import AutoIngestService

        ingest = AutoIngestService()
        result = ingest.scan_for_new_files()
        return Response(result)


class KnowledgeStatsView(APIView):
    """Get AI knowledge base statistics."""

    def get_permissions(self):
        return _get_permission()

    def get(self, request):
        from .auto_ingest import AutoIngestService

        ingest = AutoIngestService()
        stats = ingest.get_knowledge_stats()
        return Response(stats)


class GenerateQuestionsView(AITutorThrottleMixin, APIView):
    """AI-generated practice MCQs for weak topics."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        subject = request.data.get('subject', '')
        topic = request.data.get('topic', '')
        difficulty = request.data.get('difficulty', 'medium')
        count = min(int(request.data.get('count', 5)), 20)
        if not subject:
            return Response({'error': 'Subject is required'}, status=400)

        ok, err = consume_ai_token(request)
        if not ok:
            return err

        try:
            service = AIService()
            questions = service.generate_questions(subject, topic, difficulty, count)
            return Response({'questions': questions, 'count': len(questions)})
        except Exception as e:
            logger.error(f"GenerateQuestions failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class PageScreenshotView(APIView):
    """Extract a page screenshot from a textbook PDF."""

    def get_permissions(self):
        return _get_permission()

    def get(self, request, question_id):
        from questions.models import Question
        from .document_processor import DocumentProcessor
        import os

        try:
            question = Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            return Response({'error': 'Question not found'}, status=404)

        # Check if screenshot already exists
        if question.page_screenshot:
            return Response({'screenshot_url': question.page_screenshot.url})

        # Try to find textbook reference and generate screenshot
        if question.page_number and question.book_name:
            # Find the PDF
            train_dir = str(getattr(__import__('django.conf', fromlist=['settings']).settings, 'MEDURA_TRAIN_DIR', ''))
            textbook_dirs = [
                os.path.join(train_dir, 'textbooks'),
                train_dir,
            ]

            for tb_dir in textbook_dirs:
                if not os.path.exists(tb_dir):
                    continue
                for f in os.listdir(tb_dir):
                    if f.endswith('.pdf') and question.book_name.lower() in f.lower():
                        pdf_path = os.path.join(tb_dir, f)
                        try:
                            page_num = int(question.page_number) - 1
                            screenshot_dir = str(getattr(__import__('django.conf', fromlist=['settings']).settings, 'TEXTBOOK_SCREENSHOT_DIR', '/tmp'))
                            os.makedirs(screenshot_dir, exist_ok=True)
                            output = DocumentProcessor.extract_page_image(pdf_path, page_num, screenshot_dir)
                            if output:
                                return Response({'screenshot_path': output})
                        except (ValueError, Exception) as e:
                            logger.error(f"Screenshot extraction failed: {e}")

        return Response({'error': 'No screenshot available'}, status=404)


class AIStatusView(APIView):
    """Check which AI providers are initialized (admin-only in production)."""
    permission_classes = property(lambda self: _get_admin_permission())

    def get_permissions(self):
        return _get_admin_permission()

    def get(self, request):
        try:
            service = AIService()
            # Mirror the providers list in _call_ai() so admin dashboards
            # reflect all 10 clients, not just the 2 the previous version
            # reported. Keeps the operator's "is the AI healthy?" view
            # in sync with the round-robin code path.
            providers = {
                'gemini': service.gemini_client is not None,
                'groq': service.groq is not None,
                'cerebras': service.cerebras is not None,
                'cohere': service.cohere is not None,
                'openrouter': service.openrouter is not None,
                'openrouter2': service.openrouter2 is not None,
                'github_models': service.github_models is not None,
                'huggingface': service.huggingface is not None,
                'mistral': service.mistral is not None,
                'nvidia_mistral': service.nvidia_mistral is not None,
            }
        except Exception as e:
            logger.error(f"AIService init failed: {e}")
            providers = {'error': str(e)}
        keys_present = {
            'GEMINI_API_KEY': bool(getattr(django_settings, 'GEMINI_API_KEY', '')),
            'GROQ_API_KEY': bool(getattr(django_settings, 'GROQ_API_KEY', '')),
            'CEREBRAS_API_KEY': bool(getattr(django_settings, 'CEREBRAS_API_KEY', '')),
            'COHERE_API_KEY': bool(getattr(django_settings, 'COHERE_API_KEY', '')),
            'OPENROUTER_API_KEY': bool(getattr(django_settings, 'OPENROUTER_API_KEY', '')),
            'OPENROUTER_API_KEY2': bool(os.getenv('OPENROUTER_API_KEY2', '')),
            'GITHUB_TOKEN': bool(getattr(django_settings, 'GITHUB_TOKEN', '')),
            'HUGGINGFACE_API_KEY': bool(getattr(django_settings, 'HUGGINGFACE_API_KEY', '')),
            'MISTRAL_API_KEY': bool(getattr(django_settings, 'MISTRAL_API_KEY', '')),
            'NVIDIA_MISTRAL_API_KEY': bool(getattr(django_settings, 'NVIDIA_MISTRAL_API_KEY', '')),
        }
        any_available = (
            any(v is True for v in providers.values())
            if providers and isinstance(next(iter(providers.values())), bool)
            else False
        )
        logger.info(f"AI Status check — providers: {providers}, keys_present: {keys_present}")
        return Response({
            'providers_initialized': providers,
            'keys_present': keys_present,
            'any_available': any_available,
        })


class AITestView(APIView):
    """Quick AI ping — tests if any provider can respond (admin-only in production)."""

    def get_permissions(self):
        return _get_admin_permission()

    def get(self, request):
        try:
            service = AIService()
            result = service._call_ai("Reply with exactly: OK", system="You are a test bot. Reply with one word only.", temperature=0, max_tokens=10)
            return Response({'status': 'ok', 'response': result[:100]})
        except Exception as e:
            logger.error(f"AI test failed: {e}")
            return Response({'status': 'error', 'error': str(e)}, status=500)


# =============================================================================
# CHAT HISTORY VIEWS
# =============================================================================

from rest_framework import generics
from .models import ChatSession, ChatMessage
from .serializers import ChatSessionSerializer, ChatSessionDetailSerializer, ChatMessageSerializer


class ChatSessionListCreateView(generics.ListCreateAPIView):
    """
    List user's chat sessions or create a new one.
    GET: Returns all non-archived sessions for the authenticated user.
    POST: Creates a new chat session.
    """
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            return ChatSession.objects.filter(
                user=self.request.user,
                is_archived=False
            ).order_by('-updated_at')[:50]  # Keep last 50 sessions
        except (OperationalError, ProgrammingError) as e:
            logger.warning(f"ChatSession table unavailable: {e}")
            return ChatSession.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ChatSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a specific chat session.
    """
    serializer_class = ChatSessionDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            return ChatSession.objects.filter(user=self.request.user)
        except (OperationalError, ProgrammingError) as e:
            logger.warning(f"ChatSession detail lookup failed (schema unavailable): {e}")
            return ChatSession.objects.none()

    def perform_destroy(self, instance):
        # Soft delete by archiving
        instance.is_archived = True
        instance.save()


class ChatMessageListView(generics.ListAPIView):
    """
    Get all messages in a specific chat session.
    """
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        session_id = self.kwargs.get('session_id')
        try:
            return ChatMessage.objects.filter(
                session_id=session_id,
                session__user=self.request.user
            )
        except (OperationalError, ProgrammingError) as e:
            logger.warning(f"ChatMessage table unavailable: {e}")
            return ChatMessage.objects.none()


class ChatMessageCreateView(AITutorThrottleMixin, APIView):
    """
    Add a message to a chat session (used when saving AI responses).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id, user=request.user)
        except (OperationalError, ProgrammingError) as e:
            logger.warning(f"Chat schema unavailable during message create: {e}")
            return Response({'error': 'Chat history storage is not initialized yet.'}, status=503)
        except ChatSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)

        role = request.data.get('role', 'user')
        content = request.data.get('content', '')
        mode = request.data.get('mode', '')
        citations = request.data.get('citations', [])

        if not content:
            return Response({'error': 'Content is required'}, status=400)

        message = ChatMessage.objects.create(
            session=session,
            role=role,
            content=content,
            mode=mode,
            citations=citations
        )

        # Update session title from first user message
        if role == 'user' and not session.title:
            session.title = content[:100]
            session.save()

        # Update session's updated_at timestamp
        session.save()

        return Response(ChatMessageSerializer(message).data, status=201)

class AIFeedbackView(APIView):
    """
    Handle user feedback on AI responses.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import AIFeedback
        query = request.data.get('query', '')
        response_text = request.data.get('response_text', '')
        is_helpful = request.data.get('is_helpful', True)
        report_reason = request.data.get('report_reason', '')
        comments = request.data.get('comments', '')

        AIFeedback.objects.create(
            user=request.user,
            query=query,
            response_text=response_text,
            is_helpful=is_helpful,
            report_reason=report_reason,
            comments=comments
        )

        return Response({"status": "Feedback recorded."})
