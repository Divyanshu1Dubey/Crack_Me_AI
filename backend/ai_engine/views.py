"""
Enhanced AI Engine API Views with RAG integration.

Token System Integration:
- Every AI call consumes 1 token (checked via consume_ai_token()).
- Admins (user.is_admin) bypass token limits entirely.
- Students get free daily/weekly tokens; after exhaustion, they must buy tokens.
- Token config is managed via Django Admin > Token Configuration.
"""
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
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


def consume_ai_token(request):
    """
    Check and consume 1 AI token for the requesting user.
    
    Returns:
        (True, None) — token consumed successfully, proceed with AI call.
        (False, Response) — insufficient tokens, return the error response.
    
    Admin users bypass token limits entirely.
    Unauthenticated users in DEBUG mode also bypass.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        # In DEBUG mode, unauthenticated requests are allowed
        if getattr(django_settings, 'DEBUG', False):
            return True, None
        return False, Response({'error': 'Authentication required'}, status=401)

    # Admins have unlimited tokens
    if user.is_admin:
        return True, None

    balance, _ = TokenBalance.objects.get_or_create(user=user)
    if balance.consume_token():
        return True, None

    return False, Response({
        'error': 'insufficient_tokens',
        'message': 'You have exhausted your AI tokens. Purchase more tokens to continue.',
        'available': balance.available_tokens,
    }, status=429)


def refund_ai_token(request):
    """Refund 1 AI token if the AI call fails after token was consumed."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_admin:
        return
    try:
        balance = TokenBalance.objects.get(user=user)
        balance.refund_token()
        logger.info(f"Refunded 1 AI token for user {user.username}")
    except TokenBalance.DoesNotExist:
        pass


class AskTutorView(APIView):
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


class GenerateMnemonicView(APIView):
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


class ExplainConceptView(APIView):
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


class AnalyzeQuestionView(APIView):
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


class ExplainAfterAnswerView(APIView):
    """Rich AI explanation after answering a question — textbook refs, mnemonics, related concepts."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question_text = request.data.get('question_text', '')
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
            return Response(result)
        except Exception as e:
            logger.error(f"ExplainAfterAnswer failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class RAGSearchView(APIView):
    """Semantic search across indexed textbooks."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        query = request.data.get('query', '')
        book_filter = request.data.get('book', None)
        n_results = min(int(request.data.get('n_results', 5)), 20)
        if not query:
            return Response({'error': 'Query is required'}, status=400)

        service = AIService()
        results = service.rag_search(query, book_filter, n_results)
        return Response(results)


class RAGAnswerView(APIView):
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
            return Response(result)
        except Exception as e:
            logger.error(f"RAGAnswer failed: {e}")
            refund_ai_token(request)
            return Response({'error': 'AI service temporarily unavailable. Token refunded.'}, status=503)


class TextbookReferenceView(APIView):
    """Find textbook references for a question or topic."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question_text = request.data.get('question_text', '')
        if not question_text:
            return Response({'error': 'question_text is required'}, status=400)

        service = AIService()
        references = service.find_textbook_reference(question_text)
        return Response({'references': references})


class StudyPlanView(APIView):
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


class HighYieldTopicsView(APIView):
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


class GenerateQuestionsView(APIView):
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
                            output = PDFProcessor.extract_page_image(pdf_path, page_num, screenshot_dir)
                            if output:
                                return Response({'screenshot_path': output})
                        except (ValueError, Exception) as e:
                            logger.error(f"Screenshot extraction failed: {e}")

        return Response({'error': 'No screenshot available'}, status=404)


class AIStatusView(APIView):
    """Check which AI providers are initialized (for debugging production issues)."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            service = AIService()
            providers = {
                'gemini': service.gemini_client is not None,
                'groq': service.groq is not None,
                'deepseek': service.deepseek is not None,
            }
        except Exception as e:
            logger.error(f"AIService init failed: {e}")
            providers = {'error': str(e)}
        keys_present = {
            'GEMINI_API_KEY': bool(getattr(django_settings, 'GEMINI_API_KEY', '')),
            'GROQ_API_KEY': bool(getattr(django_settings, 'GROQ_API_KEY', '')),
            'DEEPSEEK_API_KEY': bool(getattr(django_settings, 'DEEPSEEK_API_KEY', '')),
        }
        logger.info(f"AI Status check — providers: {providers}, keys_present: {keys_present}")
        return Response({
            'providers_initialized': providers,
            'keys_present': keys_present,
            'any_available': any(v is True for v in providers.values()) if isinstance(list(providers.values())[0], bool) else False,
        })


class AITestView(APIView):
    """Quick AI ping — tests if any provider can respond (AllowAny for debugging)."""
    authentication_classes = []
    permission_classes = [AllowAny]

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


class ChatMessageCreateView(APIView):
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
