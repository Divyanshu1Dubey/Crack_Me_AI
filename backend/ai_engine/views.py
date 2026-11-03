"""
Enhanced AI Engine API Views with RAG integration.

Token System Integration:
- AI calls consume tokens via consume_ai_token(): 1 for tutor chat, textbook
  answers and a fresh high-yield prediction; 10 for mnemonic, explain,
  analyze, explain-answer, explain-question, study plan and question
  generation.
- Admins, staff (_is_unmetered_staff) and unlimited plans bypass token limits entirely.
- Students get free daily/weekly tokens; after exhaustion, they must buy tokens.
- Token config is managed via Django Admin > Token Configuration.

Failure contract: when no AI provider answers, AIService raises AIUnavailable.
Every view then gives back what it charged (tokens AND the freemium slot),
persists and caches nothing, and answers either with a grounded extractive
offline answer (ai_engine.offline) or a 503 {code: 'ai_unavailable'}.
With AI_OFFLINE_MODE on, the same offline answers are served free of charge
and no provider is called.
"""
import hashlib
import json
import logging
import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from crack_cms.throttling import ScopedRateThrottle
from rest_framework import status
from django.conf import settings as django_settings
from django.core.cache import cache
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .offline import (
    REASON_OFFLINE_MODE,
    REASON_PROVIDERS_DOWN,
    ai_offline_mode,
    compose_offline_answer,
    is_unusable_text,
    offline_notice,
    public_subject,
    pyq_summary,
    stored_rich_explanation,
    with_public_subject,
)
from .services import AIService, AIUnavailable
from accounts.models import TokenBalance

logger = logging.getLogger(__name__)

# Input limits for every AI endpoint (prompt size drives provider cost).
MAX_AI_INPUT_CHARS = 4000      # question / topic / concept / question stem
MAX_AI_CONTEXT_CHARS = 6000    # optional extra context sent to the tutor
MAX_AI_PROMPT_CHARS = 1000     # custom instruction on explain-question
MAX_OPTION_CHARS = 1000
MAX_LABEL_CHARS = 200          # subject / topic labels

AI_UNAVAILABLE_MESSAGE = (
    'The AI tutor is unavailable right now and no grounded offline answer was '
    'found for this question. You were not charged. Please try again in a few minutes.'
)
AI_OFFLINE_UNAVAILABLE_MESSAGE = (
    'AI generation is switched off (offline mode) and no grounded offline answer '
    'was found for this question. You were not charged.'
)


def _as_text(value) -> str:
    """A request field as stripped text ('' for missing / non-scalar values)."""
    if value is None or isinstance(value, (dict, list, tuple)):
        return ''
    return str(value).strip()


def _required_text(request, name: str, label: str, max_chars: int = MAX_AI_INPUT_CHARS):
    """(text, None) or ('', 400 Response) for a required, length-capped field."""
    text = _as_text(request.data.get(name))
    if not text:
        return '', Response({'error': f'{label} is required'}, status=400)
    if len(text) > max_chars:
        return '', Response(
            {'error': f'{label} is too long (max {max_chars} characters)'}, status=400,
        )
    return text, None


def _optional_text(request, name: str, max_chars: int) -> str:
    return _as_text(request.data.get(name))[:max_chars]


def _as_bool(value) -> bool:
    """Strict boolean parse: multipart 'false' / '0' are False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return _as_text(value).lower() in ('1', 'true', 'yes', 'on')


def _answer_letter(value) -> str:
    letter = _as_text(value).upper()[:1]
    return letter if letter in ('A', 'B', 'C', 'D') else ''


def _options_param(value) -> dict:
    """Client-supplied options as {A..D: text}, capped; anything else dropped."""
    if not isinstance(value, dict):
        return {}
    out = {}
    for key in ('A', 'B', 'C', 'D'):
        raw = value.get(key, value.get(key.lower()))
        if raw is not None:
            out[key] = _as_text(raw)[:MAX_OPTION_CHARS]
    return out


def _ai_unavailable_response(*, offline: bool = False, message: str = None) -> Response:
    """503 telling the client no AI (and no grounded offline) answer exists.
    `error` stays human-readable for clients that display it directly."""
    text = message or (AI_OFFLINE_UNAVAILABLE_MESSAGE if offline else AI_UNAVAILABLE_MESSAGE)
    return Response(
        {'code': 'ai_unavailable', 'error': text, 'message': text,
         'offline': offline, 'charged': False},
        status=503,
    )


# ─── Question-bank entitlement ──────────────────────────────────────────
#
# An explanation of a question-bank question reveals its answer: stored and
# cached explanations, the curated explanation served offline, the DB answer
# key behind `is_correct` / `ai_verified_answer`, and any fresh AI text built
# from that key. So the explain endpoints apply the question bank's ONE rule
# (questions.views.user_can_view_answer) to every DB question, on every path
# (stored, cached, generated, offline, outage), before anything is served.

ANSWER_PAYWALL_FEATURE = 'PYQ answers'


def _can_view_answer(user, question) -> bool:
    """True when ``user`` may see the answer / explanation of the DB
    ``question``: staff, premium subscribers, or an admin-curated free
    showcase question (``questions.views.user_can_view_answer``).
    Scholarship-test questions are never explained to non-premium users,
    even when showcased. Fails closed."""
    try:
        from questions.views import user_can_view_answer

        if not user_can_view_answer(user, question):
            return False
        if getattr(question, 'is_scholarship_eligible', False):
            from accounts.utils import is_premium
            return bool(
                user is not None and getattr(user, 'is_authenticated', False) and (
                    getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)
                    or getattr(user, 'is_staff', False) or is_premium(user)
                )
            )
        return True
    except Exception:
        logger.exception('Answer entitlement check failed for Q%s; denying',
                         getattr(question, 'pk', question))
        return False


def _answer_paywall_response() -> Response:
    """402 ``upgrade_required`` -- the question bank's paywall envelope (the
    frontend interceptor opens the upgrade modal on it). Nothing is charged."""
    return Response(
        {
            'code': 'upgrade_required',
            'feature': ANSWER_PAYWALL_FEATURE,
            'message': (
                'This question is part of the premium question bank. '
                'Subscribe to see answers and explanations.'
            ),
            'charged': False,
        },
        status=402,
    )


class IsAdminUser(BasePermission):
    """Custom permission to only allow admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (hasattr(request.user, 'is_admin') and request.user.is_admin or request.user.is_superuser)
        )


def _get_permission():
    """Never bypass authentication — DEBUG mode still requires valid users."""
    return [IsAuthenticated()]


def _get_admin_permission():
    """Only allow admin users (for upload/train features)."""
    return [IsAdminUser()]


class AITutorThrottleMixin:
    """Apply the 'ai_tutor' scoped rate limit (30/min default — see settings.REST_FRAMEWORK).

    Mix in on any AI tutor / RAG / generation endpoint to defend against
    runaway agent loops or scripts that hammer the LLM round-robin.
    Admins inherit the auth permission; the throttle layer lives independently.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_tutor'


def _set_consumption(request, breakdown):
    try:
        request._ai_token_consumption = breakdown
    except Exception:  # pragma: no cover - exotic request objects
        pass


def _is_unmetered_staff(user) -> bool:
    """Admins, superusers and staff: AI use is never metered or capped (the
    token wallet's ``unlimited_ai`` and the header's 'Unlimited' pill rely
    on the same rule)."""
    return bool(
        getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)
        or getattr(user, 'is_staff', False)
    )


def consume_ai_token(request, amount: int = 1):
    """
    Check and consume N AI tokens for the requesting user.

    Returns:
        (True, None) — token consumed successfully (or bypassed), proceed with AI call.
        (False, Response) — insufficient tokens, return the error response.

    Bypass rules (in priority order):
      1. Unauthenticated in DEBUG mode → bypass (dev only).
      2. Admin / superuser / staff (`_is_unmetered_staff`) → unlimited.
      3. Active subscription with `unlimited_ai=True` (1_year / legacy / admin_grant)
         → unlimited, no token deducted. THIS IS THE FIX FOR:
         "I paid for Premium but tokens keep decreasing."
      4. Otherwise → consume ``amount`` tokens. If insufficient, return 429.

    Token cost (2026-08-04 update): heavy generation endpoints that produce a
    structured multi-section analysis (mnemonic + why_correct + topic deep dive
    + high-yield points + key differentiators + textbook references + clinical
    pearls + exam tips + quick revision + related concepts + PYQ intelligence)
    cost 10 tokens per call. Lighter chat-style endpoints (ask_tutor,
    generate_questions) cost 1 token per call. The distinction is encoded
    at the call site, not here, so we keep this function parameterised.
    """
    user = getattr(request, 'user', None)
    # Nothing consumed yet for this request -> nothing to refund.
    _set_consumption(request, None)
    if not user or not user.is_authenticated:
        if getattr(django_settings, 'DEBUG', False):
            return True, None
        return False, Response({'error': 'Authentication required'}, status=401)

    # 1. Admins and staff have unlimited tokens
    if _is_unmetered_staff(user):
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
    if balance.consume_token(amount=amount):
        _set_consumption(request, getattr(balance, '_last_consumption', None))
        return True, None

    return False, Response({
        'error': 'insufficient_tokens',
        'message': f'This AI action costs {amount} tokens but you have insufficient balance. Subscribe for unlimited usage or purchase more tokens.',
        'available': balance.available_tokens,
        'required': amount,
    }, status=429)


def refund_ai_token(request, amount: int = 1):
    """Refund AI tokens if the AI call fails after token was consumed.

    The prior implementation only refunded daily/weekly counters and never
    restored feedback_credits or purchased_tokens — meaning every AI failure
    silently cost the user 1 paid token. We now write a 'consume' transaction
    on success and a matching 'refund' on failure so the source pool is
    reversed exactly.

    The ``amount`` argument must match the ``amount`` that was originally
    passed to ``consume_ai_token`` so we never over-refund.
    """
    from accounts.models import TokenBalance, TokenTransaction

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or _is_unmetered_staff(user):
        return

    # Refund exactly what consume_ai_token drew for this request. When the
    # call was bypassed (subscription / admin) nothing was deducted, so
    # nothing is refunded -- refunding anyway minted free tokens.
    breakdown = getattr(request, '_ai_token_consumption', None)
    if not breakdown:
        return
    _set_consumption(request, None)  # never refund the same draw twice

    try:
        balance = TokenBalance.objects.get(user=user)
        balance.refund_token(amount=amount, breakdown=breakdown)
        # Audit log so refunds are visible in transaction history
        TokenTransaction.objects.create(
            user=user,
            transaction_type='refund',
            amount=amount,
            price_paid=0,
            note=f'AI call failed — {amount} token(s) refunded',
        )
        logger.info(f"Refunded {amount} AI token(s) for user {user.username}")
    except TokenBalance.DoesNotExist:
        pass


# Free-tier daily cap for the AI Tutor (tutor/mnemonic/explain/textbook/analyze).
# Premium and admin users bypass entirely. The cap is *additional* to the
# existing token economy (daily 10 + weekly 50 + purchased + feedback) — users
# with an unlimited plan never hit this counter at all.
#
# Configurable at runtime via ``accounts.TokenConfig.ai_tutor_daily_cap`` so
# ops can tune without a deploy. Falls back to the constant when no row exists.
AI_TUTOR_DAILY_FREE_CAP = 2


def _ai_tutor_cap() -> int:
    """Read the AI tutor daily cap from TokenConfig (single source of truth)."""
    try:
        from accounts.models import TokenConfig
        cfg = TokenConfig.get_config()
        val = getattr(cfg, 'ai_tutor_daily_cap', None)
        if isinstance(val, int) and val >= 0:
            return val
    except Exception:
        logger.exception('_ai_tutor_cap: TokenConfig lookup failed; using fallback')
    return AI_TUTOR_DAILY_FREE_CAP


def _take_ai_tutor_slot(user):
    """Atomic check-and-consume for the AI tutor daily cap.

    Returns ``(error_response, slot_day)``: ``(None, day)`` when a slot was
    consumed (``day`` lets the caller release exactly that slot later),
    ``(None, None)`` when the user is exempt, ``(402 Response, None)`` when
    the daily cap is hit. Uses ``models_usage.check_and_consume`` which holds
    a row lock for the entire check+increment window.

    Exempt: anonymous (the view's permissions answer 401), admin/superuser/
    staff, and every user with an active subscription of any plan
    (``accounts.utils.is_premium``) — the profile already tells subscribers
    their AI tutor cap is unlimited (``ai_tutor_daily_cap = None``); holding
    1-month/3-month subscribers to the free cap contradicted that.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return None, None
    if _is_unmetered_staff(user):
        return None, None

    try:
        from accounts.utils import is_premium
        if is_premium(user):
            return None, None
    except Exception:
        logger.exception('_check_ai_tutor_quota: subscription lookup failed; applying cap anyway')

    from .models_usage import check_and_consume

    cap = _ai_tutor_cap()
    day = timezone.localdate()
    allowed, _new_count = check_and_consume(user, cap=cap)
    if allowed:
        return None, day
    return Response(
        {
            'code': 'upgrade_required',
            'feature': 'AI Tutor',
            'message': (
                f"You've used your {cap} free AI Tutor messages for today. "
                'Subscribe to remove the daily limit — plans start at ₹129/month.'
            ),
            'remaining': 0,
            'cap': cap,
        },
        status=402,
    ), None


def _check_ai_tutor_quota(user):
    """Returns ``None`` if the user may proceed, or the 402 ``Response`` when
    the free daily cap is hit (consumes one slot when it lets a free user
    through). See ``_take_ai_tutor_slot``."""
    err, _day = _take_ai_tutor_slot(user)
    return err


def _check_freemium_ai_quota(request):
    """Convenience wrapper for views: same as ``_check_ai_tutor_quota`` but
    reads ``user`` off the request object and remembers a consumed slot on the
    request so ``_release_freemium_slot`` can give it back if the call does
    not deliver an answer. Returns the Response to short-circuit with, or
    ``None`` if the call may proceed.
    """
    err, day = _take_ai_tutor_slot(getattr(request, 'user', None))
    if day is not None:
        try:
            request._ai_tutor_slot_day = day
        except Exception:  # pragma: no cover - exotic request objects
            pass
    return err


def _release_freemium_slot(request) -> None:
    """Give back the freemium slot this request consumed (no-op otherwise)."""
    day = getattr(request, '_ai_tutor_slot_day', None)
    if not day:
        return
    try:
        request._ai_tutor_slot_day = None  # never release the same slot twice
    except Exception:  # pragma: no cover
        pass
    try:
        from .models_usage import release_ai_tutor_message
        release_ai_tutor_message(request.user, date=day)
    except Exception:
        logger.exception('Failed to release AI tutor slot')


def _charge_ai_call(request, *, amount: int, freemium: bool):
    """Spend the freemium slot (capped endpoints) and then ``amount`` tokens.

    Returns an error Response, or None when the call may proceed. When the
    token check fails the slot is given back, so a 429 never costs a free
    message.
    """
    if freemium:
        err = _check_freemium_ai_quota(request)
        if err is not None:
            return err
    ok, err = consume_ai_token(request, amount=amount)
    if not ok:
        if freemium:
            _release_freemium_slot(request)
        return err
    return None


def _refund_ai_call(request, *, amount: int) -> None:
    """Give back everything this request was charged: the tokens (exact
    pools, see refund_ai_token) and the freemium slot."""
    try:
        refund_ai_token(request, amount=amount)
    except Exception:
        logger.exception('AI token refund failed')
    _release_freemium_slot(request)


# ─── Chat history (server-side, opt-in per request) ────────────────────

def _clean_citations(citations) -> list:
    if not isinstance(citations, list):
        return []
    out = []
    for c in citations[:20]:
        if isinstance(c, dict):
            out.append({
                'book': _as_text(c.get('book'))[:200],
                'page': c.get('page') if isinstance(c.get('page'), (int, str)) else '',
                'excerpt': _as_text(c.get('excerpt'))[:300],
                'relevance': c.get('relevance') if isinstance(c.get('relevance'), (int, float)) else None,
            })
    return out


def _record_chat_turn(request, payload: dict, *, mode: str, question: str, answer: str,
                      citations=None) -> None:
    """Save the question and the answer to the user's chat history when the
    client asked for it (``save_history`` or a ``chat_session_id``), and put
    the session id in ``payload['chat_session_id']``. Never fails the AI
    response: history is best-effort."""
    data = request.data
    session_id = data.get('chat_session_id')
    if not (_as_bool(data.get('save_history')) or session_id not in (None, '')):
        return
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False) or not answer:
        return
    try:
        from .models import ChatMessage, ChatSession
        valid_modes = {key for key, _label in ChatSession.MODE_CHOICES}
        session = None
        if session_id not in (None, ''):
            try:
                session = ChatSession.objects.filter(
                    id=int(session_id), user=user, is_archived=False,
                ).first()
            except (TypeError, ValueError):
                session = None
        if session is None:
            session = ChatSession.objects.create(
                user=user,
                mode=mode if mode in valid_modes else 'tutor',
                title=question[:100],
            )
        ChatMessage.objects.create(session=session, role='user', content=question, mode=mode)
        ChatMessage.objects.create(
            session=session, role='ai', content=answer, mode=mode,
            citations=_clean_citations(citations),
        )
        session.save(update_fields=['updated_at'])
        payload['chat_session_id'] = session.id
    except Exception:
        logger.warning('Chat history write failed', exc_info=True)


def _offline_text_response(request, question: str, *, key: str, reason: str,
                           passages=None, mode: str = None, extra: dict = None) -> Response:
    """Grounded extractive answer under ``key`` (200, labelled offline, free),
    or a 503 ``ai_unavailable`` when nothing in the library matches."""
    try:
        result = compose_offline_answer(question, passages=passages,
                                        user=getattr(request, 'user', None), reason=reason)
    except Exception:
        logger.exception('Offline composer failed')
        result = None
    if result is None or not result.grounded:
        return _ai_unavailable_response(offline=(reason == REASON_OFFLINE_MODE))
    payload = {
        key: result.answer,
        'offline': True,
        'offline_reason': reason,
        'citations': result.citations,
        'charged': False,
    }
    if result.pyq:
        payload['similar_pyq'] = {
            'id': result.pyq['id'], 'year': result.pyq.get('year'),
            'exam_source': result.pyq.get('exam_source'),
        }
    if extra:
        payload.update(extra)
    if mode:
        _record_chat_turn(request, payload, mode=mode, question=question,
                          answer=result.answer, citations=result.citations)
    return Response(payload)


def _run_text_endpoint(request, *, question: str, mode: str, key: str, amount: int,
                       freemium: bool, generate, offline_fallback: bool = True,
                       unavailable_message: str = None) -> Response:
    """Shared flow of the text-answer AI endpoints (tutor, mnemonic, explain,
    analyze): offline mode → free extractive answer; otherwise charge, call
    ``generate(service)``, and on AIUnavailable refund everything and fall
    back to the extractive answer (or a 503).

    ``offline_fallback=False`` (mnemonic): an extract of textbook sentences
    is not what was asked for, so when no model answers the caller gets the
    503 ``ai_unavailable`` (with ``unavailable_message``) instead."""
    def fallback(reason, passages=None):
        if not offline_fallback:
            offline = reason == REASON_OFFLINE_MODE
            message = unavailable_message
            if message and offline:
                message = f'{message} AI generation is switched off (offline mode). You were not charged.'
            elif message:
                message = f'{message} The AI is unavailable right now. You were not charged — please try again in a few minutes.'
            return _ai_unavailable_response(offline=offline, message=message)
        return _offline_text_response(request, question, key=key, reason=reason,
                                      passages=passages, mode=mode)

    if ai_offline_mode():
        return fallback(REASON_OFFLINE_MODE)

    charge_err = _charge_ai_call(request, amount=amount, freemium=freemium)
    if charge_err is not None:
        return charge_err

    try:
        service = AIService()
        text = generate(service)
    except AIUnavailable as exc:
        _refund_ai_call(request, amount=amount)
        reason = REASON_OFFLINE_MODE if exc.offline else REASON_PROVIDERS_DOWN
        return fallback(reason, passages=exc.passages)
    except Exception as e:
        logger.error(f"AI {mode} failed: {e}")
        _refund_ai_call(request, amount=amount)
        return _ai_unavailable_response()

    if not isinstance(text, str) or is_unusable_text(text):
        # Defence in depth: never hand an outage sentence over as an answer.
        _refund_ai_call(request, amount=amount)
        return fallback(REASON_PROVIDERS_DOWN)

    payload = {key: text}
    _record_chat_turn(request, payload, mode=mode, question=question, answer=text)
    return Response(payload)


class AskTutorView(AITutorThrottleMixin, APIView):
    """AI Tutor — RAG-grounded medical Q&A."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question, err = _required_text(request, 'question', 'Question')
        if err:
            return err
        context = _optional_text(request, 'context', MAX_AI_CONTEXT_CHARS)
        # Freemium 2/day cap (subscribers/admin exempt) + 1 token; both are
        # given back if no AI answer is delivered.
        return _run_text_endpoint(
            request, question=question, mode='tutor', key='response', amount=1, freemium=True,
            generate=lambda service: service.ask_tutor(question, context),
        )


class GenerateMnemonicView(AITutorThrottleMixin, APIView):
    """Generate memory tricks for medical topics.

    Only a model can write a mnemonic: when none answers (outage or
    AI_OFFLINE_MODE) this is a free 503 ``ai_unavailable``, never the
    extractive textbook answer (clients saved that, offline notice included,
    as a flashcard "mnemonic")."""

    UNAVAILABLE_MESSAGE = 'A mnemonic needs the AI to write it.'

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        topic, err = _required_text(request, 'topic', 'Topic')
        if err:
            return err
        concept = _optional_text(request, 'concept', MAX_AI_INPUT_CHARS)
        return _run_text_endpoint(
            request, question=f'{topic} {concept}'.strip(), mode='mnemonic', key='mnemonic',
            amount=10, freemium=True,
            generate=lambda service: service.generate_mnemonic(topic, concept),
            offline_fallback=False, unavailable_message=self.UNAVAILABLE_MESSAGE,
        )


class ExplainConceptView(AITutorThrottleMixin, APIView):
    """Explain medical concepts from basics."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        concept, err = _required_text(request, 'concept', 'Concept')
        if err:
            return err
        level = _as_text(request.data.get('level')).lower()
        if level not in ('basic', 'intermediate', 'advanced'):
            level = 'basic'
        return _run_text_endpoint(
            request, question=concept, mode='explain', key='explanation', amount=10, freemium=True,
            generate=lambda service: service.explain_concept(concept, level),
        )


class AnalyzeQuestionView(AITutorThrottleMixin, APIView):
    """Analyze a CMS question — concepts, reasoning, strategy."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        question_text, err = _required_text(request, 'question_text', 'question_text')
        if err:
            return err
        options = _options_param(request.data.get('options'))
        correct_answer = _answer_letter(request.data.get('correct_answer'))
        return _run_text_endpoint(
            request, question=question_text, mode='analyze', key='analysis', amount=10, freemium=True,
            generate=lambda service: service.analyze_question(question_text, options, correct_answer),
        )


# Per-request keys that must never be stored in the shared ai_explanation.
_TRANSIENT_EXPLANATION_KEYS = (
    'is_correct', 'offline', 'offline_reason', 'offline_notice', 'charged', 'cached',
    'chat_session_id',
)
# ExplainQuestionView's markdown answer, kept next to the rich JSON in the
# same ai_explanation (explain-question serves it; explain-answer does not).
_ANALYSIS_KEYS = ('analysis', 'context')


def _parse_stored_json(raw):
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _stored_ai_explanation(q):
    """The question's stored rich explanation if it is a valid one (not
    failed, not an outage sentence, not the markdown shape), else None.
    Its subject labels are the ones students see (rows stored before the
    display rule say "Imported")."""
    data = _parse_stored_json(getattr(q, 'ai_explanation', ''))
    return with_public_subject(dict(data)) if AIService.is_valid_explanation(data) else None


def _stored_analysis_markdown(q):
    """ExplainQuestionView's stored ``{"analysis": md}`` as markdown, if valid."""
    data = _parse_stored_json(getattr(q, 'ai_explanation', ''))
    if not data or data.get('_failed'):
        return None
    analysis = data.get('analysis')
    if not isinstance(analysis, str) or is_unusable_text(analysis):
        return None
    return _stitch_explanation_markdown(data, q)


def _ai_model_label(service) -> str:
    provider = getattr(service, 'last_provider', None)
    return f'roundrobin/{provider}' if provider else 'roundrobin'


def _capture_question_revision(q, user, reason: str) -> None:
    """Revision snapshot of ``q`` (the question editor's history / undo),
    taken with the editor's own helper so the snapshot records the same
    fields (AI explanation and verified state included) and undo restores
    them. Call it before changing any field of ``q``."""
    from questions.views import QuestionViewSet
    QuestionViewSet()._capture_revision_snapshot(q, user, reason=reason)


def _persist_rich_explanation(q, result: dict, service) -> list:
    """Store a validated explanation in the question's EMPTY shared fields.

    Student-triggered calls never overwrite existing content: ai_explanation
    is written only when it is empty or unusable (failed / outage sentence /
    the older markdown-only shape, which the rich shape supersedes), and
    each companion field only when it is empty. Locked explanations are not
    touched, and neither are admin-verified questions: students read the AI
    fields ahead of the curated ones (effective explanation, mnemonic and
    references), so a first AI write would replace the reviewed content
    under the "Verified by Admin" badge (QE-03). The dispute flags compare
    the AI's answer with the STORED key (callers pass DB fields), and only
    on the first stored generation. Returns the names of the fields written.
    """
    if (getattr(q, 'lock_explanation', False) or getattr(q, 'is_verified_by_admin', False)
            or not AIService.is_valid_explanation(result)):
        return []
    data = {k: v for k, v in result.items() if k not in _TRANSIENT_EXPLANATION_KEYS}
    fields = []
    if _stored_ai_explanation(q) is None:
        stored = dict(data)
        if _stored_analysis_markdown(q) is not None:
            # Keep explain-question's markdown (e.g. an admin regeneration)
            # next to the new rich JSON instead of discarding it.
            previous = _parse_stored_json(getattr(q, 'ai_explanation', '')) or {}
            stored.update({k: previous[k] for k in _ANALYSIS_KEYS if k in previous})
        # The question detail payload carries this JSON: student-facing
        # subject labels only (a kept ``context`` may predate the rule).
        q.ai_explanation = json.dumps(with_public_subject(stored), ensure_ascii=False)
        q.ai_generated_at = timezone.now()
        q.ai_model = _ai_model_label(service)
        q.ai_version = 'v2-verify'
        fields += ['ai_explanation', 'ai_generated_at', 'ai_model', 'ai_version']
    for field, value in (
        ('ai_mnemonic', data.get('mnemonic')),
        ('ai_clinical_pearl', data.get('clinical_pearl')),
        ('learning_technique', data.get('exam_tip')),
    ):
        if isinstance(value, str) and value.strip() and not (getattr(q, field, '') or '').strip():
            setattr(q, field, value.strip())
            fields.append(field)
    ref = data.get('textbook_reference')
    if isinstance(ref, dict) and ref.get('book') and not q.ai_references:
        q.ai_references = [ref]
        fields.append('ai_references')
    concepts = data.get('around_concepts')
    if isinstance(concepts, list) and concepts and not q.concept_keywords:
        q.concept_keywords = [str(c)[:200] for c in concepts[:10]]
        fields.append('concept_keywords')

    if 'ai_explanation' in fields:
        ai_verified = _answer_letter(data.get('ai_verified_answer'))
        mismatch = data.get('answer_mismatch')
        mismatch = mismatch is True or _as_text(mismatch).lower() == 'true'
        stored_key = _answer_letter(q.correct_answer)
        if mismatch and ai_verified and stored_key and ai_verified != stored_key:
            q.needs_review = True
            q.is_disputed = True
            fields += ['needs_review', 'is_disputed']
            logger.warning(
                f"ANSWER MISMATCH Q#{q.id}: DB says {stored_key}, AI says {ai_verified}. "
                f"Reason: {_as_text(data.get('confidence_note'))[:200] or 'N/A'}"
            )
    if fields:
        q.save(update_fields=fields + ['updated_at'])
    return fields


def _empty_rich_explanation(subject: str = '', topic: str = '') -> dict:
    return {
        'ai_verified_answer': '', 'answer_mismatch': False, 'confidence_note': '',
        'why_correct': '', 'why_wrong': {},
        'textbook_reference': {'book': '', 'chapter': '', 'page': '', 'section': ''},
        'mnemonic': '', 'core_concept': '', 'topic_deep_dive': '', 'key_differentiators': [],
        'category': public_subject(subject), 'sub_category': topic, 'question_type': '',
        'around_concepts': [], 'high_yield_points': [], 'clinical_pearl': '', 'exam_tip': '',
        'quick_revision': '', 'pyq_frequency': '', 'similar_pyq': '', 'citations': [],
    }


class ExplainAfterAnswerView(AITutorThrottleMixin, APIView):
    """Rich AI explanation after answering a question — textbook refs, mnemonics, related concepts.

    With ``question_id`` (or an exact stem + options match) the prompt is
    built from the question's DB fields — stem, options, answer key, subject,
    topic — never from client-supplied values, and a valid result fills the
    question's empty shared AI fields (not on locked or admin-verified
    questions, see ``_persist_rich_explanation``). Without one (e.g.
    AI-generated practice questions) the client's question is explained but
    nothing is stored and no dispute flag is set.

    A DB question is only explained to users entitled to its answer
    (``_can_view_answer``); anyone else gets the 402 ``upgrade_required``
    envelope before any stored, cached, offline or AI path runs.

    Cost: 10 tokens, charged only when a new explanation is generated (stored
    and cached explanations are free) and refunded when the AI fails.
    """

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        from questions.models import Question

        selected_answer = _answer_letter(request.data.get('selected_answer'))
        db_question = None
        raw_id = request.data.get('question_id')
        if raw_id not in (None, ''):
            try:
                qid = int(raw_id)
            except (TypeError, ValueError):
                return Response({'error': 'question_id must be an integer'}, status=400)
            db_question = Question.objects.select_related('subject', 'topic').filter(id=qid).first()
            if db_question is None:
                return Response({'error': f'Question {qid} not found'}, status=404)
            options = {}
        else:
            question_text, err = _required_text(request, 'question_text', 'question_text')
            if err:
                return err
            options = _options_param(request.data.get('options'))
            db_question = self._exact_match(question_text, options, user=request.user)

        # Paywall: the stored / cached / curated explanation, the DB key
        # behind is_correct and any explanation generated from it reveal the
        # answer of a bank question the caller may not be entitled to.
        if db_question is not None and not _can_view_answer(request.user, db_question):
            return _answer_paywall_response()

        if db_question is not None:
            question_text = db_question.question_text or ''
            options = {
                'A': db_question.option_a or '', 'B': db_question.option_b or '',
                'C': db_question.option_c or '', 'D': db_question.option_d or '',
            }
            correct_answer = _answer_letter(db_question.correct_answer)
            subject = getattr(db_question.subject, 'name', '') if db_question.subject_id else ''
            topic = getattr(db_question.topic, 'name', '') if db_question.topic_id else ''
            qid = db_question.id
        else:
            correct_answer = _answer_letter(request.data.get('correct_answer'))
            subject = _optional_text(request, 'subject', MAX_LABEL_CHARS)
            topic = _optional_text(request, 'topic', MAX_LABEL_CHARS)
            qid = None
        # Ad-hoc questions are cached in their own namespace. Batch jobs
        # cache bank questions under question_id=None too, so a shared key
        # space let a free user who re-typed a bank question (one the exact
        # match missed) probe the cache for its answer key, and let an
        # ad-hoc answer key land in the bank's cache.
        cache_scope = '' if db_question is not None else AIService.ADHOC_CACHE_SCOPE
        is_correct = bool(selected_answer) and selected_answer == correct_answer

        # 1. Stored explanation on the question (free).
        if db_question is not None:
            stored = _stored_ai_explanation(db_question)
            if stored:
                for key in _ANALYSIS_KEYS:
                    stored.pop(key, None)
                stored['is_correct'] = is_correct
                return Response(stored)

        # 2. Shared 24 h cache (free) — checked before charging.
        cached = AIService.get_cached_explanation(question_text, options, correct_answer,
                                                  question_id=qid, cache_scope=cache_scope)
        if cached:
            cached['is_correct'] = is_correct
            return Response(cached)

        if ai_offline_mode():
            return self._offline(request, db_question, question_text, options, correct_answer,
                                 selected_answer, subject, topic, REASON_OFFLINE_MODE)

        ok, err = consume_ai_token(request, amount=10)
        if not ok:
            return err

        try:
            service = AIService()
            result = service.explain_after_answer(
                question_text, options, correct_answer, selected_answer, subject, topic,
                question_id=qid, cache_scope=cache_scope,
            )
        except AIUnavailable as exc:
            refund_ai_token(request, amount=10)
            reason = REASON_OFFLINE_MODE if exc.offline else REASON_PROVIDERS_DOWN
            return self._offline(request, db_question, question_text, options, correct_answer,
                                 selected_answer, subject, topic, reason, passages=exc.passages)
        except Exception as e:
            logger.error(f"ExplainAfterAnswer failed: {e}")
            refund_ai_token(request, amount=10)
            return _ai_unavailable_response()

        with_public_subject(result)
        if db_question is not None:
            try:
                _persist_rich_explanation(db_question, result, service)
            except Exception:
                logger.warning("ExplainAfterAnswer: could not store explanation for Q%s",
                               db_question.id, exc_info=True)
        return Response(result)

    @staticmethod
    def _exact_match(question_text: str, options: dict, user=None):
        """The DB question with exactly this stem and these four options, or
        None. (Matching on the stem alone picked the wrong row for duplicates
        with shuffled options.)

        Every column is compared, empty ones too: an option the client left
        out matches an empty column, so a bank question with a blank option
        is still recognised (and paywalled) instead of being treated as
        ad hoc. When several rows match, one ``user`` may not see wins, so
        an exact duplicate cannot unlock a paywalled question."""
        from questions.models import Question
        if not question_text:
            return None
        rows = list(
            Question.objects.select_related('subject', 'topic')
            .filter(question_text=question_text,
                    option_a=options.get('A', ''), option_b=options.get('B', ''),
                    option_c=options.get('C', ''), option_d=options.get('D', ''))
            .order_by('id')[:5]
        )
        if not rows:
            return None
        for row in rows:
            if not _can_view_answer(user, row):
                return row
        return rows[0]

    @staticmethod
    def _offline(request, db_question, question_text, options, correct_answer, selected_answer,
                 subject, topic, reason, passages=None):
        """Free answer from stored data: the question's curated explanation
        plus textbook sentences; a 503 when neither exists. The curated
        explanation and the DB key are only served to entitled users."""
        payload = None
        if db_question is not None:
            if not _can_view_answer(getattr(request, 'user', None), db_question):
                return _answer_paywall_response()
            payload = stored_rich_explanation(db_question, selected_answer=selected_answer)
        query = question_text
        if correct_answer and options.get(correct_answer):
            query = f"{question_text} {options[correct_answer]}"
        try:
            composed = compose_offline_answer(
                query, passages=passages, user=getattr(request, 'user', None), reason=reason,
                exclude_question_id=getattr(db_question, 'id', None),
            )
        except Exception:
            logger.exception('Offline composer failed')
            composed = None
        grounded = composed is not None and composed.grounded
        if payload is None:
            if not grounded:
                return _ai_unavailable_response(offline=(reason == REASON_OFFLINE_MODE))
            payload = _empty_rich_explanation(subject, topic)
            payload['ai_verified_answer'] = correct_answer
            payload['why_correct'] = '\n'.join(
                f"• {s['text']} [{s['label']}]" for s in composed.sentences
            )
            if composed.pyq:
                payload['similar_pyq'] = pyq_summary(composed.pyq)
                if not payload['why_correct']:
                    payload['why_correct'] = composed.pyq['explanation']
            payload['is_correct'] = bool(selected_answer) and selected_answer == correct_answer
        if grounded:
            payload['citations'] = [
                {'book': c['book'], 'page': c['page'], 'text': c['excerpt']}
                for c in composed.citations
            ]
        payload.update({
            'offline': True,
            'offline_reason': reason,
            'offline_notice': offline_notice(reason),
            'charged': False,
        })
        return Response(payload)


class ExplainQuestionView(AITutorThrottleMixin, APIView):
    """Get an AI explanation for a question by its DB id.

    The frontend player (`NeetPgPlayer.tsx`) calls
    `aiAPI.explainQuestion(questionId, {selected_answer, ...})` and expects
    `{explanation: <markdown>}`. This view:
      1. Loads the Question by id (404 if missing); the prompt is always
         built from its DB fields.
      2. Serves the stored explanation (rich or markdown, validated) for
         free unless the client sent a custom ``prompt`` or
         ``force_regenerate``.
      3. Otherwise calls `AIService.analyze_question(...)` and returns
         the markdown wrapped as `{explanation, cached, question_id}`.

    Only the default (no custom prompt) answer is stored, only into an empty
    or unusable ai_explanation; a custom-prompt answer goes to that user
    alone. Replacing an existing shared explanation (``force_regenerate``)
    is admin-only — a student's regenerate returns a fresh answer without
    storing it. An admin regeneration over a valid rich explain-after-answer
    explanation is stored next to it (``analysis`` key) instead of replacing
    it, so the two explain endpoints stop regenerating each other's work.

    Admin-verified questions (QE-03): students read ai_explanation ahead of
    the curated explanation, under the "Verified by Admin" badge, so only an
    admin's ``force_regenerate`` stores into a verified question, and a
    stored change clears the mark (``verification_cleared``) until an admin
    reviews the text and verifies it again, as the question editor's
    generate-explanation and force-regenerate actions do. Like them, an
    admin regeneration that changes the stored text first takes a revision
    snapshot (the editor's undo restores the earlier text and the mark), and
    the write is a partial save. Every other answer on a verified question
    is served without being stored.

    The prompt carries the DB answer key, so the question is only explained
    to users entitled to its answer (``_can_view_answer``): anyone else gets
    the 402 ``upgrade_required`` envelope, on every path.

    Cost: 10 tokens (admins, staff and unlimited plans bypass). Refunded on
    AI failure.
    """

    def get_permissions(self):
        return _get_permission()

    def post(self, request, question_id: int):
        from questions.models import Question

        q = (
            Question.objects.filter(id=question_id)
            .select_related("subject", "topic")
            .first()
        )
        if not q:
            return Response({'error': f'Question {question_id} not found'}, status=404)
        if not _can_view_answer(request.user, q):
            return _answer_paywall_response()

        client_prompt = _as_text(request.data.get("prompt"))
        if len(client_prompt) > MAX_AI_PROMPT_CHARS:
            return Response(
                {'error': f'prompt is too long (max {MAX_AI_PROMPT_CHARS} characters)'}, status=400,
            )
        force_regen = _as_bool(request.data.get("force_regenerate"))
        user = request.user
        is_admin = bool(getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False))

        if not client_prompt and not force_regen:
            stored = _stored_ai_explanation(q)
            explanation = _stitch_explanation_markdown(stored, q) if stored else _stored_analysis_markdown(q)
            if explanation:
                return Response({
                    'explanation': explanation,
                    'cached': True,
                    'question_id': q.id,
                    'ai_model': q.ai_model,
                    'ai_generated_at': q.ai_generated_at.isoformat() if q.ai_generated_at else None,
                })

        if ai_offline_mode():
            return self._offline(request, q, REASON_OFFLINE_MODE)

        ok, err = consume_ai_token(request, amount=10)
        if not ok:
            return err

        try:
            service = AIService()
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
        except AIUnavailable as exc:
            refund_ai_token(request, amount=10)
            reason = REASON_OFFLINE_MODE if exc.offline else REASON_PROVIDERS_DOWN
            return self._offline(request, q, reason, passages=exc.passages)
        except Exception as e:
            logger.error(f"ExplainQuestion failed for Q{question_id}: {e}")
            refund_ai_token(request, amount=10)
            return _ai_unavailable_response()

        if not isinstance(analysis, str) or is_unusable_text(analysis):
            refund_ai_token(request, amount=10)
            return self._offline(request, q, REASON_PROVIDERS_DOWN)

        ai_model = _ai_model_label(service)
        persisted = False
        verification_cleared = False
        admin_regen = force_regen and is_admin
        if not client_prompt and not q.lock_explanation:
            rich = _stored_ai_explanation(q)
            has_valid = rich is not None or _stored_analysis_markdown(q) is not None
            # A verified question's shared text changes only through an
            # explicit admin regeneration (QE-03, see the docstring).
            if admin_regen or (not has_valid and not q.is_verified_by_admin):
                try:
                    stored = {
                        "analysis": analysis,
                        "context": {
                            # The question detail payload carries this JSON.
                            "subject": public_subject(getattr(q.subject, 'name', '') if q.subject_id else ''),
                            "topic": getattr(q.topic, 'name', '') if q.topic_id else '',
                            "year": q.year,
                            "exam_type": q.exam_type,
                            "exam_source": q.exam_source,
                        },
                    }
                    fields = ["ai_explanation", "ai_model", "ai_generated_at", "updated_at"]
                    if rich is not None:
                        # Keep the rich explain-after-answer JSON (students'
                        # explain-answer serves it) and store the regenerated
                        # markdown next to it; replacing it made the next
                        # explain-answer call pay to regenerate (and overwrite)
                        # the admin's analysis.
                        stored = {**rich, **stored}
                    new_explanation = json.dumps(stored, ensure_ascii=False)
                    text_changed = new_explanation != (q.ai_explanation or '')
                    # QE-03: unreviewed AI text must not sit under an earlier
                    # "Verified by Admin" badge; verify again after review.
                    clear_mark = bool(q.is_verified_by_admin) and text_changed
                    with transaction.atomic():
                        if admin_regen and text_changed:
                            # Before any field changes: the question editor's
                            # undo restores the earlier text and verified
                            # state, as after generate-explanation.
                            _capture_question_revision(q, user, 'Before AI explain-question regenerate')
                        if rich is None:
                            q.ai_version = "explain-question-v1"
                            fields.append("ai_version")
                        if clear_mark:
                            q.is_verified_by_admin = False
                            q.verified_by = None
                            q.verified_at = None
                            fields += ["is_verified_by_admin", "verified_by", "verified_at"]
                        q.ai_explanation = new_explanation
                        q.ai_model = ai_model
                        q.ai_generated_at = timezone.now()
                        q.save(update_fields=fields)
                    persisted = True
                    verification_cleared = clear_mark
                except Exception as save_exc:  # noqa: BLE001
                    logger.warning("ExplainQuestion: cache write failed for Q%s: %s", q.id, save_exc)

        return Response({
            'explanation': analysis,
            'cached': False,
            'question_id': q.id,
            'ai_model': ai_model,
            'persisted': persisted,
            'verification_cleared': verification_cleared,
        })

    @staticmethod
    def _offline(request, q, reason, passages=None):
        """Free markdown answer from the question's curated fields plus
        textbook sentences; a 503 when neither exists. Only for users
        entitled to the question's answer."""
        if not _can_view_answer(getattr(request, 'user', None), q):
            return _answer_paywall_response()
        stored = stored_rich_explanation(q)
        correct = _answer_letter(q.correct_answer)
        query = q.question_text or ''
        if correct:
            query = f"{query} {getattr(q, f'option_{correct.lower()}', '') or ''}"
        try:
            composed = compose_offline_answer(
                query, passages=passages, user=getattr(request, 'user', None), reason=reason,
                exclude_question_id=q.id,
            )
        except Exception:
            logger.exception('Offline composer failed')
            composed = None
        parts = [f'> {offline_notice(reason)}']
        if stored:
            parts.append(_stitch_explanation_markdown(stored, q))
        if composed is not None and composed.grounded:
            parts.append(composed.body)
        if len(parts) == 1:
            return _ai_unavailable_response(offline=(reason == REASON_OFFLINE_MODE))
        return Response({
            'explanation': '\n\n'.join(parts),
            'cached': False,
            'offline': True,
            'offline_reason': reason,
            'question_id': q.id,
            'charged': False,
        })


def _markdown_value(value) -> str:
    """Render a stored explanation value as markdown (dicts/lists used to be
    interpolated as Python reprs)."""
    if isinstance(value, dict):
        lines = []
        for key, val in value.items():
            text = _markdown_value(val)
            if text:
                lines.append(f"- **{key}:** {text}")
        return '\n'.join(lines)
    if isinstance(value, (list, tuple)):
        return '\n'.join(f"- {_markdown_value(v)}" for v in value if _markdown_value(v))
    return _as_text(value)


def _reference_markdown(ref) -> str:
    if isinstance(ref, dict):
        bits = [_as_text(ref.get('book'))]
        if ref.get('chapter'):
            bits.append(f"Chapter: {_as_text(ref['chapter'])}")
        if ref.get('page'):
            bits.append(f"p. {_as_text(ref['page'])}")
        if ref.get('section'):
            bits.append(_as_text(ref['section']))
        return ', '.join(b for b in bits if b)
    if isinstance(ref, list):
        return '; '.join(r for r in (_reference_markdown(x) for x in ref) if r)
    return _as_text(ref)


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
    core = _markdown_value(cached.get("core_concept") or cached.get("ai_verified_answer"))
    if core:
        parts.append(f"**Core concept:** {core}")
    why_correct = _markdown_value(cached.get("why_correct"))
    if why_correct:
        parts.append(f"\n**Why the correct answer is right:**\n{why_correct}")
    why_wrong = _markdown_value(cached.get("why_wrong"))
    if why_wrong:
        parts.append(f"\n**Why other options are wrong:**\n{why_wrong}")
    pearl = _markdown_value(cached.get("clinical_pearl"))
    if pearl:
        parts.append(f"\n**Clinical pearl:** {pearl}")
    high_yield = cached.get("high_yield_points") or []
    if high_yield:
        if isinstance(high_yield, list):
            parts.append("\n**High-yield points:**\n" + _markdown_value(high_yield))
        else:
            parts.append(f"\n**High-yield points:**\n{_markdown_value(high_yield)}")
    mnemonic = _markdown_value(cached.get("mnemonic"))
    if mnemonic:
        parts.append(f"\n**Mnemonic:** {mnemonic}")
    tip = _markdown_value(cached.get("exam_tip"))
    if tip:
        parts.append(f"\n**Exam tip:** {tip}")
    ref = _reference_markdown(cached.get("textbook_reference"))
    if ref:
        parts.append(f"\n**Textbook reference:** {ref}")
    if not parts:
        # Last resort: if the cached dict has no known keys, dump as JSON
        # so we at least surface *something* (shouldn't normally happen).
        parts.append(json.dumps(with_public_subject(dict(cached)), indent=2, ensure_ascii=False))
    return "\n".join(parts)


class RAGSearchView(AITutorThrottleMixin, APIView):
    """Search across indexed textbooks (raw passages) — admin only.

    It returns passage text from the indexed store, which includes
    copyrighted textbooks, so it is not a student endpoint (no student UI
    calls it; students get cited answers from rag-answer). Results are
    capped at 10 and each passage at RAG_SEARCH_EXCERPT_CHARS characters.
    """

    RAG_SEARCH_EXCERPT_CHARS = 600

    def get_permissions(self):
        return _get_admin_permission()

    def post(self, request):
        query, err = _required_text(request, 'query', 'Query', max_chars=1000)
        if err:
            return err
        book_filter = _as_text(request.data.get('book')) or None
        try:
            n_results = max(1, min(int(request.data.get('n_results', 5)), 10))
        except (TypeError, ValueError):
            return Response({'error': 'n_results must be an integer'}, status=400)

        try:
            service = AIService()
            results = service.rag_search(query, book_filter, n_results)
            if isinstance(results, dict):
                for item in results.get('results') or []:
                    if isinstance(item, dict) and isinstance(item.get('text'), str):
                        item['text'] = item['text'][:self.RAG_SEARCH_EXCERPT_CHARS]
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
        question, err = _required_text(request, 'question', 'Question')
        if err:
            return err

        if ai_offline_mode():
            return _offline_text_response(request, question, key='answer', reason=REASON_OFFLINE_MODE,
                                          mode='textbook', extra={'confidence': 'offline'})

        charge_err = _charge_ai_call(request, amount=1, freemium=True)
        if charge_err is not None:
            return charge_err

        try:
            service = AIService()
            result = service.rag_answer(question)
        except AIUnavailable as exc:
            _refund_ai_call(request, amount=1)
            reason = REASON_OFFLINE_MODE if exc.offline else REASON_PROVIDERS_DOWN
            return _offline_text_response(request, question, key='answer', reason=reason,
                                          passages=exc.passages, mode='textbook',
                                          extra={'confidence': 'offline'})
        except Exception as e:
            logger.error(f"RAGAnswer failed: {e}")
            _refund_ai_call(request, amount=1)
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

        if not isinstance(result, dict):
            result = {'answer': _as_text(result), 'citations': []}
        # The textbook store cannot be searched (RAG disabled / store missing;
        # the legacy payload leaked an operator command). Give back the token
        # AND the freemium slot: the client falls back to AI Tutor mode, which
        # then costs exactly one message instead of two.
        if (
            result.get('error') == 'textbook_search_unavailable'
            or 'RAG pipeline not initialized' in str(result.get('answer', ''))
        ):
            logger.warning("Textbook-mode answer requested but RAG is unavailable")
            _refund_ai_call(request, amount=1)
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
        # Nothing in the textbooks matched: no AI call was made, so it is free.
        if result.get('no_match'):
            _refund_ai_call(request, amount=1)
            result['charged'] = False
            return Response(result)
        answer = result.get('answer')
        if not isinstance(answer, str) or is_unusable_text(answer):
            _refund_ai_call(request, amount=1)
            return _offline_text_response(request, question, key='answer', reason=REASON_PROVIDERS_DOWN,
                                          mode='textbook', extra={'confidence': 'offline'})
        _record_chat_turn(request, result, mode='textbook', question=question,
                          answer=answer, citations=result.get('citations'))
        return Response(result)


def _snippet(text, limit: int) -> str:
    """``text`` cut to ``limit`` characters at a word boundary (with an
    ellipsis when cut)."""
    text = _as_text(text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return (cut[: cut.rfind(' ')] if ' ' in cut else cut).rstrip(' ,;:') + '…'


class TextbookReferenceView(AITutorThrottleMixin, APIView):
    """Find textbook references (book + page) for a question or topic.

    Auth required even in DEBUG: textbook-reference lookups drive real
    RAG cost and must not be reachable by anonymous callers.

    The call is free and the store holds copyrighted textbooks, so each
    reference carries only a short locating snippet
    (REFERENCE_EXCERPT_CHARS), not a passage — three 300-character excerpts
    per call made it a bulk-extraction path once rag-search went admin-only.

    Textbook references are part of a bank question's explanation (the
    question bank's "Find in Textbook" card sends the stem; the bank redacts
    a question's references for callers who may not see its answer), so the
    exact stem of a question the caller is not entitled to
    (``_can_view_answer``) gets the 402 ``upgrade_required`` envelope.
    """

    MAX_REFERENCES = 3
    REFERENCE_EXCERPT_CHARS = 160

    def get_permissions(self):
        return [IsAuthenticated()]

    @staticmethod
    def _locked_bank_stem(user, question_text: str) -> bool:
        """True when ``question_text`` is the stem of a bank question
        ``user`` may not see the answer of."""
        from questions.models import Question
        rows = (Question.objects.filter(question_text=question_text)
                .only('id', 'is_scholarship_eligible').order_by('id')[:5])
        return any(not _can_view_answer(user, row) for row in rows)

    def post(self, request):
        question_text, err = _required_text(request, 'question_text', 'question_text')
        if err:
            return err
        if self._locked_bank_stem(request.user, question_text):
            return _answer_paywall_response()

        service = AIService()
        references = []
        for ref in (service.find_textbook_reference(question_text) or [])[:self.MAX_REFERENCES]:
            if not isinstance(ref, dict):
                continue
            ref = dict(ref)
            if 'excerpt' in ref:
                ref['excerpt'] = _snippet(ref.get('excerpt'), self.REFERENCE_EXCERPT_CHARS)
            references.append(ref)
        return Response({'references': references})


class StudyPlanView(AITutorThrottleMixin, APIView):
    """Generate personalized study plan (10 tokens, refunded on AI failure)."""

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        raw_topics = request.data.get('weak_topics', [])
        if isinstance(raw_topics, str):
            raw_topics = [raw_topics]
        if not isinstance(raw_topics, (list, tuple)):
            return Response({'error': 'weak_topics must be a list'}, status=400)
        weak_topics = [t for t in (_as_text(x)[:MAX_LABEL_CHARS] for x in raw_topics[:30]) if t]
        try:
            days_remaining = max(1, min(int(request.data.get('days_remaining', 60)), 730))
        except (TypeError, ValueError):
            return Response({'error': 'days_remaining must be an integer'}, status=400)
        user_analytics = request.data.get('analytics', None)
        if user_analytics is not None:
            if not isinstance(user_analytics, dict) or len(json.dumps(user_analytics, default=str)) > MAX_AI_INPUT_CHARS:
                user_analytics = None

        if ai_offline_mode():
            # A personal plan cannot be extracted from stored text.
            return _ai_unavailable_response(offline=True)

        ok, err = consume_ai_token(request, amount=10)
        if not ok:
            return err

        try:
            service = AIService()
            plan = service.generate_study_plan(weak_topics, days_remaining, user_analytics)
        except AIUnavailable as exc:
            refund_ai_token(request, amount=10)
            return _ai_unavailable_response(offline=exc.offline)
        except Exception as e:
            logger.error(f"StudyPlan failed: {e}")
            refund_ai_token(request, amount=10)
            return _ai_unavailable_response()
        return Response({'study_plan': plan})


HIGH_YIELD_CACHE_SECONDS = 24 * 3600
HIGH_YIELD_FALLBACK_CACHE_SECONDS = 3600


def _question_bank_high_yield(subject: str, reason: str):
    """High-yield list from the question bank itself (PYQ frequency per topic),
    in the markdown shape the roadmap page parses. None when the bank has no
    topic-tagged CMS questions."""
    from django.db.models import Count
    from questions.models import Question

    qs = Question.objects.filter(is_active=True, exam_type='cms', topic__isnull=False)
    if subject:
        qs = qs.filter(subject__name__icontains=subject)
    rows = list(
        qs.values('subject__name', 'topic__name')
        .annotate(n=Count('id'), years=Count('year', distinct=True))
        .order_by('subject__name', '-years', '-n')
    )
    if not rows:
        return None
    by_subject: dict = {}
    for row in rows:
        # Grouped by the label students see, so the loader's "Imported" and
        # an "Expert Curated" subject form one section.
        by_subject.setdefault(public_subject(row['subject__name']) or 'General', []).append(row)
    lines = [f'> {offline_notice(reason)} Ranked by how often each topic appeared in past CMS papers.', '']
    for name, topics in by_subject.items():
        lines.append(f'## {name}')
        # Re-ranked across the subjects of a merged section (stable: a single
        # subject keeps the query's order).
        topics = sorted(topics, key=lambda row: (-row['years'], -row['n']))
        for i, row in enumerate(topics[:10], 1):
            stars = '★★★' if row['years'] >= 4 else ('★★' if row['years'] >= 2 else '★')
            lines.append(f"{i}. **{row['topic__name']}** ({row['n']} PYQs in {row['years']} years) ({stars})")
        lines.append('')
    return '\n'.join(lines).strip()


def _public_subject_headings(markdown):
    """High-yield markdown with every ``## <subject>`` heading as students
    see it (``public_subject``): a list cached before the display rule can
    still say ``## Imported``. Anything that is not text is returned as is."""
    if not isinstance(markdown, str):
        return markdown
    lines = markdown.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('## '):
            label = public_subject(line[3:])
            if label != line[3:]:
                lines[i] = f'## {label}'
    return '\n'.join(lines)


class HighYieldTopicsView(AITutorThrottleMixin, APIView):
    """Get AI-predicted high-yield topics for CMS exam.

    The prediction prompt is the same for every user, so the result is cached
    for 24 h per subject (``?subject=`` optional) and served free. Only a cache
    miss calls the AI, for 1 token (refunded on failure). When the AI is
    unavailable or offline mode is on, the topics are ranked from the question
    bank's own PYQ frequencies instead (free, cached for an hour).
    """

    def get_permissions(self):
        return _get_permission()

    def get(self, request):
        subject = _as_text(request.query_params.get('subject'))[:60]
        cache_key = 'ai_high_yield_v1:' + (
            hashlib.sha256(subject.lower().encode('utf-8')).hexdigest()[:16] if subject else 'all'
        )
        try:
            cached = cache.get(cache_key)
        except Exception:
            cached = None
        if isinstance(cached, dict) and cached.get('predictions'):
            return Response({**cached, 'predictions': _public_subject_headings(cached['predictions']),
                             'cached': True})

        if ai_offline_mode():
            return self._from_question_bank(subject, cache_key, REASON_OFFLINE_MODE)

        ok, err = consume_ai_token(request, amount=1)
        if not ok:
            return err
        try:
            service = AIService()
            predictions = service.predict_high_yield_topics(subject)
        except AIUnavailable as exc:
            refund_ai_token(request, amount=1)
            return self._from_question_bank(
                subject, cache_key, REASON_OFFLINE_MODE if exc.offline else REASON_PROVIDERS_DOWN,
            )
        except Exception as e:
            logger.error(f"HighYield failed: {e}")
            refund_ai_token(request, amount=1)
            return _ai_unavailable_response()

        payload = {
            'predictions': _public_subject_headings(predictions),
            'subject': subject or None,
            'generated_at': timezone.now().isoformat(),
        }
        try:
            cache.set(cache_key, payload, timeout=HIGH_YIELD_CACHE_SECONDS)
        except Exception:
            logger.debug('HighYield cache write failed', exc_info=True)
        return Response({**payload, 'cached': False})

    @staticmethod
    def _from_question_bank(subject: str, cache_key: str, reason: str):
        try:
            markdown = _question_bank_high_yield(subject, reason)
        except Exception:
            logger.exception('HighYield question-bank fallback failed')
            markdown = None
        if not markdown:
            return _ai_unavailable_response(offline=(reason == REASON_OFFLINE_MODE))
        payload = {
            'predictions': markdown,
            'subject': subject or None,
            'offline': True,
            'offline_reason': reason,
            'generated_at': timezone.now().isoformat(),
        }
        try:
            cache.set(cache_key, payload, timeout=HIGH_YIELD_FALLBACK_CACHE_SECONDS)
        except Exception:
            logger.debug('HighYield cache write failed', exc_info=True)
        return Response({**payload, 'cached': False, 'charged': False})


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
    """Get AI knowledge base statistics (indexed book names). Admin only —
    the only UI using it is the admin upload page."""

    def get_permissions(self):
        return _get_admin_permission()

    def get(self, request):
        from .auto_ingest import AutoIngestService

        ingest = AutoIngestService()
        stats = ingest.get_knowledge_stats()
        return Response(stats)


class GenerateQuestionsView(AITutorThrottleMixin, APIView):
    """AI-generated practice MCQs for weak topics.

    Cost: 10 tokens per generation (any count), refunded when the AI fails or
    returns no valid question. Raw model output is never returned.
    """

    GENERATION_COST = 10

    def get_permissions(self):
        return _get_permission()

    def post(self, request):
        subject, err = _required_text(request, 'subject', 'Subject', max_chars=MAX_LABEL_CHARS)
        if err:
            return err
        topic = _optional_text(request, 'topic', MAX_LABEL_CHARS)
        difficulty = _as_text(request.data.get('difficulty')).lower() or 'medium'
        if difficulty not in ('easy', 'medium', 'hard'):
            difficulty = 'medium'
        try:
            count = max(1, min(int(request.data.get('count', 5)), 20))
        except (TypeError, ValueError):
            return Response({'error': 'count must be an integer'}, status=400)

        if ai_offline_mode():
            return _ai_unavailable_response(
                offline=True,
                message='Question generation needs the AI, which is switched off (offline mode). '
                        'You were not charged.',
            )

        ok, err = consume_ai_token(request, amount=self.GENERATION_COST)
        if not ok:
            return err

        try:
            service = AIService()
            questions = service.generate_questions(subject, topic, difficulty, count)
        except AIUnavailable as exc:
            refund_ai_token(request, amount=self.GENERATION_COST)
            return _ai_unavailable_response(
                offline=exc.offline,
                message='The AI could not generate valid questions right now. '
                        'You were not charged — please try again.',
            )
        except Exception as e:
            logger.error(f"GenerateQuestions failed: {e}")
            refund_ai_token(request, amount=self.GENERATION_COST)
            return _ai_unavailable_response()
        return Response({'questions': questions, 'count': len(questions), 'cost': self.GENERATION_COST})


class PageScreenshotView(AITutorThrottleMixin, APIView):
    """The textbook page a question cites, as ``{screenshot_url}``.

    The page shows where (and often what) the answer is, so it is served
    only to users entitled to the question's answer (``_can_view_answer``,
    the rule the question bank applies when it redacts ``page_screenshot``);
    anyone else gets the 402 ``upgrade_required`` envelope before any stored
    URL, cache or render step runs.

    The first successful render is saved to ``question.page_screenshot`` (the
    question detail payload then carries it too) and served from there while
    its file exists; a failed lookup is remembered for MISS_CACHE_SECONDS,
    and only one render per question runs at a time, so repeated clicks
    neither rescan the textbook folders nor re-render a 200-DPI page. Only
    URLs are returned -- never a server filesystem path (the old
    ``screenshot_path``).
    """

    MISS_CACHE_SECONDS = 3600
    RENDER_LOCK_SECONDS = 120

    def get_permissions(self):
        return _get_permission()

    def get(self, request, question_id):
        from questions.models import Question

        question = Question.objects.filter(id=question_id).first()
        if question is None:
            return Response({'error': 'Question not found'}, status=404)
        if not _can_view_answer(request.user, question):
            return _answer_paywall_response()

        stored = self._stored_url(question)
        if stored:
            return Response({'screenshot_url': self._absolute(request, stored)})

        miss_key = f'ai_page_screenshot_miss_v1:{question.id}'
        lock_key = f'ai_page_screenshot_lock_v1:{question.id}'
        locked = None
        try:
            if cache.get(miss_key):
                return Response({'error': 'No screenshot available'}, status=404)
            # True: this request holds the render lock. False: another
            # request is rendering. None: the cache is down (django_redis
            # with IGNORE_EXCEPTIONS answers None instead of raising) --
            # render without a lock rather than answering 'rendering'
            # forever while Redis is unavailable.
            locked = cache.add(lock_key, 1, timeout=self.RENDER_LOCK_SECONDS)
        except Exception:
            logger.debug('Page screenshot cache unavailable', exc_info=True)
            locked = None
        if locked is False:
            return Response({'status': 'rendering'}, status=202)
        try:
            url = self._render_and_store(question)
        finally:
            if locked:
                try:
                    cache.delete(lock_key)
                except Exception:
                    pass
        if not url:
            try:
                cache.set(miss_key, True, timeout=self.MISS_CACHE_SECONDS)
            except Exception:
                pass
            return Response({'error': 'No screenshot available'}, status=404)
        return Response({'screenshot_url': self._absolute(request, url)})

    @staticmethod
    def _stored_url(question) -> str:
        """URL of the stored render, or '' when there is none or its file is
        gone (media on an ephemeral disk does not survive a redeploy): the
        page is then rendered again instead of serving a broken image."""
        field = question.page_screenshot
        if not field:
            return ''
        try:
            if not field.storage.exists(field.name):
                return ''
            return field.url
        except Exception:
            return ''

    @staticmethod
    def _absolute(request, url: str) -> str:
        """Absolute URL, like the detail serializer's ``page_screenshot``."""
        if url.startswith(('http://', 'https://')):
            return url
        return request.build_absolute_uri(url)

    @staticmethod
    def _page_index(page_number):
        """0-based page index from '123' / '123-125' / 'p. 123', or None."""
        import re
        match = re.search(r'\d+', str(page_number or ''))
        if not match:
            return None
        page = int(match.group(0))
        return page - 1 if page >= 1 else None

    @staticmethod
    def _find_pdf(book_name: str):
        train_dir = str(getattr(django_settings, 'MEDURA_TRAIN_DIR', '') or '')
        needle = (book_name or '').strip().lower()
        if not train_dir or not needle:
            return None
        for tb_dir in (os.path.join(train_dir, 'textbooks'), train_dir):
            if not os.path.isdir(tb_dir):
                continue
            for name in sorted(os.listdir(tb_dir)):
                if name.lower().endswith('.pdf') and needle in name.lower():
                    return os.path.join(tb_dir, name)
        return None

    def _render_and_store(self, question):
        """Render the cited page into ``question.page_screenshot``; its URL,
        or None when there is no reference, PDF or page, or the lookup or
        render fails (an unreadable textbook folder is a 404, not a 500)."""
        import tempfile
        from django.core.files import File

        try:
            from .document_processor import DocumentProcessor

            page_index = self._page_index(question.page_number)
            if page_index is None:
                return None
            pdf_path = self._find_pdf(question.book_name)
            if not pdf_path:
                return None
            with tempfile.TemporaryDirectory(prefix='page-shot-') as tmp:
                output = DocumentProcessor.extract_page_image(pdf_path, page_index, tmp)
                if not output or not os.path.isfile(output):
                    return None
                with open(output, 'rb') as fh:
                    question.page_screenshot.save(
                        f'q{question.id}_{os.path.basename(output)}', File(fh), save=False,
                    )
            question.save(update_fields=['page_screenshot', 'updated_at'])
            return question.page_screenshot.url
        except Exception:
            logger.exception('Page screenshot render failed for Q%s', question.id)
            return None


class KnowledgeHealthView(APIView):
    """Admin-only, read-only health of the textbook search store
    (ported from feat/ai-production-unification; see ai_engine/rag_health.py)."""

    def get_permissions(self):
        return _get_admin_permission()

    def get(self, request):
        from .rag_health import rag_store_health

        report = rag_store_health()
        report.pop('path', None)  # don't expose server paths
        return Response(report)


class AIStatusView(APIView):
    """Check which AI providers are initialized (admin-only in production)."""
    permission_classes = property(lambda self: _get_admin_permission())

    def get_permissions(self):
        return _get_admin_permission()

    def get(self, request):
        try:
            service = AIService()
            # Exactly the entries of the _call_ai() rotation, so the
            # operator's "is the AI healthy?" view matches the code path.
            # (NVIDIA Mistral is implemented but not in the rotation.)
            providers = {
                'omniroute': service.omniroute is not None,
                'groq': service.groq is not None,
                'cerebras': service.cerebras is not None,
                'gemini': service.gemini_client is not None,
                'cohere': service.cohere is not None,
                'openrouter': service.openrouter is not None,
                'github_models': service.github_models is not None,
                'huggingface': service.huggingface is not None,
                'mistral': service.mistral is not None,
                'openrouter2': service.openrouter2 is not None,
            }
        except Exception as e:
            logger.error(f"AIService init failed: {e}")
            providers = {'error': 'AI service failed to initialise; see server logs'}
        keys_present = {
            'OMNIROUTE_API_KEY': bool(getattr(django_settings, 'OMNIROUTE_API_KEY', '') or os.getenv('OMNIROUTE_API_KEY', '')),
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
            'offline_mode': ai_offline_mode(),
        })


class AITestView(APIView):
    """Quick AI ping — tests if any provider can respond (admin-only in production)."""

    def get_permissions(self):
        return _get_admin_permission()

    def get(self, request):
        try:
            service = AIService()
            result = service._call_ai("Reply with exactly: OK", system="You are a test bot. Reply with one word only.", temperature=0, max_tokens=10)
            return Response({'status': 'ok', 'response': result[:100], 'provider': service.last_provider})
        except AIUnavailable as exc:
            return Response(
                {'status': 'error', 'code': 'ai_unavailable', 'offline': exc.offline,
                 'error': 'No AI provider answered' if not exc.offline else 'AI_OFFLINE_MODE is on'},
                status=503,
            )
        except Exception as e:
            logger.error(f"AI test failed: {e}")
            return Response({'status': 'error', 'error': 'AI test failed; see server logs'}, status=500)


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
    # The list is capped at the 50 most recent sessions, so it is returned as
    # a plain array (the AI Tutor history panel expects a list).
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Count, OuterRef, Subquery
        try:
            last_message = (
                ChatMessage.objects.filter(session=OuterRef('pk'))
                .order_by('-created_at', '-id')
                .values('content')[:1]
            )
            # message_count / last preview annotated in the one query instead
            # of two extra queries per session in the serializer.
            return ChatSession.objects.filter(
                user=self.request.user,
                is_archived=False
            ).annotate(
                message_count_value=Count('messages'),
                last_message_content=Subquery(last_message),
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

        role = _as_text(request.data.get('role')) or 'user'
        content = _as_text(request.data.get('content'))
        mode = _as_text(request.data.get('mode'))
        citations = request.data.get('citations', [])

        if role not in {key for key, _label in ChatMessage.ROLE_CHOICES}:
            return Response({'error': "role must be 'user' or 'ai'"}, status=400)
        if mode and mode not in {key for key, _label in ChatSession.MODE_CHOICES}:
            return Response({'error': 'unknown mode'}, status=400)
        if not content:
            return Response({'error': 'Content is required'}, status=400)
        if len(content) > 20000:
            return Response({'error': 'content is too long (max 20000 characters)'}, status=400)

        message = ChatMessage.objects.create(
            session=session,
            role=role,
            content=content,
            mode=mode,
            citations=_clean_citations(citations),
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
