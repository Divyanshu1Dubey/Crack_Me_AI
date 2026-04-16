"""
Django settings for crack_cms project.
AI-Powered UPSC CMS Preparation Platform
"""
import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()  # Load .env file (does not override existing system env vars)

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Sentry Error Tracking ────────────────────────────────────────────
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.httpx import HttpxIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    import logging

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            HttpxIntegration(), 
            LoggingIntegration(
                level=logging.INFO,       
                event_level=logging.ERROR 
            ),
        ],
        traces_sample_rate=1.0, 
        send_default_pii=True,
    )

SECRET_KEY = (
    os.getenv('DJANGO_SECRET_KEY')
    or os.getenv('SECRET_KEY')
    or 'django-insecure-change-me-in-production-upsc-cms-2024'
)

DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
CEREBRAS_API_KEY = os.getenv('CEREBRAS_API_KEY', '')
COHERE_API_KEY = os.getenv('COHERE_API_KEY', '')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY', '')
AIML_API_KEY = os.getenv('AIML_API_KEY', '')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')
NVIDIA_MISTRAL_API_KEY = os.getenv('NVIDIA_MISTRAL_API_KEY', '')


ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,*').split(',') if h.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    # Local apps
    'accounts',
    'questions',
    'tests_engine',
    'analytics',
    'ai_engine',
    'textbooks',
    'resources',
    # Security
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'crack_cms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'crack_cms.wsgi.application'

# Database
DATABASE_URL = (
    os.getenv('DATABASE_URL')
    or os.getenv('SUPABASE_DATABASE_URL')
    or ''
).strip()
# Use in-memory SQLite for GitHub CI to avoid LFS pointer file issues
IS_CI = os.getenv('GITHUB_ACTIONS') == 'true'
IS_PRODUCTION_RUNTIME = not DEBUG and not IS_CI

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
elif IS_CI:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
else:
    if IS_PRODUCTION_RUNTIME:
        raise ImproperlyConfigured(
            'Production database URL is missing. '
            'Set DATABASE_URL (or SUPABASE_DATABASE_URL) to your Supabase Postgres connection string.'
        )

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

if DATABASES['default'].get('ENGINE', '').endswith('sqlite3'):
    sqlite_name = str(DATABASES['default'].get('NAME', ''))
    if sqlite_name and sqlite_name != ':memory:' and os.path.exists(sqlite_name):
        # Detect accidental Git LFS pointer checked in as db.sqlite3.
        with open(sqlite_name, 'rb') as sqlite_file:
            header = sqlite_file.read(64)
        if header.startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise ImproperlyConfigured(
                f'SQLite database at {sqlite_name} is a Git LFS pointer, not a real DB file. '
                'Use Postgres/Supabase in production or recreate a valid local sqlite database.'
            )

# Keep database failures fast in production so API returns explicit 5xx instead of platform 504 timeouts.
if DATABASES['default'].get('ENGINE', '').endswith('postgresql'):
    db_options = DATABASES['default'].setdefault('OPTIONS', {})
    db_options.setdefault('connect_timeout', int(os.getenv('DB_CONNECT_TIMEOUT', '5')))

# Runtime migration repair can cause long request hangs on hosted environments; keep disabled in production.
ENABLE_RUNTIME_SCHEMA_REPAIR = os.getenv(
    'ENABLE_RUNTIME_SCHEMA_REPAIR',
    'true' if DEBUG else 'false',
).lower() == 'true'

# Auth
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# django-axes: brute-force login protection
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
AXES_FAILURE_LIMIT = 5  # Lock after 5 failed attempts
AXES_COOLOFF_TIME = timedelta(minutes=30)  # 30-minute lockout
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']  # Lock by username and IP
AXES_RESET_ON_SUCCESS = True  # Reset counter on successful login

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins (needed for production)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',') if o.strip()]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static & Media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email — Gmail SMTP for password reset
# In development, use console backend if credentials are missing
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER') or os.getenv('SMTP_USERNAME', 'crackwith.ai@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD') or os.getenv('SMTP_PASSWORD', '')

# Choose email backend based on credentials availability
if EMAIL_HOST_PASSWORD and EMAIL_HOST_PASSWORD.strip():
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
else:
    # Fallback to console output for development (passwords visible in console logs)
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', f'CrackCMS <{EMAIL_HOST_USER}>')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '20'))
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# Logging — ensures API hits and AI errors show up in production logs
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        } if not DEBUG else {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'ai_engine': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# AI Configuration (keys loaded at top of file from .env)

# Training Data & RAG Configuration
MEDURA_TRAIN_DIR = BASE_DIR / 'Medura_Train'
CHROMA_DB_DIR = str(BASE_DIR / 'chroma_db')
RAG_CHUNK_SIZE = 500
RAG_CHUNK_OVERLAP = 50
TEXTBOOK_SCREENSHOT_DIR = str(MEDIA_ROOT / 'textbook_screenshots')

# ── Cache Configuration ─────────────────────────────────────────────
# Uses Redis if REDIS_URL is set, otherwise falls back to local memory cache.
REDIS_URL = os.getenv('REDIS_URL', '')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'TIMEOUT': 86400,  # 24 hours default
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'crackcms-cache',
        }
    }
