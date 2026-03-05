from rest_framework import viewsets, permissions, parsers
from .models import Textbook, Chapter, PDFUpload
from .serializers import TextbookSerializer, ChapterSerializer, PDFUploadSerializer


class TextbookViewSet(viewsets.ModelViewSet):
    queryset = Textbook.objects.all()
    serializer_class = TextbookSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]


class PDFUploadViewSet(viewsets.ModelViewSet):
    serializer_class = PDFUploadSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return PDFUpload.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
