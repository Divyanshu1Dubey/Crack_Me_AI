"""crack_cms URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/questions/', include('questions.urls')),
    path('api/tests/', include('tests_engine.urls')),
    path('api/analytics/', include('analytics.urls')),
    path('api/ai/', include('ai_engine.urls')),
    path('api/textbooks/', include('textbooks.urls')),
    path('api/resources/', include('resources.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
