"""
Enhanced AI Engine API Views with RAG integration.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.conf import settings as django_settings

from .services import AIService


def _get_permission():
    """Allow unauthenticated access in DEBUG mode for development."""
    if getattr(django_settings, 'DEBUG', False):
        return [AllowAny()]
    return [IsAuthenticated()]


class AskTutorView(APIView):
    """AI Tutor — RAG-grounded medical Q&A."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question = request.data.get('question', '')
        context = request.data.get('context', '')
        if not question:
            return Response({'error': 'Question is required'}, status=400)

        service = AIService()
        response = service.ask_tutor(question, context)
        return Response({'response': response})


class GenerateMnemonicView(APIView):
    """Generate memory tricks for medical topics."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        topic = request.data.get('topic', '')
        concept = request.data.get('concept', '')
        if not topic:
            return Response({'error': 'Topic is required'}, status=400)

        service = AIService()
        mnemonic = service.generate_mnemonic(topic, concept)
        return Response({'mnemonic': mnemonic})


class ExplainConceptView(APIView):
    """Explain medical concepts from basics."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        concept = request.data.get('concept', '')
        level = request.data.get('level', 'basic')
        if not concept:
            return Response({'error': 'Concept is required'}, status=400)

        service = AIService()
        explanation = service.explain_concept(concept, level)
        return Response({'explanation': explanation})


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

        service = AIService()
        analysis = service.analyze_question(question_text, options, correct_answer)
        return Response({'analysis': analysis})


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

        service = AIService()
        result = service.rag_answer(question)
        return Response(result)


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

        service = AIService()
        plan = service.generate_study_plan(weak_topics, days_remaining, user_analytics)
        return Response({'study_plan': plan})


class HighYieldTopicsView(APIView):
    """Get AI-predicted high-yield topics for CMS exam."""

    def get_permissions(self):
        return _get_permission()

    def get(self, request):
        service = AIService()
        predictions = service.predict_high_yield_topics()
        return Response({'predictions': predictions})


class KnowledgeUploadView(APIView):
    """Upload a file (PDF/MD/TXT) to add to AI knowledge base."""

    def get_permissions(self):
        return _get_permission()

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
    """Scan for new files in Medura_Train and auto-index them."""

    def get_permissions(self):
        return _get_permission()

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

        service = AIService()
        questions = service.generate_questions(subject, topic, difficulty, count)
        return Response({'questions': questions, 'count': len(questions)})


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
