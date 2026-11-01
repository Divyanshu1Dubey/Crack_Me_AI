"""
Django settings for crack_cms project.
AI-Powered UPSC CMS Preparation Platform
"""
import os
import sys
import socket
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse
import re
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from crack_cms.client_ip import parse_num_proxies
from crack_cms.db_config import server_side_cursors_unsupported, statement_timeout_option

BASE_DIR = Path(__file__).resolve().parent.parent

# Env file selection. Local development points DJANGO_ENV_FILE at a separate
# file (e.g. `.env.localdev`, see `.env.localdev.example`) so the production
# `.env` -- live payment, SMTP and Sentry credentials -- is never loaded
# implicitly on a developer machine. Without the variable the historical
# behaviour (load `.env` from the working directory) is unchanged.
_env_file = os.getenv('DJANGO_ENV_FILE', '').strip()
if _env_file:
    _env_path = Path(_env_file)
    if not _env_path.is_absolute():
        _env_path = BASE_DIR / _env_path
    if not _env_path.exists():
        raise ImproperlyConfigured(f'DJANGO_ENV_FILE points to a missing file: {_env_path}')
    load_dotenv(_env_path, override=False)
else:
    load_dotenv()  # Load .env file (does not override existing system env vars)

# ── Hermetic test runs ──────────────────────────────────────────────
# `manage.py test` used to inherit live credentials from backend/.env: test
# failures were reported to the production Sentry and AI tests made real
# provider calls. Under the test runner every external-service secret is
# blanked (tests mock what they need). Opt out explicitly with
# ALLOW_EXTERNAL_SERVICES_IN_TESTS=1.
_TEST_RUN = 'test' in sys.argv or 'pytest' in sys.modules
if _TEST_RUN and os.getenv('ALLOW_EXTERNAL_SERVICES_IN_TESTS', '').strip().lower() not in ('1', 'true', 'yes'):
    for _secret in (
        'SENTRY_DSN', 'GEMINI_API_KEY', 'GROQ_API_KEY', 'CEREBRAS_API_KEY', 'COHERE_API_KEY',
        'OPENROUTER_API_KEY', 'OPENROUTER_API_KEY2', 'TOGETHER_API_KEY', 'GITHUB_TOKEN',
        'HUGGINGFACE_API_KEY', 'AIML_API_KEY', 'MISTRAL_API_KEY', 'NVIDIA_MISTRAL_API_KEY',
        'DEEPSEEK_API_KEY', 'OMNIROUTE_API_KEY', 'OMNIROUTEAPI', 'OMNIROUTE_BASE_URL', 'NCBI_API_KEY',
        'SUPABASE_SERVICE_ROLE_KEY', 'RAZORPAY_KEY_SECRET', 'RAZORPAY_WEBHOOK_SECRET',
        'EMAIL_HOST_PASSWORD', 'REDIS_URL',
    ):
        os.environ[_secret] = ''

# ── Sentry Error Tracking ────────────────────────────────────────────
# Production-safe default. Local development can opt in through backend/.env.
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.httpx import HttpxIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    import logging

    sentry_traces_rate = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '1.0' if DEBUG else '0.1'))
    sentry_send_pii = os.getenv('SENTRY_SEND_DEFAULT_PII', 'true' if DEBUG else 'false').lower() == 'true'

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
        traces_sample_rate=sentry_traces_rate,
        send_default_pii=sentry_send_pii,
    )

is_testing = 'test' in sys.argv or 'pytest' in sys.modules
# Readable as settings.TESTING (Django only exposes upper-case names): the
# production posture check in crack_cms/urls.py is skipped under the test
# runner, which substitutes a test SECRET_KEY below.
TESTING = is_testing
# crack_cms/security.py resolves the key the same way; keep the two in sync.
secret_key_from_env = (os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY') or '').strip()
if not secret_key_from_env and not DEBUG:
    if is_testing:
        secret_key_from_env = 'ci-secret-key-12345'
    else:
        raise ImproperlyConfigured('SECRET_KEY is required when DEBUG is false.')

SECRET_KEY = secret_key_from_env or ('ci-secret-key-12345' if is_testing else 'django-insecure-local-dev-only')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
CEREBRAS_API_KEY = os.getenv('CEREBRAS_API_KEY', '')
COHERE_API_KEY = os.getenv('COHERE_API_KEY', '')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY', '')
AIML_API_KEY = os.getenv('AIML_API_KEY', '')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')
NVIDIA_MISTRAL_API_KEY = os.getenv('NVIDIA_MISTRAL_API_KEY', '')
OMNIROUTE_API_KEY = os.getenv('OMNIROUTE_API_KEY', '') or os.getenv('OMNIROUTEAPI', '')
OMNIROUTE_BASE_URL = os.getenv('OMNIROUTE_BASE_URL', 'https://omniroute-production-9d6b.up.railway.app/v1')


allowed_hosts_default = 'localhost,127.0.0.1,testserver'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', allowed_hosts_default).split(',') if h.strip()]

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
    'video_engine',
    'django_q',
    'jobs',
    'knowledge_base',
    'importers',
    # Production Content Ingestion Platform (Phase 1, additive only).
    # Isolated from UPSC CMS — see backend/ingestion/.
    'ingestion',
    # Generic material importer (DOCX/PDF/PPT) for cms_exclusive_material.
    'material_importer',
    # Blog management backend — model, admin, DRF API.
    'blog_engine',
    # Security
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
    'questions.middleware.RateLimitMiddleware',
    'crack_cms.cache_middleware.DisableApiCacheMiddleware',
    'crack_cms.cross_origin.CrossOriginResourcePolicyMiddleware',
    'accounts.middleware.UpdateLastSeenMiddleware',
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
# A test run creates (and drops) its own database next to DATABASE_URL, so it
# must never point at a remote server -- backend/.env holds the production
# pooler URL. Local hosts are fine; list others in TEST_DATABASE_HOSTS.
if _TEST_RUN and DATABASE_URL:
    _test_db_host = (urlparse(DATABASE_URL).hostname or '').strip().lower()
    _allowed_test_hosts = {'localhost', '127.0.0.1', '::1', 'postgres', 'db'} | {
        h.strip().lower() for h in os.getenv('TEST_DATABASE_HOSTS', '').split(',') if h.strip()
    }
    if _test_db_host and _test_db_host not in _allowed_test_hosts:
        raise ImproperlyConfigured(
            f'Refusing to run tests against the remote database host "{_test_db_host}". '
            'Unset DATABASE_URL / SUPABASE_DATABASE_URL (tests then use SQLite) or add the host to TEST_DATABASE_HOSTS.'
        )

# Use in-memory SQLite for GitHub CI to avoid LFS pointer file issues
IS_CI = os.getenv('GITHUB_ACTIONS') == 'true'
IS_PRODUCTION_RUNTIME = not DEBUG and not IS_CI
IS_COLLECTSTATIC = any(arg == 'collectstatic' for arg in sys.argv)


def _resolve_ipv4_address(hostname: str) -> str:
    """Resolve a hostname to the first IPv4 address, or empty string if unavailable."""
    if not hostname:
        return ''

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return ''

    for info in infos:
        addr = info[4][0]
        if addr:
            return addr
    return ''

if DATABASE_URL and not IS_COLLECTSTATIC:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv('CONN_MAX_AGE', '120')),
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
    # Build step `collectstatic` should not require a live database URL.
    if IS_PRODUCTION_RUNTIME and not IS_COLLECTSTATIC:
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
    if sqlite_name and sqlite_name != ':memory:' and os.path.exists(sqlite_name) and not IS_COLLECTSTATIC:
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
    db_options.setdefault('connect_timeout', int(os.getenv('DB_CONNECT_TIMEOUT', '10')))
    db_options.setdefault('keepalives', 1)
    db_options.setdefault('keepalives_idle', 30)
    db_options.setdefault('keepalives_interval', 10)
    db_options.setdefault('keepalives_count', 5)
    if IS_PRODUCTION_RUNTIME:
        db_options.setdefault('sslmode', 'require')

    # Supabase's transaction pooler (port 6543) may run each transaction on
    # another server connection, so a server-side cursor (QuerySet.iterator())
    # cannot be read past its transaction: Django's documented setting for
    # transaction pooling. DB_DISABLE_SERVER_SIDE_CURSORS=true/false overrides
    # the detection (crack_cms/db_config.py).
    if server_side_cursors_unsupported(DATABASES['default'], os.getenv('DB_DISABLE_SERVER_SIDE_CURSORS')):
        DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

    # Opt-in server-side statement timeout (DB_STATEMENT_TIMEOUT_MS, e.g.
    # 15000 on the web service): without it a runaway query keeps its
    # backend and the request thread busy until it finishes. Off by default
    # (crack_cms/db_config.py says where to set it).
    _statement_timeout = statement_timeout_option(os.getenv('DB_STATEMENT_TIMEOUT_MS'))
    if _statement_timeout:
        db_options['options'] = f"{db_options.get('options', '')} {_statement_timeout}".strip()

    force_ipv4_default = 'true' if IS_PRODUCTION_RUNTIME else 'false'
    force_ipv4 = os.getenv('DB_FORCE_IPV4', force_ipv4_default).lower() == 'true'
    if force_ipv4:
        db_host = (DATABASES['default'].get('HOST') or urlparse(DATABASE_URL).hostname or '').strip()
        db_hostaddr = _resolve_ipv4_address(db_host)
        if db_hostaddr:
            # Keep HOST for TLS/SNI while forcing TCP connect via IPv4 address.
            db_options.setdefault('hostaddr', db_hostaddr)

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

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
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

# Client IP behind proxies. DRF's throttles key anonymous traffic on the
# client IP; without NUM_PROXIES DRF uses the whole, client-controlled
# X-Forwarded-For string, so a new prefix per request is a new throttle
# bucket. Set NUM_PROXIES to the number of proxies in front of Django that
# append to X-Forwarded-For (DRF then takes that entry from the right).
# Unset keeps DRF's historical behaviour. The question-bank limiter
# (questions/middleware.py, via crack_cms/client_ip.py) reads the same value
# and falls back to REMOTE_ADDR while it is unset. TRUSTED_CLIENT_IP_HEADER
# (e.g. "CF-Connecting-IP", "DO-Connecting-IP") is honoured by that limiter
# only; set it only when every request reaches Django through that edge.
#
# Production (both default to unset; see backend/.env.example): behind the
# DigitalOcean / Cloudflare edge REMOTE_ADDR is the proxy, shared by every
# visitor, so until one of them is set the limiter counts all anonymous
# traffic -- and the first request of every new or refreshed login token --
# in that proxy's bucket (security_posture_check logs a warning).
#   1. Look at what the edge sends: as an admin, GET /api/health/client-ip/
#      echoes REMOTE_ADDR, X-Forwarded-For and the platform client-IP
#      headers of your own request (crack_cms/diagnostics.py).
#   2. TRUSTED_CLIENT_IP_HEADER=DO-Connecting-IP on DigitalOcean App
#      Platform: DO's own edge sets it on every request. Do not use
#      CF-Connecting-IP there -- the default *.ondigitalocean.app hostname
#      stays reachable around Cloudflare, and a client can send that header
#      itself. Verify before relying on it: send a forged
#      CF-Connecting-IP / DO-Connecting-IP to /api/health/client-ip/ and
#      check which value reaches Django.
#   3. NUM_PROXIES=<n> where X-Forwarded-For ends with your address followed
#      by n-1 proxy addresses (usually 1). DRF's throttles read only this
#      one, so set it as well -- TRUSTED_CLIENT_IP_HEADER alone leaves DRF
#      keying on the raw X-Forwarded-For (security_posture_check warns).
NUM_PROXIES = parse_num_proxies(os.getenv('NUM_PROXIES'))
TRUSTED_CLIENT_IP_HEADER = os.getenv('TRUSTED_CLIENT_IP_HEADER', '').strip()
# The one edge country header analytics ingest trusts
# (analytics/views_internal.py), e.g. CF-IPCountry or X-Vercel-IP-Country;
# 'none' stores no country. Unset: the country header of the edge
# TRUSTED_CLIENT_IP_HEADER names, otherwise CF-IPCountry.
ANALYTICS_COUNTRY_HEADER = os.getenv('ANALYTICS_COUNTRY_HEADER', '').strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


# Question-bank limiter (questions/middleware.py): GETs under /api/questions/
# per user (or per client IP when anonymous) per window. One student in rapid
# revision issues about 12 GETs per question; 0 disables the limiter.
QUESTION_BANK_RATE_LIMIT = _env_int('QUESTION_BANK_RATE_LIMIT', 300)
QUESTION_BANK_RATE_WINDOW = _env_int('QUESTION_BANK_RATE_WINDOW', 60)

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.supabase_rest_auth.SupabaseJWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        # DRF's SearchFilter with a cap on the number / length of terms.
        'crack_cms.filters.BoundedSearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    # Honours ?page_size= (max 100); default page size stays 20.
    'DEFAULT_PAGINATION_CLASS': 'crack_cms.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'NUM_PROXIES': NUM_PROXIES,
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('DRF_THROTTLE_ANON', '120/min'),
        'user': os.getenv('DRF_THROTTLE_USER', '600/min'),
        'admin_control_tower': os.getenv('DRF_THROTTLE_ADMIN_CONTROL_TOWER', '180/min'),
        # Scoped rates for expensive / sensitive endpoints.
        'ai_tutor': os.getenv('DRF_THROTTLE_AI_TUTOR', '30/min'),
        'password_reset': os.getenv('DRF_THROTTLE_PASSWORD_RESET', '5/min'),
        'token_purchase': os.getenv('DRF_THROTTLE_TOKEN_PURCHASE', '10/min'),
        'subscription_order': os.getenv('DRF_THROTTLE_SUBSCRIPTION_ORDER', '15/min'),
        # GET endpoints that auto-expire subs and run DB writes — must not
        # be abusable for DoS. 60/min is generous for real users (mobile + web)
        # but blocks scripted loops. See accounts.views.SubscriptionStatusView.
        'subscription_status': os.getenv('DRF_THROTTLE_SUBSCRIPTION_STATUS', '60/min'),
        'contact_us': os.getenv('DRF_THROTTLE_CONTACT_US', '5/min'),
        # Every `throttle_scope` used by a view MUST have a rate here --
        # ScopedRateThrottle raises ImproperlyConfigured (HTTP 500) for an
        # unknown scope on every request to that view.
        'ai_heavy': os.getenv('DRF_THROTTLE_AI_HEAVY', '5/min'),
        'analytics_ingest': os.getenv('DRF_THROTTLE_ANALYTICS_INGEST', '120/min'),
        'local_auth': os.getenv('DRF_THROTTLE_LOCAL_AUTH', '60/min'),
        # analytics/views.py FeedbackSubmitThrottle / ContactHourlyThrottle
        # (same defaults as their built-in fallbacks; listed to be tunable).
        'feedback_submit': os.getenv('DRF_THROTTLE_FEEDBACK_SUBMIT', '10/hour'),
        'contact_us_hourly': os.getenv('DRF_THROTTLE_CONTACT_US_HOURLY', '20/hour'),
    },
}

# Dev-only local email/password auth (accounts/local_auth.py) for running the
# stack without Supabase. Hard-disabled unless DEBUG is on, so a stray
# LOCAL_DEV_AUTH=1 in a production environment has no effect.
_local_dev_auth_requested = os.getenv('LOCAL_DEV_AUTH', '').strip().lower() in ('1', 'true', 'yes')
LOCAL_DEV_AUTH = bool(DEBUG and _local_dev_auth_requested)
if _local_dev_auth_requested and not DEBUG:
    print('WARNING: LOCAL_DEV_AUTH ignored because DEBUG is off.', file=sys.stderr)
# Local mock payment provider (accounts/payments_mock.py): no network, no
# money. Like LOCAL_DEV_AUTH it is hard-disabled unless DEBUG is on.
_payments_mock_requested = os.getenv('PAYMENTS_MODE', '').strip().lower() == 'mock'
PAYMENTS_MOCK = bool(DEBUG and _payments_mock_requested)
if _payments_mock_requested and not DEBUG:
    print('WARNING: PAYMENTS_MODE=mock ignored because DEBUG is off.', file=sys.stderr)
if LOCAL_DEV_AUTH:
    REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = (
        *REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'],
        'accounts.local_auth_authentication.LocalDevJWTAuthentication',
    )

# SimpleJWT — refresh rotation + blacklist after rotation.
# These apply to the DRF-issued JWT fallback only (Supabase users go through
# SupabaseJWTAuthentication which has its own refresh handling). Today that
# is only the dev-only local refresh endpoint (accounts/local_auth.py).
# Blacklisting needs the 'rest_framework_simplejwt.token_blacklist' app (and
# its tables); it is not installed, so SimpleJWT silently skipped the
# blacklist and rotated refresh tokens stayed valid until expiry. The flag
# now reflects that: it can only be on when the app is installed.
_JWT_BLACKLIST_APP_INSTALLED = 'rest_framework_simplejwt.token_blacklist' in INSTALLED_APPS
SIMPLE_JWT = {
    'ROTATE_REFRESH_TOKENS': os.getenv('JWT_ROTATE_REFRESH_TOKENS', 'true').lower() == 'true',
    'BLACKLIST_AFTER_ROTATION': (
        _JWT_BLACKLIST_APP_INSTALLED
        and os.getenv('JWT_BLACKLIST_AFTER_ROTATION', 'true').lower() == 'true'
    ),
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME_MIN', '15'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME_DAYS', '7'))),
}

# Upload hardening — cap body size to 10 MB to prevent DoS via giant payloads.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('DATA_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('FILE_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024))

def _normalize_origin(value: str) -> str:
    """Return canonical origin (scheme://host[:port]) or empty string for invalid inputs."""
    if not value:
        return ''

    cleaned = value.strip().strip('"\'[]()')
    if not cleaned:
        return ''

    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return ''

    # Origins must not include path/query/fragment. Normalize a trailing '/'.
    if parsed.path not in ('', '/') or parsed.params or parsed.query or parsed.fragment:
        return ''

    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_origin_list(value: str) -> list[str]:
    if not value:
        return []

    origins: list[str] = []
    for item in re.split(r'[;,\n]+', value):
        normalized = _normalize_origin(item)
        if normalized and normalized not in origins:
            origins.append(normalized)
    return origins


def _append_unique(items: list[str], value: str) -> list[str]:
    normalized = _normalize_origin(value)
    if normalized and normalized not in items:
        items.append(normalized)
    return items


def _sync_www_variant(items: list[str], base_url: str) -> None:
    """If base_url is a bare domain, also allow its www variant (and vice-versa)."""
    parsed = urlparse(base_url)
    host = parsed.hostname or ''
    if '.' not in host:
        return
    if host.startswith('www.'):
        alt = f"{parsed.scheme}://{host[4:]}"
    else:
        alt = f"{parsed.scheme}://www.{host}"
    _append_unique(items, alt)


# Used only to keep CORS/CSRF checks aligned with the frontend origin; defaults to empty.
cors_frontend_url = os.getenv('FRONTEND_URL', '').strip()

# CORS
cors_allowed_origins = _parse_origin_list(
    os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000',
    )
)
if cors_frontend_url:
    _append_unique(cors_allowed_origins, cors_frontend_url)
    # Also allow the www subdomain if FRONTEND_URL is the bare domain (and vice-versa)
    _sync_www_variant(cors_allowed_origins, cors_frontend_url)
CORS_ALLOWED_ORIGINS = cors_allowed_origins
CORS_ALLOW_CREDENTIALS = True

from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-session-id",
    # Optimistic locking: the admin question editor (and QuestionImage
    # PATCH/DELETE) send If-Match: <updated_at>. Without it in the allow-list
    # the cross-origin preflight fails and the save never reaches the API.
    "if-match",
]
# Response headers cross-origin JavaScript may read. The question-bank
# limiter's 429 carries Retry-After, and the bank's automatic retry waits
# that long; without exposing it the browser hides the header and the client
# fell back to a fixed 5 s.
CORS_EXPOSE_HEADERS = ["Retry-After"]
CORS_MAX_AGE = 86400  # 24 hours — browsers cache preflight responses

# CSRF trusted origins (needed for production)
csrf_trusted_origins = _parse_origin_list(
    os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000',
    )
)
if cors_frontend_url:
    _append_unique(csrf_trusted_origins, cors_frontend_url)
    _sync_www_variant(csrf_trusted_origins, cors_frontend_url)
CSRF_TRUSTED_ORIGINS = csrf_trusted_origins

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static & Media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT').strip()) if os.getenv('MEDIA_ROOT', '').strip() else BASE_DIR / 'media'
# Optional local mirror of the Supabase Storage buckets (an extracted
# storage backup: <dir>/<bucket>/<path>). When set, question images whose
# URL points at Supabase public storage are streamed from disk instead of
# redirecting to Supabase. Unset in production.
SUPABASE_STORAGE_MIRROR_DIR = os.getenv('SUPABASE_STORAGE_MIRROR_DIR', '').strip()

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

# Explicit override (local dev uses the file backend so mail is captured to
# disk and never sent).
if os.getenv('EMAIL_BACKEND', '').strip():
    EMAIL_BACKEND = os.getenv('EMAIL_BACKEND').strip()
    EMAIL_FILE_PATH = os.getenv('EMAIL_FILE_PATH', str(BASE_DIR / 'tmp_mail'))

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', f'CrackCMS <{EMAIL_HOST_USER}>')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '20'))
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
# Recipient of feedback / contact-form notifications (analytics/views.py,
# which falls back to its built-in address when this is empty).
ADMIN_NOTIFICATION_EMAIL = os.getenv('ADMIN_NOTIFICATION_EMAIL', '').strip()

# ── Leaderboard gating ──────────────────────────────────────────────
# Number of real (non-admin) users with weekly activity before the global
# /leaderboard exposes a top-10 ranking slab. Below the threshold the page
# renders a personal-stats dashboard instead (no global rows are shown).
# Tune via env var without code change.
LEADERBOARD_LIVE_THRESHOLD = int(os.getenv('LEADERBOARD_LIVE_THRESHOLD', '50'))

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

# Cap the number of chunks scanned per RAG query to keep memory bounded
# on small Render instances (free tier 512MB RAM). Reduce further via
# `RAG_MAX_SEARCH_CHUNKS=500` if you see OOM kills under heavy load.
try:
    RAG_MAX_SEARCH_CHUNKS = int(os.getenv('RAG_MAX_SEARCH_CHUNKS', '2000'))
except (TypeError, ValueError):
    RAG_MAX_SEARCH_CHUNKS = 2000

# ── Cache Configuration ─────────────────────────────────────────────
# Uses Redis if REDIS_URL is set AND valid, otherwise falls back to
# local memory cache. The redis:// / rediss:// check prevents a crash
# in django_redis when the env var is set to a bare hostname or empty
# placeholder (which happened on DigitalOcean App Platform).
REDIS_URL = os.getenv('REDIS_URL', '').strip()
_redis_url_valid = REDIS_URL and REDIS_URL.startswith(('redis://', 'rediss://', 'unix://'))

# 'rate_limit' holds the question-bank limiter's counters and token -> user
# mappings (questions/middleware.py). On LocMemCache the 'default' alias keeps
# Django's 300-entry cap and is shared with the question-list caches, so under
# load culling evicted token mappings (students fell back to the shared IP
# bucket) as well as cached data. Without Redis each process still counts on
# its own (a per-worker budget).
_RATE_LIMIT_CACHE_MAX_ENTRIES = _env_int('RATE_LIMIT_CACHE_MAX_ENTRIES', 50000)

if _redis_url_valid:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,   # don't crash if Redis goes down
            },
            'TIMEOUT': 86400,  # 24 hours default
        },
        # Dedicated cache for KB retrieval so it doesn't share quota
        # with sessions / generic view cache.
        'kb_retrieval': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,
            },
            'TIMEOUT': 3600,
        },
        'rate_limit': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'rl',
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,   # limiter fails open
            },
            'TIMEOUT': 300,
        },
    }
else:
    if REDIS_URL:
        import logging as _logging
        _logging.getLogger('django').warning(
            'REDIS_URL is set (%r) but does not start with redis://, '
            'rediss://, or unix://. Falling back to LocMemCache.',
            REDIS_URL[:40],
        )
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'crackcms-cache',
        },
        'kb_retrieval': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'crackcms-kb',
        },
        'rate_limit': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'crackcms-rate-limit',
            'OPTIONS': {'MAX_ENTRIES': _RATE_LIMIT_CACHE_MAX_ENTRIES},
        },
    }
    if _TEST_RUN:
        # Same in-process store as 'default' (separate alias, larger cap), so
        # the cache.clear() calls in test setUp keep resetting limiter buckets
        # as they did when the limiter used 'default'; otherwise every
        # question-bank GET of the whole suite would count in one long-lived
        # 127.0.0.1 bucket.
        CACHES['rate_limit']['LOCATION'] = CACHES['default']['LOCATION']

# ── Knowledge Base ──────────────────────────────────────────────────────
KB_FALLBACK_THRESHOLD = int(os.getenv('KB_FALLBACK_THRESHOLD', '10'))
KB_DEFAULT_TOP_K = int(os.getenv('KB_DEFAULT_TOP_K', '8'))
KB_USE_RERANK = os.getenv('KB_USE_RERANK', 'true').lower() == 'true'
KB_USE_KG_BOOST = os.getenv('KB_USE_KG_BOOST', 'true').lower() == 'true'

# Embedding
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'bge-small-en-v1.5')
NCBI_API_KEY = os.getenv('NCBI_API_KEY', '')

# ── Security Hardening ──────────────────────────────────────────────
# Browser-level protections against common web vulnerabilities (OWASP).
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

if not DEBUG:
    # Production-only TLS enforcement
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Not inside the test runner: CI runs the suite with DEBUG=False and the
    # test client speaks plain HTTP, so every API test got a 301 instead of
    # its real response (the CI backend job could never pass).
    SECURE_SSL_REDIRECT = (
        not is_testing
        and os.getenv('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
    )
    # Cloudflare + Railway terminate TLS at the edge; trust X-Forwarded-Proto
    # so SecurityMiddleware knows requests are already HTTPS and doesn't loop.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Django Q2 Configuration
Q_CLUSTER = {
    'name': 'crack_cms_q',
    'workers': 4,
    'recycle': 500,
    'timeout': 3600,
    'retry': 3660,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'orm': 'default',
    # A task that raises or is killed at the timeout is never acknowledged
    # (ack_failures is off), so the ORM broker re-presents it every 'retry'
    # seconds; django-q2's default 0 means for ever. Ingestion and the recall
    # importers treat a re-delivery as a no-op or mark the job failed; this
    # bounds every other task (video_engine.tasks, questions.tasks).
    'max_attempts': 3,
}

# Ingestion stale-job recovery (ingestion/schedules.py, orchestrator.py):
# minutes between the scheduled recovery passes (0 removes the schedule) and
# how often one job is re-queued automatically after losing its worker.
INGESTION_RECOVERY_SCHEDULE_MINUTES = _env_int('INGESTION_RECOVERY_SCHEDULE_MINUTES', 10)
INGESTION_MAX_AUTO_RESUMES = _env_int('INGESTION_MAX_AUTO_RESUMES', 2)

