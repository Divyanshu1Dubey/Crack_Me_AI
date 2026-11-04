"""Backend performance probe: query counts, SQL time and latency per endpoint.

Run from backend/ against the LOCAL restored PostgreSQL database only:

    DJANGO_ENV_FILE=.env.localdev python -m ai_eval.perf_probe --label before --runs 7
    DJANGO_ENV_FILE=.env.localdev python -m ai_eval.perf_probe --label before-rtt20 --rtt-ms 20 --runs 2
    python -m ai_eval.perf_probe --compare ../docs/audit/perf/backend_before.json \
        ../docs/audit/perf/backend_after.json --out ../docs/audit/perf/compare.md

Output: ``<out>/backend_<label>.json`` and ``.md`` (default out: ../docs/audit/perf).

Guards (the probe refuses to run otherwise):

* ``DJANGO_ENV_FILE`` must name ``.env.localdev`` (checked before Django loads
  any env file, so ``backend/.env`` is never read) and ``DEBUG`` must be on;
* the database must be PostgreSQL named ``crack_local`` on 127.0.0.1 / ::1 /
  localhost (``crack_restore``, the pristine restore, is refused);
* every cache alias must be LocMem (per process, nothing outlives the probe);
* ``AI_OFFLINE_MODE`` must be on (no LLM call);
* outbound connections to anything but loopback are refused (socket guard).

Every request runs inside ``transaction.atomic()`` and is rolled back, together
with the per-run setup (seed-user auth state, the probe's test papers, the
attempt a /submit/ or /review/ needs). ``transaction.on_commit`` callbacks
(mail threads, task queueing) therefore never run.

Measurement:

* Auth mode ``supabase`` (default): the real ``SupabaseJWTAuthentication``
  with ``_fetch_supabase_user`` patched to return a canned GoTrue user, so
  the per-request auth DB work (user lookup, token wallet, device checks) is
  counted; ``--gotrue-ms N`` sleeps N ms on a verification-cache miss. The
  seed users' device row and ``last_seen`` are primed before each request
  (steady state: a known device, no once-per-minute touch). Mode ``force``
  uses ``APIClient.force_authenticate`` to isolate the view cost.
* Per request: SQL statements executed (incl. SAVEPOINT / RELEASE: the
  request's own ``atomic()`` blocks nest inside the probe's transaction, where
  production pays BEGIN / COMMIT round trips the driver issues outside
  ``cursor.execute``), writes, distinct normalised templates, duplicate
  executions of one template (N+1 signal), SQL time, wall time, status, raw
  and gzip-6 bytes.
* ``cold`` runs clear every Django cache (and the GoTrue emulation) first;
  ``warm`` runs follow one priming request and keep the caches. Process-level
  state (imports, the BM25 index) is warmed by one discarded pass first; its
  wall time is reported as ``first_ms``.
* ``--rtt-ms R`` sleeps R ms per executed statement (round-trip emulation of
  the app <-> database distance). It does not add BEGIN / COMMIT / TLS / GoTrue
  / CORS / edge time, so it underestimates production latency.
* DRF throttles and the question-bank limiter still run but never block (the
  probe sends hundreds of requests a minute). ``DEBUG=True`` adds debug-cursor
  overhead to wall times; query counts are unaffected.

Seed users (``manage.py seed_local_dev_users``): student / premium / admin; no
personal data is printed (labels and counts only).
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import math
import os
import re
import statistics
import sys
import time
import uuid
from collections import Counter

LOCAL_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})
LOCAL_DB_NAME = 'crack_local'
PRISTINE_DB_NAME = 'crack_restore'
ENV_FILE_NAME = '.env.localdev'
SEED_EMAILS = {
    'student': 'student@local.test',
    'premium': 'premium@local.test',
    'admin': 'admin@local.test',
}
PROBE_UA = 'crack-perf-probe/1.0'
PROBE_IP = '127.0.0.1'
_TRUE = ('1', 'true', 'yes', 'on')


# ─── guards (pure functions, unit-tested) ─────────────────────────────

def env_refusal(environ) -> str | None:
    """Why the probe must not start in this environment (None: it may)."""
    env_file = (environ.get('DJANGO_ENV_FILE') or '').strip()
    if os.path.basename(env_file.replace('\\', '/')) != ENV_FILE_NAME:
        return f'Refusing: set DJANGO_ENV_FILE={ENV_FILE_NAME} (the local restored database).'
    if (environ.get('AI_OFFLINE_MODE') or '').strip().lower() not in _TRUE and environ.get('AI_OFFLINE_MODE') is not None:
        return 'Refusing: AI_OFFLINE_MODE is off (the probe never calls an LLM).'
    return None


def database_refusal(db: dict, debug: bool) -> str | None:
    """Why ``db`` (a settings.DATABASES entry) must not be probed (None: it may)."""
    if not debug:
        return 'Refusing: DEBUG is off (the probe is a local development tool).'
    engine = str(db.get('ENGINE') or '')
    if 'postgresql' not in engine:
        return f'Refusing: database engine {engine!r} is not PostgreSQL (the local restore).'
    host = str(db.get('HOST') or '').strip()
    if host not in LOCAL_HOSTS:
        return f'Refusing: database host {host!r} is not local.'
    name = str(db.get('NAME') or '')
    if name == PRISTINE_DB_NAME:
        return f'Refusing: {PRISTINE_DB_NAME} is the pristine restore and is never used.'
    if name != LOCAL_DB_NAME:
        return f'Refusing: database {name!r} is not {LOCAL_DB_NAME}.'
    return None


def cache_refusal(caches_setting: dict) -> str | None:
    for alias, conf in (caches_setting or {}).items():
        backend = str((conf or {}).get('BACKEND') or '')
        if not backend.endswith('LocMemCache'):
            return f'Refusing: cache {alias!r} uses {backend!r}; the probe needs per-process LocMem caches.'
    return None


# ─── SQL helpers (pure, unit-tested) ──────────────────────────────────

_WS = re.compile(r'\s+')
_STR = re.compile(r"'(?:[^']|'')*'")
_IN_LIST = re.compile(r'IN \((?:%s(?:, )?)+\)')
_VALUES_LIST = re.compile(r'VALUES (?:\((?:%s(?:, )?)+\)(?:, )?)+')
_NUM = re.compile(r'\b\d+\b')
_SAVEPOINT = re.compile(r'^(SAVEPOINT|RELEASE SAVEPOINT|ROLLBACK TO SAVEPOINT)\s+\S+', re.IGNORECASE)


def sql_template(sql: str) -> str:
    """``sql`` with literals, IN / VALUES lists and savepoint names folded."""
    text = _WS.sub(' ', (sql or '').strip())
    text = _SAVEPOINT.sub(lambda m: m.group(1).upper() + ' <sp>', text)
    text = _STR.sub("'?'", text)
    text = _IN_LIST.sub('IN (...)', text)
    text = _VALUES_LIST.sub('VALUES (...)', text)
    return _NUM.sub('N', text)


def sql_kind(sql: str) -> str:
    head = (sql or '').lstrip()[:24].upper()
    for kind in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'RELEASE SAVEPOINT', 'ROLLBACK TO SAVEPOINT', 'SAVEPOINT'):
        if head.startswith(kind):
            return {'RELEASE SAVEPOINT': 'savepoint', 'ROLLBACK TO SAVEPOINT': 'savepoint', 'SAVEPOINT': 'savepoint'}.get(kind, kind.lower())
    if head.startswith('WITH'):
        return 'select'
    return 'other'


def summarize_statements(rows) -> dict:
    """``rows``: [(sql, seconds)] of one request -> counts and N+1 signals."""
    kinds = Counter(sql_kind(sql) for sql, _ in rows)
    templates = Counter(sql_template(sql) for sql, _ in rows if sql_kind(sql) != 'savepoint')
    statements = sum(templates.values())
    top = [
        {'count': n, 'sql': tpl[:220]}
        for tpl, n in templates.most_common(5) if n > 1
    ]
    return {
        'queries': len(rows),
        'statements': statements,
        'savepoints': kinds.get('savepoint', 0),
        'writes': kinds.get('insert', 0) + kinds.get('update', 0) + kinds.get('delete', 0),
        'templates': len(templates),
        'duplicates': statements - len(templates),
        'sql_ms': round(sum(seconds for _, seconds in rows) * 1000.0, 2),
        'top_duplicates': top,
    }


def percentile(values, pct: float):
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    rank = max(1, math.ceil(pct / 100.0 * len(data)))
    return data[min(rank, len(data)) - 1]


def aggregate_runs(runs: list[dict]) -> dict:
    """Per-phase summary of several runs of one endpoint."""
    if not runs:
        return {}
    statuses = Counter(r['status'] for r in runs)
    queries = [r['queries'] for r in runs]
    walls = [r['wall_ms'] for r in runs]
    out = {
        'runs': len(runs),
        'status': statuses.most_common(1)[0][0],
        'statuses': dict(statuses),
        'queries': int(statistics.median(queries)),
        'queries_min': min(queries),
        'queries_max': max(queries),
        'statements': int(statistics.median(r['statements'] for r in runs)),
        'writes': int(statistics.median(r['writes'] for r in runs)),
        'savepoints': int(statistics.median(r['savepoints'] for r in runs)),
        'templates': int(statistics.median(r['templates'] for r in runs)),
        'duplicates': int(statistics.median(r['duplicates'] for r in runs)),
        'sql_ms': round(statistics.median(r['sql_ms'] for r in runs), 2),
        'wall_p50_ms': round(percentile(walls, 50), 1),
        'wall_p95_ms': round(percentile(walls, 95), 1),
        'bytes': int(statistics.median(r['bytes'] for r in runs)),
        'gzip_bytes': int(statistics.median(r['gzip_bytes'] for r in runs)),
        'top_duplicates': runs[-1].get('top_duplicates', []),
    }
    codes = [r.get('error_code') for r in runs if r.get('error_code')]
    if codes:
        out['error_code'] = Counter(codes).most_common(1)[0][0]
    return out


# Critical-path flows: stages run one after the other; the endpoints of a
# stage are fired in parallel by the frontend.
FLOWS = [
    ('dashboard (student)', [
        [('auth.profile', 'student')],
        [('dashboard.bundle', 'student'), ('questions.stats', 'student'), ('auth.tokens', 'student'),
         ('analytics.announcements', 'student')],
    ]),
    ('bank question open (premium)', [
        [('questions.detail', 'premium'), ('questions.similar', 'premium'), ('questions.discussions', 'premium')],
    ]),
    ('practice answer + reveal (premium)', [
        [('questions.attempt', 'premium')],
        [('ai.why_correct', 'premium'), ('ai.clinical', 'premium'), ('ai.mnemonic', 'premium'),
         ('ai.exam_importance', 'premium'), ('ai.concept', 'premium'), ('ai.why_incorrect', 'premium'),
         ('ai.related_pyqs', 'premium'), ('ai.related_topics', 'premium')],
    ]),
    ('test submit + review, 120 questions (premium)', [
        [('tests.submit', 'premium')],
        [('tests.review', 'premium')],
    ]),
]


def compute_flows(endpoints: list[dict], phase: str = 'warm') -> list[dict]:
    index = {(e['key'], e['user']): e for e in endpoints}
    flows = []
    for name, stages in FLOWS:
        total_q = critical_q = 0
        critical_ms = 0.0
        missing = []
        requests = 0
        for stage in stages:
            stage_q, stage_ms = [], []
            for key in stage:
                entry = index.get(key)
                data = ((entry or {}).get('phases') or {}).get(phase) or ((entry or {}).get('phases') or {}).get('cold')
                if not data:
                    missing.append('%s/%s' % key)
                    continue
                requests += 1
                stage_q.append(data['queries'])
                stage_ms.append(data['wall_p50_ms'])
            total_q += sum(stage_q)
            critical_q += max(stage_q or [0])
            critical_ms += max(stage_ms or [0.0])
        flows.append({
            'flow': name, 'phase': phase, 'requests': requests, 'total_queries': total_q,
            'critical_path_queries': critical_q, 'critical_path_ms': round(critical_ms, 1),
            'missing': missing,
        })
    return flows


# ─── report rendering (pure) ──────────────────────────────────────────

def _cell(value, default='-'):
    return default if value is None else value


def render_markdown(report: dict) -> str:
    cfg = report.get('config', {})
    lines = [
        f"# Backend perf probe: {report.get('label')}",
        '',
        f"Generated {report.get('generated_at')} on `{cfg.get('db', {}).get('name')}` "
        f"(PostgreSQL {cfg.get('db', {}).get('server_version', '?')}, {cfg.get('db', {}).get('host')}), "
        f"auth `{cfg.get('auth')}`, runs {cfg.get('runs')}, rtt {cfg.get('rtt_ms')} ms/statement, "
        f"GoTrue {cfg.get('gotrue_ms')} ms/miss. Queries = statements executed incl. SAVEPOINT/RELEASE; "
        'dup = repeated executions of one statement template; times in ms (p50/p95 over the runs).',
        '',
        '| endpoint | user | status | q cold | q warm | writes | dup | SQL ms | wall cold p50/p95 | wall warm p50/p95 | KB gz |',
        '|---|---|---|---|---|---|---|---|---|---|---|',
    ]
    for e in report.get('endpoints', []):
        cold = e['phases'].get('cold') or {}
        warm = e['phases'].get('warm') or {}
        main = warm or cold
        status = main.get('status')
        if main.get('error_code'):
            status = f"{status} {main['error_code']}"
        lines.append(
            f"| `{e['method']} {e['path']}` | {e['user']} | {_cell(status)} | {_cell(cold.get('queries'))} | "
            f"{_cell(warm.get('queries'))} | {_cell(main.get('writes'))} | {_cell(main.get('duplicates'))} | "
            f"{_cell(main.get('sql_ms'))} | {_cell(cold.get('wall_p50_ms'))}/{_cell(cold.get('wall_p95_ms'))} | "
            f"{_cell(warm.get('wall_p50_ms'))}/{_cell(warm.get('wall_p95_ms'))} | "
            f"{round((main.get('gzip_bytes') or 0) / 1024, 1)} |"
        )
    lines += ['', '## Flows (critical path: stages in sequence, a stage\'s requests in parallel)', '',
              '| flow | phase | requests | total queries | critical-path queries | critical-path ms |',
              '|---|---|---|---|---|---|']
    for f in report.get('flows', []):
        lines.append(f"| {f['flow']} | {f['phase']} | {f['requests']} | {f['total_queries']} | "
                     f"{f['critical_path_queries']} | {f['critical_path_ms']} |")
    boot = report.get('boot') or {}
    if boot:
        lines += ['', '## Boot work', '']
        for name, value in boot.items():
            lines.append(f'* `{name}`: {value}')
    lines += ['', '## Repeated statements (top duplicate templates, warm)', '']
    for e in report.get('endpoints', []):
        main = e['phases'].get('warm') or e['phases'].get('cold') or {}
        dups = [d for d in main.get('top_duplicates') or [] if d['count'] > 2]
        if dups:
            lines.append(f"* `{e['key']}` ({e['user']}): " + '; '.join(
                f"{d['count']}x `{d['sql'][:120]}`" for d in dups[:3]))
    lines.append('')
    return '\n'.join(lines)


def render_comparison(before: dict, after: dict) -> str:
    b_index = {(e['key'], e['user']): e for e in before.get('endpoints', [])}
    lines = [
        f"# Perf probe comparison: {before.get('label')} -> {after.get('label')}",
        '',
        '| endpoint | user | queries cold | queries warm | dup warm | SQL ms warm | wall warm p50 ms |',
        '|---|---|---|---|---|---|---|',
    ]

    def pair(b, a, field):
        bv = (b or {}).get(field)
        av = (a or {}).get(field)
        if bv is None and av is None:
            return '-'
        return f'{_cell(bv)} -> {_cell(av)}'

    for e in after.get('endpoints', []):
        b = b_index.get((e['key'], e['user']))
        bp = (b or {}).get('phases', {})
        ap = e.get('phases', {})
        lines.append(
            f"| `{e['key']}` | {e['user']} | {pair(bp.get('cold'), ap.get('cold'), 'queries')} | "
            f"{pair(bp.get('warm'), ap.get('warm'), 'queries')} | {pair(bp.get('warm'), ap.get('warm'), 'duplicates')} | "
            f"{pair(bp.get('warm'), ap.get('warm'), 'sql_ms')} | {pair(bp.get('warm'), ap.get('warm'), 'wall_p50_ms')} |"
        )
    b_flows = {(f['flow'], f['phase']): f for f in before.get('flows', [])}
    lines += ['', '| flow | phase | total queries | critical-path queries | critical-path ms |', '|---|---|---|---|---|']
    for f in after.get('flows', []):
        b = b_flows.get((f['flow'], f['phase'])) or {}
        lines.append(
            f"| {f['flow']} | {f['phase']} | {_cell(b.get('total_queries'))} -> {f['total_queries']} | "
            f"{_cell(b.get('critical_path_queries'))} -> {f['critical_path_queries']} | "
            f"{_cell(b.get('critical_path_ms'))} -> {f['critical_path_ms']} |"
        )
    lines.append('')
    return '\n'.join(lines)


# ─── runtime (needs Django) ───────────────────────────────────────────

class StatementRecorder:
    """connection.execute_wrapper: times statements (and sleeps --rtt-ms)."""

    def __init__(self, rtt_ms: float = 0.0):
        self.rtt = max(0.0, float(rtt_ms or 0)) / 1000.0
        self.active = False
        self.rows: list[tuple[str, float]] = []

    def start(self):
        self.rows = []
        self.active = True

    def stop(self):
        self.active = False
        return self.rows

    def __call__(self, execute, sql, params, many, context):
        if not self.active:
            return execute(sql, params, many, context)
        if self.rtt:
            time.sleep(self.rtt)
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.rows.append((sql, time.perf_counter() - started))


def install_network_guard():
    """Refuse outbound connections to anything but loopback."""
    import socket

    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def _allowed(address):
        host = address[0] if isinstance(address, tuple) and address else address
        if not isinstance(host, str):
            return True
        return host in LOCAL_HOSTS or host.startswith('127.')

    def connect(self, address):
        if not _allowed(address):
            raise OSError(f'perf_probe: outbound connection to {address!r} blocked')
        return original(self, address)

    def connect_ex(self, address):
        if not _allowed(address):
            raise OSError(f'perf_probe: outbound connection to {address!r} blocked')
        return original_ex(self, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex


def install_non_blocking_throttles():
    """Throttles and the question-bank limiter keep their bookkeeping but never answer 429."""
    from django.conf import settings
    from rest_framework import exceptions
    from rest_framework.views import APIView

    original = APIView.check_throttles

    def check_throttles(self, request):
        try:
            original(self, request)
        except exceptions.Throttled:
            pass

    APIView.check_throttles = check_throttles
    settings.QUESTION_BANK_RATE_LIMIT = 10 ** 9


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).decode().rstrip('=')


class ProbeAuth:
    """Canned GoTrue identities for the seed users (mode ``supabase``)."""

    def __init__(self, gotrue_ms: float = 0.0):
        self.gotrue_s = max(0.0, float(gotrue_ms or 0)) / 1000.0
        self.users: dict[str, dict] = {}     # token -> GoTrue user payload
        self.seen: set[str] = set()          # verification-cache emulation
        self.installed = False
        self.gotrue_calls = 0

    def identity(self, user) -> dict:
        uid = (user.supabase_uid or '').strip() or str(uuid.uuid5(uuid.NAMESPACE_URL, f'crack-perf-probe:user:{user.pk}'))
        session = str(uuid.uuid5(uuid.NAMESPACE_URL, f'crack-perf-probe:session:{user.pk}'))
        device = str(uuid.uuid5(uuid.NAMESPACE_URL, f'crack-perf-probe:device:{user.pk}'))
        token = '.'.join([
            _b64({'alg': 'HS256', 'typ': 'JWT'}),
            _b64({'sub': uid, 'session_id': session, 'exp': int(time.time()) + 6 * 3600,
                  'role': 'authenticated', 'aud': 'authenticated'}),
            'perf-probe-signature',
        ])
        self.users[token] = {
            'id': uid,
            'aud': 'authenticated',
            'role': 'authenticated',
            'email': (user.email or '').lower(),
            'email_confirmed_at': '2026-01-01T00:00:00Z',
            'app_metadata': {'provider': 'email', **({'role': 'admin'} if user.is_superuser else {})},
            'user_metadata': {},
            'created_at': user.date_joined.isoformat() if user.date_joined else '2026-01-01T00:00:00Z',
        }
        return {'uid': uid, 'session': session, 'device': device, 'token': token}

    def install(self) -> bool:
        try:
            from accounts.supabase_rest_auth import SupabaseJWTAuthentication
        except ImportError:
            return False
        if not hasattr(SupabaseJWTAuthentication, '_fetch_supabase_user'):
            return False
        probe = self

        def _fetch_supabase_user(self, token):
            payload = probe.users.get(token)
            if payload is None:
                return None
            if token not in probe.seen:
                probe.gotrue_calls += 1
                if probe.gotrue_s:
                    time.sleep(probe.gotrue_s)
                probe.seen.add(token)
            return dict(payload)

        SupabaseJWTAuthentication._fetch_supabase_user = _fetch_supabase_user
        self.installed = True
        return True


def _valid_key_q():
    from django.db.models import Q
    return Q(correct_answer__in=['A', 'B', 'C', 'D'])


def pick_fixtures(users: dict) -> dict:
    """Deterministic ids from crack_local (read-only)."""
    from django.db.models import Count, Q
    from questions.models import Question, QuestionAttempt
    from questions.views import free_showcase_rows
    from tests_engine.models import Test

    answered = set(QuestionAttempt.objects.filter(user__in=list(users.values())).values_list('question_id', flat=True))
    cms = (Question.objects.filter(is_active=True, exam_type='cms', is_scholarship_eligible=False)
           .filter(_valid_key_q()).exclude(exam_source__istartswith='NEET').exclude(exam_source__istartswith='INI'))
    showcase_ids = list(free_showcase_rows().filter(question__is_active=True)
                        .filter(**{'question__correct_answer__in': ['A', 'B', 'C', 'D']})
                        .order_by('question_id').values_list('question_id', flat=True))
    with_images = (cms.annotate(n_img=Count('images', filter=Q(images__is_active=True)))
                   .exclude(pk__in=answered).order_by('id'))
    q_img = None
    # A premium (non-showcase) question first, so anonymous / free readers get the redacted path.
    tiers = ({'n_img__gte': 2, 'topic__isnull': False}, {'n_img__gte': 1, 'topic__isnull': False}, {'n_img__gte': 1})
    for pool in (with_images.exclude(pk__in=showcase_ids), with_images):
        q_img = next((qid for qid in (pool.filter(**extra).values_list('id', flat=True).first() for extra in tiers)
                      if qid), None)
        if q_img:
            break
    q_show = next((qid for qid in showcase_ids if qid not in answered), showcase_ids[0] if showcase_ids else None)
    q_neet = (Question.objects.filter(is_active=True, exam_source__startswith='NEET PG').filter(_valid_key_q())
              .exclude(pk__in=answered).order_by('id').values_list('id', flat=True).first())
    paper_source = (Test.objects.filter(is_published=True, exam_type='cms')
                    .annotate(n=Count('questions')).filter(n=120).order_by('id').values_list('id', flat=True).first())
    paper_ids = []
    if paper_source:
        paper_ids = sorted(Test.objects.get(pk=paper_source).questions
                           .filter(is_active=True).filter(_valid_key_q()).values_list('id', flat=True))
    keys = dict(Question.objects.filter(pk__in=paper_ids + showcase_ids[:20] + [q for q in (q_img, q_show, q_neet) if q])
                .values_list('id', 'correct_answer'))
    return {
        'q_img': q_img, 'q_show': q_show, 'q_neet': q_neet,
        'paper_source_test': paper_source, 'paper_question_ids': paper_ids,
        'test20_question_ids': showcase_ids[:20], 'keys': keys,
    }


def _wrong(letter: str) -> str:
    letters = 'ABCD'
    return letters[(letters.index(letter) + 1) % 4] if letter in letters else 'A'


def submit_payload(attempt_id, question_ids, keys) -> dict:
    """All answered, 40 % wrong (every 5th and 5th+1), 45 s each."""
    answers = []
    for i, qid in enumerate(question_ids):
        key = keys.get(qid) or 'A'
        answers.append({
            'question_id': qid,
            'selected_answer': _wrong(key) if i % 5 < 2 else key,
            'time_taken_seconds': 45,
            'confidence_level': 3,
        })
    return {'attempt_id': attempt_id, 'answers': answers}


def endpoint_specs() -> list[dict]:
    def spec(key, user, method, path, body=None, needs=(), pre=None, phases=('cold', 'warm')):
        return {'key': key, 'user': user, 'method': method, 'path': path, 'body': body,
                'needs': tuple(needs), 'pre': pre, 'phases': phases}

    ai = [spec(f'ai.{name}', 'premium', 'GET', f'/api/questions/{{q_img}}/ai/{name}/') for name in
          ('why_correct', 'clinical', 'mnemonic', 'exam_importance', 'concept', 'why_incorrect',
           'related_pyqs', 'related_topics')]
    analytics = [spec(f'analytics.{name}', 'premium', 'GET', f'/api/analytics/{name}/') for name in
                 ('weak-topics', 'topic-performance', 'performance-trend', 'score-prediction', 'heatmap',
                  'leaderboard', 'dashboard_v3', 'dashboard')]
    return [
        spec('auth.profile', 'student', 'GET', '/api/auth/profile/'),
        spec('auth.profile', 'premium', 'GET', '/api/auth/profile/'),
        spec('auth.tokens', 'student', 'GET', '/api/auth/tokens/'),
        spec('auth.tokens', 'premium', 'GET', '/api/auth/tokens/'),
        spec('analytics.announcements', 'student', 'GET', '/api/analytics/announcements/'),
        spec('dashboard.bundle', 'student', 'GET', '/api/analytics/dashboard/bundle/'),
        spec('dashboard.bundle', 'premium', 'GET', '/api/analytics/dashboard/bundle/'),
        spec('questions.stats', 'student', 'GET', '/api/questions/stats/?exam_source=UPSC%20CMS'),
        spec('questions.list', 'student', 'GET', '/api/questions/?page=1&page_size=20&exam_type=cms'),
        spec('questions.list', 'premium', 'GET', '/api/questions/?page=1&page_size=20&exam_type=cms'),
        spec('questions.list', 'admin', 'GET', '/api/questions/?page=1&page_size=20&exam_type=cms'),
        spec('questions.list_search', 'student', 'GET',
             '/api/questions/?page=1&page_size=20&exam_type=cms&search=anaemia'),
        spec('questions.subjects', 'student', 'GET', '/api/questions/subjects/'),
        spec('questions.topics', 'student', 'GET', '/api/questions/topics/'),
        spec('questions.years', 'student', 'GET', '/api/questions/years/?exam_type=cms'),
        spec('questions.detail', 'anon', 'GET', '/api/questions/{q_img}/'),
        spec('questions.detail', 'student', 'GET', '/api/questions/{q_show}/'),
        spec('questions.detail', 'premium', 'GET', '/api/questions/{q_img}/'),
        spec('questions.detail', 'admin', 'GET', '/api/questions/{q_img}/'),
        spec('questions.detail_neet', 'premium', 'GET', '/api/questions/{q_neet}/'),
        spec('questions.similar', 'student', 'GET', '/api/questions/{q_show}/similar/'),
        spec('questions.similar', 'premium', 'GET', '/api/questions/{q_img}/similar/'),
        spec('questions.discussions', 'premium', 'GET', '/api/questions/discussions/?question={q_img}'),
        *ai,
        spec('questions.attempt', 'premium', 'POST', '/api/questions/{q_img}/attempt/',
             body={'selected_answer': '{wrong_q_img}', 'time_spent_seconds': 40}),
        spec('questions.attempt', 'student', 'POST', '/api/questions/{q_show}/attempt/',
             body={'selected_answer': '{wrong_q_show}', 'time_spent_seconds': 40}),
        spec('questions.practice_attempt', 'premium', 'POST', '/api/questions/{q_img}/practice/attempt/',
             body={'answer': '{wrong_q_img}', 'time_spent': 40, 'confidence': 3}),
        spec('questions.practice_queue', 'student', 'GET', '/api/questions/practice_queue/?mode=random'),
        spec('questions.recall_search', 'anon', 'GET', '/api/questions/recall_search/?q=hypertension'),
        spec('questions.recall_search', 'student', 'GET', '/api/questions/recall_search/?q=hypertension'),
        spec('questions.recall_search', 'premium', 'GET', '/api/questions/recall_search/?q=hypertension'),
        spec('tests.library', 'student', 'GET', '/api/tests/?scope=library'),
        spec('tests.start', 'premium', 'POST', '/api/tests/{paper}/start/', needs=('paper',)),
        spec('tests.submit', 'premium', 'POST', '/api/tests/{paper}/submit/', needs=('paper',), pre='start'),
        spec('tests.review', 'premium', 'GET', '/api/tests/{paper}/review/?attempt_id={attempt}',
             needs=('paper',), pre='submit'),
        spec('tests.start', 'student', 'POST', '/api/tests/{test20}/start/', needs=('test20',)),
        spec('tests.submit', 'student', 'POST', '/api/tests/{test20}/submit/', needs=('test20',), pre='start'),
        *analytics,
        spec('ai.tutor', 'premium', 'POST', '/api/ai/tutor/',
             body={'question': 'What is the drug of choice for absence seizures?'}),
    ]


class Probe:
    def __init__(self, args):
        from django.contrib.auth import get_user_model

        self.args = args
        self.auth_mode = args.auth
        self.recorder = StatementRecorder(args.rtt_ms)
        self.auth = ProbeAuth(args.gotrue_ms)
        if self.auth_mode == 'supabase' and not self.auth.install():
            print('SupabaseJWTAuthentication._fetch_supabase_user not found; falling back to --auth force.')
            self.auth_mode = 'force'
        User = get_user_model()
        self.users = {}
        for label, email in SEED_EMAILS.items():
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise SystemExit(f'Seed user {label!r} missing: run manage.py seed_local_dev_users.')
            self.users[label] = user
        self.identities = {label: self.auth.identity(user) for label, user in self.users.items()}
        self.fixtures = pick_fixtures(self.users)
        missing = [k for k in ('q_img', 'q_show', 'q_neet') if not self.fixtures.get(k)]
        if missing or not self.fixtures['paper_question_ids']:
            raise SystemExit(f'crack_local lacks probe fixtures: {missing or ["paper"]}')
        from django.conf import settings
        frontend = (getattr(settings, 'FRONTEND_URL', '') or 'http://localhost:3000').split(',')[0].strip()
        self.origin = frontend or 'http://localhost:3000'
        hosts = list(getattr(settings, 'ALLOWED_HOSTS', []) or [])
        self.host = next((h for h in ('localhost', '127.0.0.1', 'testserver') if h in hosts or '*' in hosts), None)
        if self.host is None:
            settings.ALLOWED_HOSTS = hosts + ['testserver']
            self.host = 'testserver'

    # ── per-run state, inside the run's transaction ──
    def _prime_user(self, label):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        if label == 'anon':
            return None
        User = get_user_model()
        user = self.users[label]
        ident = self.identities[label]
        now = timezone.now()
        updates = {'last_seen': now}
        if self.auth_mode == 'supabase' and not (user.supabase_uid or '').strip():
            updates['supabase_uid'] = ident['uid']
        User.objects.filter(pk=user.pk).update(**updates)
        if self.auth_mode == 'supabase' and user.role != 'admin':
            from accounts.models import UserDevice
            row = UserDevice.objects.filter(user_id=user.pk, device_fingerprint=ident['device']).first()
            values = {'session_id': ident['session'], 'device_name': PROBE_UA, 'ip_address': PROBE_IP,
                      'is_active': True}
            if row is None:
                UserDevice.objects.create(user_id=user.pk, device_fingerprint=ident['device'], **values)
            else:
                UserDevice.objects.filter(pk=row.pk).update(last_login=now, **values)
        return User.objects.get(pk=user.pk)

    def _make_tests(self, needs, ctx):
        from tests_engine.models import Test

        if 'paper' in needs:
            paper = Test.objects.create(
                title='Perf probe paper 1', exam_type='cms', test_type='paper1', num_questions=120,
                time_limit_minutes=120, negative_marking=True, negative_mark_value=0.33,
                is_published=True, created_by=self.users['premium'],
            )
            paper.questions.set(self.fixtures['paper_question_ids'])
            ctx['paper'] = paper.pk
            ctx['paper_qids'] = self.fixtures['paper_question_ids']
        if 'test20' in needs:
            test = Test.objects.create(
                title='Perf probe daily', exam_type='cms', test_type='daily', num_questions=20,
                time_limit_minutes=30, negative_marking=True, negative_mark_value=0.33,
                is_published=True, created_by=self.users['student'],
            )
            test.questions.set(self.fixtures['test20_question_ids'])
            ctx['test20'] = test.pk
            ctx['test20_qids'] = self.fixtures['test20_question_ids']

    def _client(self, label, user):
        from rest_framework.test import APIClient

        client = APIClient(raise_request_exception=False)
        headers = {'HTTP_ORIGIN': self.origin, 'HTTP_USER_AGENT': PROBE_UA, 'HTTP_HOST': self.host}
        if label == 'anon':
            headers['HTTP_X_SESSION_ID'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'crack-perf-probe:anon'))
        elif self.auth_mode == 'supabase':
            ident = self.identities[label]
            headers['HTTP_AUTHORIZATION'] = f"Bearer {ident['token']}"
            headers['HTTP_X_SESSION_ID'] = ident['device']
        else:
            client.force_authenticate(user=user)
            headers['HTTP_X_SESSION_ID'] = self.identities[label]['device']
        return client, headers

    @staticmethod
    def _fill(template, ctx):
        if isinstance(template, str):
            return template.format(**ctx)
        if isinstance(template, dict):
            return {k: Probe._fill(v, ctx) for k, v in template.items()}
        return template

    @staticmethod
    def _call(client, method, path, body, headers):
        if method == 'GET':
            return client.get(path, **headers)
        return client.generic(method, path, data=json.dumps(body or {}), content_type='application/json', **headers)

    def _context(self):
        keys = self.fixtures['keys']
        return {
            'q_img': self.fixtures['q_img'], 'q_show': self.fixtures['q_show'], 'q_neet': self.fixtures['q_neet'],
            'wrong_q_img': _wrong(keys.get(self.fixtures['q_img'], 'A')),
            'wrong_q_show': _wrong(keys.get(self.fixtures['q_show'], 'A')),
            'attempt': '',
        }

    def _pre_steps(self, spec, client, headers, ctx):
        """Start (and submit) an attempt outside the measured window."""
        test_key = 'paper' if 'paper' in spec['needs'] else 'test20'
        test_id = ctx[test_key]
        resp = self._call(client, 'POST', f'/api/tests/{test_id}/start/', {}, headers)
        if resp.status_code != 200:
            raise RuntimeError(f'pre-step start answered {resp.status_code}')
        ctx['attempt'] = resp.json()['attempt_id']
        payload = submit_payload(ctx['attempt'], ctx[f'{test_key}_qids'], self.fixtures['keys'])
        ctx['submit_body'] = payload
        if spec['pre'] == 'submit':
            resp = self._call(client, 'POST', f'/api/tests/{test_id}/submit/', payload, headers)
            if resp.status_code != 200:
                raise RuntimeError(f'pre-step submit answered {resp.status_code}')

    def run_once(self, spec) -> dict:
        from django.db import transaction

        result = {}
        with transaction.atomic():
            user = self._prime_user(spec['user'])
            ctx = self._context()
            self._make_tests(spec['needs'], ctx)
            client, headers = self._client(spec['user'], user)
            if spec['pre']:
                self._pre_steps(spec, client, headers, ctx)
            path = self._fill(spec['path'], ctx)
            body = ctx.get('submit_body') if spec['key'] == 'tests.submit' else self._fill(spec['body'], ctx)
            self.recorder.start()
            started = time.perf_counter()
            try:
                response = self._call(client, spec['method'], path, body, headers)
            finally:
                wall = (time.perf_counter() - started) * 1000.0
                rows = self.recorder.stop()
            content = getattr(response, 'content', b'') or b''
            result = summarize_statements(rows)
            if getattr(self.args, 'trace', False):
                result['trace'] = [f'{seconds * 1000:7.2f} ms  {sql_template(sql)[:200]}' for sql, seconds in rows]
            result.update({
                'status': response.status_code,
                'wall_ms': round(wall, 2),
                'bytes': len(content),
                'gzip_bytes': len(gzip.compress(content, 6)) if content else 0,
            })
            if response.status_code >= 400:
                try:
                    payload = json.loads(content.decode('utf-8'))
                    result['error_code'] = str(payload.get('code') or payload.get('detail') or '')[:60]
                except (ValueError, UnicodeDecodeError, AttributeError):
                    pass
            transaction.set_rollback(True)
        return result

    @staticmethod
    def clear_caches(auth: ProbeAuth):
        from django.core.cache import caches
        from django.conf import settings

        for alias in settings.CACHES:
            caches[alias].clear()
        auth.seen.clear()

    def selected(self):
        pattern = re.compile(self.args.only) if self.args.only else None
        for spec in endpoint_specs():
            name = f"{spec['key']}:{spec['user']}"
            if pattern and not pattern.search(name):
                continue
            yield spec

    def run(self) -> dict:
        from django.db import connection

        specs = list(self.selected())
        phases = [p.strip() for p in self.args.phases.split(',') if p.strip()]
        endpoints = []
        with connection.execute_wrapper(self.recorder):
            # Process warm-up: imports, URL resolvers, the BM25 index.
            first = {}
            for spec in specs:
                self.clear_caches(self.auth)
                started = time.perf_counter()
                self.run_once(spec)
                first[(spec['key'], spec['user'])] = round((time.perf_counter() - started) * 1000.0, 1)
            for spec in specs:
                entry = {'key': spec['key'], 'user': spec['user'], 'method': spec['method'],
                         'path': spec['path'], 'first_ms': first[(spec['key'], spec['user'])], 'phases': {}}
                for phase in phases:
                    if phase not in spec['phases']:
                        continue
                    runs = []
                    if phase == 'warm':
                        self.clear_caches(self.auth)
                        self.run_once(spec)          # priming request, not measured
                    for _ in range(self.args.runs):
                        if phase == 'cold':
                            self.clear_caches(self.auth)
                        runs.append(self.run_once(spec))
                    entry['phases'][phase] = aggregate_runs(runs)
                    if getattr(self.args, 'trace', False) and runs and runs[0].get('trace'):
                        print(f"--- {spec['key']} {spec['user']} ({phase}, first run)")
                        print('\n'.join(runs[0]['trace']))
                endpoints.append(entry)
                main = entry['phases'].get('warm') or entry['phases'].get('cold') or {}
                print(f"{spec['key']:<28} {spec['user']:<8} {main.get('status')} q={main.get('queries')} "
                      f"dup={main.get('duplicates')} sql={main.get('sql_ms')}ms p50={main.get('wall_p50_ms')}ms",
                      flush=True)
        return {'endpoints': endpoints, 'flows': compute_flows(endpoints, 'warm') + compute_flows(endpoints, 'cold')}


def measure_boot_scan() -> dict:
    """Wall time and statements of the relink pass every server process starts
    (questions.apps auto-heal), run as a dry run (no writes)."""
    import io
    from django.core.management import call_command
    from django.db import connection, transaction

    recorder = StatementRecorder()
    with connection.execute_wrapper(recorder):
        with transaction.atomic():
            recorder.start()
            started = time.perf_counter()
            call_command('relink_fixture_images', stdout=io.StringIO(), stderr=io.StringIO(), no_color=True)
            wall = (time.perf_counter() - started) * 1000.0
            rows = recorder.stop()
            transaction.set_rollback(True)
    summary = summarize_statements(rows)
    return {'relink_fixture_images_dry_run_ms': round(wall, 1),
            'relink_fixture_images_statements': summary['queries']}


def _server_version() -> str:
    from django.db import connection
    try:
        connection.ensure_connection()
        version = int(connection.pg_version)
    except Exception:  # noqa: BLE001 - informational only
        return '?'
    return f'{version // 10000}.{version % 10000}'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--label', default='probe')
    parser.add_argument('--runs', type=int, default=7)
    parser.add_argument('--rtt-ms', type=float, default=0.0)
    parser.add_argument('--gotrue-ms', type=float, default=0.0)
    parser.add_argument('--auth', choices=('supabase', 'force'), default='supabase')
    parser.add_argument('--phases', default='cold,warm')
    parser.add_argument('--only', default='', help='regex on "<key>:<user>"')
    parser.add_argument('--no-boot', action='store_true', help='skip the relink boot-scan measurement')
    parser.add_argument('--trace', action='store_true', help='print the statements of the first run of each phase')
    parser.add_argument('--out', default=os.path.join('..', 'docs', 'audit', 'perf'))
    parser.add_argument('--compare', nargs=2, metavar=('BEFORE_JSON', 'AFTER_JSON'))
    args = parser.parse_args(argv)

    if args.compare:
        with open(args.compare[0], encoding='utf-8') as fh:
            before = json.load(fh)
        with open(args.compare[1], encoding='utf-8') as fh:
            after = json.load(fh)
        text = render_comparison(before, after)
        if args.out.endswith('.md'):
            with open(args.out, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
        print(text)
        return 0

    from django.conf import settings

    db = settings.DATABASES['default']
    for reason in (database_refusal(db, settings.DEBUG), cache_refusal(settings.CACHES),
                   env_refusal(os.environ)):
        if reason:
            print(reason)
            return 2
    if (os.getenv('AI_OFFLINE_MODE') or '').strip().lower() not in _TRUE:
        print('Refusing: AI_OFFLINE_MODE must be 1.')
        return 2
    install_network_guard()
    install_non_blocking_throttles()

    probe = Probe(args)
    results = probe.run()
    report = {
        'label': args.label,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'config': {
            'runs': args.runs, 'rtt_ms': args.rtt_ms, 'gotrue_ms': args.gotrue_ms, 'auth': probe.auth_mode,
            'phases': args.phases, 'only': args.only, 'debug': bool(settings.DEBUG),
            'db': {'vendor': 'postgresql', 'name': db.get('NAME'), 'host': db.get('HOST'),
                   'server_version': _server_version()},
            'python': sys.version.split()[0],
        },
        'fixtures': {k: v for k, v in probe.fixtures.items() if k not in ('keys', 'paper_question_ids',
                                                                          'test20_question_ids')},
        'fixture_sizes': {'paper_questions': len(probe.fixtures['paper_question_ids']),
                          'test20_questions': len(probe.fixtures['test20_question_ids'])},
        **results,
    }
    if not args.no_boot and not args.only:
        report['boot'] = measure_boot_scan()
    os.makedirs(args.out, exist_ok=True)
    base = os.path.join(args.out, f'backend_{args.label}')
    with open(base + '.json', 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(report, fh, indent=1, sort_keys=False, default=str)
        fh.write('\n')
    with open(base + '.md', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(render_markdown(report))
    print(f'wrote {base}.json and .md')
    return 0


if __name__ == '__main__':
    if '--compare' not in sys.argv:
        _reason = env_refusal(os.environ)
        if _reason:
            print(_reason)
            sys.exit(2)
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
        import django
        django.setup()
    sys.exit(main())
