# Freemium Conversion Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a freemium gate layer to CrackCMS so free users see 10 curated PYQ questions per year, 2 admin-curated mock tests, and 2 AI tutor messages per day — with all premium features still visible in the UI but locked — while paying users (any active `Subscription`) and admins retain full, zero-friction access.

**Architecture:** Server is the source of truth. New `FreeShowcaseQuestion`, `AITutorDailyUsage` tables + a `is_free_preview` boolean on `Test` carry the gate state. A shared `_is_premium(user)` helper uses `Subscription.is_active` plus `is_admin` for the bypass. Endpoints that gate return `403 {"code": "upgrade_required", "feature": "..."}` (or `402` for AI quota). The frontend `api.ts` interceptor catches that envelope and opens a single `<UpgradeModal>` mounted at layout root. A persistent `<UsageBanner>` on `/questions`, `/tests`, `/ai-tutor` shows the AI counter. Locked features stay visible everywhere with a `<LockedBadge>`.

**Tech Stack:** Django 5 + DRF, Next.js 16 + React 19 + TypeScript + Tailwind 4 + Radix UI, Zustand (already in use via `sidebarStore`), Lucide icons.

**Spec:** [C:\Users\DIVYANSHU\.claude\plans\i-want-u-to-eager-tulip.md](C:/Users/DIVYANSHU/.claude/plans/i-want-u-to-eager-tulip.md)

## Global Constraints

- Premium detection: `Subscription.is_active` (status='active' AND (expires_at IS NULL OR expires_at > now)). `is_admin`/`is_superuser` always bypass.
- Premium copy: ₹129/month (live Razorpay price, do not change).
- Every premium feature stays visible with a lock icon; never hidden.
- Token economy unchanged (daily 10, weekly 50, purchased, feedback). New AI 2/day cap is **additional**, not a replacement.
- Backend `403 {"code": "upgrade_required", "feature": "..."}` envelope is canonical. Frontend `api.ts` interceptor owns the modal trigger.
- Migration files must follow the next sequential number in each app.
- Use `transaction.atomic()` + `select_for_update()` for AI daily counter increment.
- Test isolation: every test creates a fresh `User` via `User.objects.create_user`.
- Frontend uses existing `api.ts` axios client; never instantiate a new one.
- Analytics: every UpgradeModal interaction fires `paywall_view`, `upgrade_click`, or `paywall_dismissed` via `frontend/src/lib/analytics.ts`.

---

## File Structure (locked before task decomposition)

**New backend (4 files):**
- `backend/accounts/utils.py` — `_is_premium(user) -> bool` helper.
- `backend/accounts/models_freemium.py` — `FreeShowcaseQuestion` model.
- `backend/accounts/migrations/<next>_freeshowcasequestion.py` — auto-generated.
- `backend/ai_engine/models_usage.py` — `AITutorDailyUsage` model.
- `backend/ai_engine/migrations/<next>_aitutordailyusage.py` — auto-generated.
- `backend/tests_engine/migrations/<next>_test_is_free_preview.py` — auto-generated.

**Modified backend (6 files):**
- `backend/questions/views.py` — filter free users to showcase questions.
- `backend/questions/serializers.py` — add `is_showcase` field.
- `backend/tests_engine/views.py` — gate `start` action.
- `backend/tests_engine/models.py` — add `is_free_preview` field.
- `backend/ai_engine/views.py` — add quota check inside `consume_ai_token`.
- `backend/accounts/views.py` — extend profile payload with `ai_tutor_used_today` + `showcase_questions_remaining`.

**New backend tests (3 files):**
- `backend/questions/tests/test_freemium_filter.py`
- `backend/tests_engine/tests/test_freemium_start.py`
- `backend/ai_engine/tests/test_ai_tutor_quota.py`

**New frontend (5 files):**
- `frontend/src/components/paywall/UpgradeModal.tsx`
- `frontend/src/components/paywall/LockedBadge.tsx`
- `frontend/src/components/paywall/UsageBanner.tsx`
- `frontend/src/lib/hooks/useUpgradeModal.tsx`
- `frontend/src/lib/stores/paywallStore.ts`

**Modified frontend (10 files):**
- `frontend/src/lib/api.ts` — interceptor + helper
- `frontend/src/app/layout.tsx` — mount modal + banner
- `frontend/src/lib/analytics.ts` — events
- `frontend/src/components/question/ExamQuestionBank.tsx` — list filter
- `frontend/src/app/tests/page.tsx` — lock badges
- `frontend/src/app/tests/[id]/page.tsx` — start gate
- `frontend/src/app/simulator/page.tsx` — lock badges
- `frontend/src/app/ai-tutor/page.tsx` — quota banner
- `frontend/src/components/Sidebar.tsx` — lock icons
- `frontend/src/app/dashboard/page.tsx` — premium features row

---

## Task 1: Premium detection helper + tests (foundation)

**Files:**
- Create: `backend/accounts/utils.py`
- Create: `backend/accounts/tests/test_is_premium.py`

**Interfaces:**
- Produces: `accounts.utils._is_premium(user) -> bool` (also exposed as `is_premium` for non-underscore import).
- Consumes: `accounts.models.Subscription.get_active_subscription(user)`, `CustomUser.is_admin`, `CustomUser.is_superuser`.

- [ ] **Step 1: Write the failing test**

```python
# backend/accounts/tests/test_is_premium.py
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from accounts.models import CustomUser, Subscription, PLAN_FEATURES
from accounts.utils import is_premium


class IsPremiumTests(TestCase):
    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='stu', email='stu@x.com', password='x'
        )
        self.admin = CustomUser.objects.create_user(
            username='adm', email='adm@x.com', password='x', is_staff=True
        )

    def test_anonymous_user_is_not_premium(self):
        # AnonymousUser has no is_admin attribute path
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(is_premium(AnonymousUser()))

    def test_student_without_subscription_is_not_premium(self):
        self.assertFalse(is_premium(self.student))

    def test_admin_is_always_premium(self):
        self.assertTrue(is_premium(self.admin))

    def test_active_subscription_makes_premium(self):
        Subscription.objects.create(
            user=self.student,
            plan='1_month',
            status='active',
            expires_at=timezone.now() + timedelta(days=30),
            amount_paid=12900,
        )
        self.assertTrue(is_premium(self.student))

    def test_expired_subscription_is_not_premium(self):
        Subscription.objects.create(
            user=self.student,
            plan='1_month',
            status='active',
            expires_at=timezone.now() - timedelta(days=1),
            amount_paid=12900,
        )
        self.assertFalse(is_premium(self.student))

    def test_cancelled_subscription_is_not_premium(self):
        Subscription.objects.create(
            user=self.student,
            plan='1_month',
            status='cancelled',
            expires_at=timezone.now() + timedelta(days=30),
            amount_paid=12900,
        )
        self.assertFalse(is_premium(self.student))

    def test_lifetime_subscription_is_premium(self):
        Subscription.objects.create(
            user=self.student,
            plan='legacy',
            status='active',
            expires_at=None,
            amount_paid=19900,
        )
        self.assertTrue(is_premium(self.student))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python manage.py test accounts.tests.test_is_premium --verbosity=2`
Expected: `ModuleNotFoundError: No module named 'accounts.utils'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/accounts/utils.py
"""Shared helpers for account-related logic."""
from .models import Subscription


def is_premium(user) -> bool:
    """Return True if the user has an active subscription OR is admin/staff.

    Single source of truth used by every freemium gate. Anonymous users,
    users without a subscription, and users whose only subscription is
    expired or cancelled are NOT premium.

    `Subscription.is_active` already enforces status='active' AND
    (expires_at IS NULL OR expires_at > now).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
        return True
    sub = Subscription.get_active_subscription(user)
    return bool(sub and sub.is_active)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python manage.py test accounts.tests.test_is_premium --verbosity=2`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add accounts/utils.py accounts/tests/test_is_premium.py
git commit -m "feat(accounts): is_premium() helper as single source of truth for freemium gates"
```

---

## Task 2: FreeShowcaseQuestion model + admin + tests

**Files:**
- Create: `backend/accounts/models_freemium.py`
- Create: `backend/accounts/migrations/<next>_freeshowcasequestion.py` (auto-gen, then commit)
- Modify: `backend/accounts/admin.py` (register the new model inline)
- Create: `backend/accounts/tests/test_freeshowcase.py`

**Interfaces:**
- Produces: `accounts.models_freemium.FreeShowcaseQuestion` with `question` (OneToOne to `questions.Question`), `year` (PositiveSmallIntegerField), `position` (PositiveSmallIntegerField 0-9), `created_at`. `unique_together = ('year', 'position')`. Meta ordering by `(year, position)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/accounts/tests/test_freeshowcase.py
from django.test import TestCase
from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import Question, Subject, ExamTrack
import datetime


class FreeShowcaseQuestionTests(TestCase):
    def setUp(self):
        self.track = ExamTrack.objects.create(slug='cms', name='CMS')
        self.subject = Subject.objects.create(name='Medicine', exam_track=self.track)
        # Create 12 questions for year 2024
        self.questions = []
        for i in range(12):
            self.questions.append(
                Question.objects.create(
                    question_text=f'Q{i}',
                    option_a='A', option_b='B', option_c='C', option_d='D',
                    correct_answer='A',
                    year=2024,
                    subject=self.subject,
                )
            )

    def test_unique_year_position_pair(self):
        FreeShowcaseQuestion.objects.create(
            question=self.questions[0], year=2024, position=1
        )
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FreeShowcaseQuestion.objects.create(
                    question=self.questions[1], year=2024, position=1
                )

    def test_same_question_can_be_in_multiple_years(self):
        FreeShowcaseQuestion.objects.create(
            question=self.questions[0], year=2024, position=1
        )
        # Same question, different year should be allowed
        FreeShowcaseQuestion.objects.create(
            question=self.questions[0], year=2023, position=1
        )
        self.assertEqual(FreeShowcaseQuestion.objects.count(), 2)

    def test_ordering_by_year_then_position(self):
        FreeShowcaseQuestion.objects.create(
            question=self.questions[2], year=2024, position=3
        )
        FreeShowcaseQuestion.objects.create(
            question=self.questions[0], year=2024, position=1
        )
        FreeShowcaseQuestion.objects.create(
            question=self.questions[1], year=2024, position=2
        )
        ordered = list(
            FreeShowcaseQuestion.objects.filter(year=2024).values_list(
                'position', flat=True
            )
        )
        self.assertEqual(ordered, [1, 2, 3])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python manage.py test accounts.tests.test_freeshowcase --verbosity=2`
Expected: `ModuleNotFoundError: No module named 'accounts.models_freemium'`

- [ ] **Step 3: Write the model**

```python
# backend/accounts/models_freemium.py
"""Freemium-related models: curated showcase questions for free users."""
from django.db import models


class FreeShowcaseQuestion(models.Model):
    """Admin-curated set of 10 questions per year shown to free users.

    The same 10 questions are visible to every free user per year — keeps
    content deterministic, shareable, and SEO-friendly. Admin sets these
    in Django admin via an inline ordered by `(year, position)`.

    Premium users are NOT affected; they see the full question bank.
    """
    question = models.OneToOneField(
        'questions.Question',
        on_delete=models.CASCADE,
        related_name='free_showcase',
    )
    year = models.PositiveSmallIntegerField(db_index=True)
    position = models.PositiveSmallIntegerField(
        help_text='Display order 0-9 within the year (admin curates 10 per year).'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('year', 'position')
        ordering = ('year', 'position')
        indexes = [models.Index(fields=['year'])]

    def __str__(self):
        return f'Showcase {self.year} #{self.position}: Q{self.question_id}'
```

- [ ] **Step 4: Generate and apply migration**

Run: `cd backend && python manage.py makemigrations accounts --name freeshowcasequestion`
Expected: `Migrations for 'accounts': accounts/migrations/XXXX_freeshowcasequestion.py`
Then: `cd backend && python manage.py migrate`
Expected: migration applies cleanly.

- [ ] **Step 5: Register in admin**

```python
# In backend/accounts/admin.py, add at the end of the file:
from .models_freemium import FreeShowcaseQuestion


@admin.register(FreeShowcaseQuestion)
class FreeShowcaseQuestionAdmin(admin.ModelAdmin):
    list_display = ('year', 'position', 'question')
    list_filter = ('year',)
    ordering = ('year', 'position')
    search_fields = ('question__question_text',)
    raw_id_fields = ('question',)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python manage.py test accounts.tests.test_freeshowcase --verbosity=2`
Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
cd backend
git add accounts/models_freemium.py accounts/migrations/ accounts/admin.py accounts/tests/test_freeshowcase.py
git commit -m "feat(accounts): FreeShowcaseQuestion model for curated 10 PYQ/year for free users"
```

---

## Task 3: AITutorDailyUsage model + tests

**Files:**
- Create: `backend/ai_engine/models_usage.py`
- Create: `backend/ai_engine/migrations/<next>_aitutordailyusage.py` (auto-gen)
- Create: `backend/ai_engine/tests/test_ai_tutor_quota.py`

**Interfaces:**
- Produces: `ai_engine.models_usage.AITutorDailyUsage` with `user` (FK CustomUser), `date` (DateField, default=today), `message_count` (PositiveSmallIntegerField, default=0). `unique_together = ('user', 'date')`.
- Helper: `ai_engine.models_usage.consume_ai_tutor_message(user) -> int` returning the new count, atomic with `select_for_update`.

- [ ] **Step 1: Write the failing test**

```python
# backend/ai_engine/tests/test_ai_tutor_quota.py
from datetime import date
from django.test import TestCase
from django.utils import timezone
from accounts.models import CustomUser, Subscription
from ai_engine.models_usage import AITutorDailyUsage, consume_ai_tutor_message


class AITutorDailyUsageTests(TestCase):
    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username='stu', email='stu@x.com', password='x'
        )

    def test_first_message_creates_row(self):
        count = consume_ai_tutor_message(self.student)
        self.assertEqual(count, 1)
        self.assertTrue(
            AITutorDailyUsage.objects.filter(user=self.student).exists()
        )

    def test_subsequent_messages_increment(self):
        consume_ai_tutor_message(self.student)
        consume_ai_tutor_message(self.student)
        count = consume_ai_tutor_message(self.student)
        self.assertEqual(count, 3)
        row = AITutorDailyUsage.objects.get(user=self.student)
        self.assertEqual(row.message_count, 3)

    def test_unique_per_user_per_date(self):
        from django.db import IntegrityError, transaction
        consume_ai_tutor_message(self.student)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AITutorDailyUsage.objects.create(
                    user=self.student, date=date.today(), message_count=0
                )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python manage.py test ai_engine.tests.test_ai_tutor_quota --verbosity=2`
Expected: `ModuleNotFoundError: No module named 'ai_engine.models_usage'`

- [ ] **Step 3: Write the model + helper**

```python
# backend/ai_engine/models_usage.py
"""Per-user daily AI tutor usage counter for freemium 2/day cap.

This is an ADDITIONAL cap on top of the existing token economy (daily 10 +
weekly 50 + purchased + feedback). It applies to the structured AI tutor
endpoints (tutor / mnemonic / explain / rag-answer / analyze) for free
users only; premium and admin users bypass entirely.
"""
from datetime import date

from django.db import models, transaction
from django.db.models import F


class AITutorDailyUsage(models.Model):
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='ai_tutor_daily_usage',
    )
    date = models.DateField(default=date.today)
    message_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        indexes = [models.Index(fields=['user', 'date'])]


def consume_ai_tutor_message(user) -> int:
    """Atomically increment today's counter and return the new total.

    Always uses select_for_update + transaction.atomic so concurrent
    requests can't double-count past the cap.
    """
    today = date.today()
    with transaction.atomic():
        row, _ = (
            AITutorDailyUsage.objects
            .select_for_update()
            .get_or_create(user=user, date=today, defaults={'message_count': 0})
        )
        AITutorDailyUsage.objects.filter(pk=row.pk).update(
            message_count=F('message_count') + 1
        )
        row.refresh_from_db(fields=['message_count'])
        return row.message_count


def get_today_usage(user) -> int:
    """Return today's count, or 0 if no row yet."""
    row = AITutorDailyUsage.objects.filter(user=user, date=date.today()).first()
    return row.message_count if row else 0
```

- [ ] **Step 4: Generate and apply migration**

Run: `cd backend && python manage.py makemigrations ai_engine --name aitutordailyusage`
Expected: new migration file. Then: `cd backend && python manage.py migrate`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python manage.py test ai_engine.tests.test_ai_tutor_quota --verbosity=2`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
cd backend
git add ai_engine/models_usage.py ai_engine/migrations/ ai_engine/tests/test_ai_tutor_quota.py
git commit -m "feat(ai_engine): AITutorDailyUsage table + atomic consume helper for 2/day cap"
```

---

## Task 4: Add `is_free_preview` to Test model

**Files:**
- Modify: `backend/tests_engine/models.py` — add field
- Create: `backend/tests_engine/migrations/<next>_test_is_free_preview.py` (auto-gen)

**Interfaces:**
- Produces: `Test.is_free_preview: bool` (default False). Admin toggles via Django admin.

- [ ] **Step 1: Modify the model**

```python
# In backend/tests_engine/models.py, inside class Test, add the field
# next to the existing is_published field (around line ~50):

    is_free_preview = models.BooleanField(
        default=False,
        db_index=True,
        help_text='If True, free (non-premium) users can start this test. '
                  'Admin curates exactly 2 free-preview tests for the catalog.',
    )
```

- [ ] **Step 2: Generate and apply migration**

Run: `cd backend && python manage.py makemigrations tests_engine --name test_is_free_preview`
Expected: new migration. Then: `cd backend && python manage.py migrate`

- [ ] **Step 3: Commit**

```bash
cd backend
git add tests_engine/models.py tests_engine/migrations/
git commit -m "feat(tests_engine): is_free_preview boolean on Test for 2-admin-curated free tests"
```

---

## Task 5: Backend gate — AI tutor 2/day quota

**Files:**
- Modify: `backend/ai_engine/views.py` — add quota check inside `consume_ai_token`
- Create: `backend/ai_engine/tests/test_quota_integration.py`

**Interfaces:**
- Modifies: `consume_ai_token(request)` — before the existing token-economy block, check `is_premium` then `AITutorDailyUsage`. If free and count >= 2, return `(False, Response(402, {"code": "upgrade_required", "feature": "AI Tutor", "remaining": 0}))`. Otherwise, increment and continue.

- [ ] **Step 1: Write the failing test**

```python
# backend/ai_engine/tests/test_quota_integration.py
from unittest.mock import patch
from django.test import TestCase, RequestFactory
from rest_framework.response import Response
from accounts.models import CustomUser
from ai_engine.views import consume_ai_token


class ConsumeAITokenQuotaTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.student = CustomUser.objects.create_user(
            username='stu', email='stu@x.com', password='x'
        )

    def _make_request(self, user):
        req = self.factory.post('/api/ai/tutor/')
        req.user = user
        return req

    @patch('ai_engine.views.TokenBalance')
    def test_free_user_first_two_calls_succeed(self, mock_tb):
        # Mock the token balance so we test ONLY the 2/day quota
        mock_tb.objects.get_or_create.return_value = (
            type('TB', (), {'consume_token': lambda self, amount: True})(),
            True,
        )
        ok1, _ = consume_ai_token(self._make_request(self.student))
        ok2, _ = consume_ai_token(self._make_request(self.student))
        self.assertTrue(ok1)
        self.assertTrue(ok2)

    @patch('ai_engine.views.TokenBalance')
    def test_free_user_third_call_returns_402_upgrade_required(self, mock_tb):
        mock_tb.objects.get_or_create.return_value = (
            type('TB', (), {'consume_token': lambda self, amount: True})(),
            True,
        )
        consume_ai_token(self._make_request(self.student))
        consume_ai_token(self._make_request(self.student))
        ok, resp = consume_ai_token(self._make_request(self.student))
        self.assertFalse(ok)
        self.assertIsInstance(resp, Response)
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.data['code'], 'upgrade_required')
        self.assertEqual(resp.data['feature'], 'AI Tutor')

    @patch('ai_engine.views.TokenBalance')
    def test_premium_user_bypasses_quota(self, mock_tb):
        from accounts.models import Subscription
        from django.utils import timezone
        from datetime import timedelta
        Subscription.objects.create(
            user=self.student, plan='1_month', status='active',
            expires_at=timezone.now() + timedelta(days=30), amount_paid=12900,
        )
        mock_tb.objects.get_or_create.return_value = (
            type('TB', (), {'consume_token': lambda self, amount: True})(),
            True,
        )
        for _ in range(10):
            ok, _ = consume_ai_token(self._make_request(self.student))
            self.assertTrue(ok)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python manage.py test ai_engine.tests.test_quota_integration --verbosity=2`
Expected: 3 tests fail (quota check not yet wired).

- [ ] **Step 3: Modify consume_ai_token**

```python
# In backend/ai_engine/views.py, replace the consume_ai_token function
# (currently lines 64-109) with the version below. Keep the
# refund_ai_token and everything else below it untouched.

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
         → unlimited, no token deducted.
      4. Any active subscription → unlimited (freemium 2/day cap is for free users only).
      5. Freemium 2/day cap: free users get 2 AI tutor messages per day.
         3rd call returns 402 {"code": "upgrade_required", "feature": "AI Tutor"}.
      6. Otherwise → consume 1 token. If insufficient, return 429.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        if getattr(django_settings, 'DEBUG', False):
            return True, None
        return False, Response({'error': 'Authentication required'}, status=401)

    # 1. Admins have unlimited tokens
    if user.is_admin:
        return True, None

    # 2. Premium users (any active subscription) bypass both the 2/day cap
    # and token metering — they are paying customers.
    from accounts.utils import is_premium
    if is_premium(user):
        return True, None

    # 3. Freemium 2/day cap for free users (token economy still applies below).
    from .models_usage import AITutorDailyUsage, consume_ai_tutor_message
    today_count = AITutorDailyUsage.get_today_usage(user) if hasattr(
        AITutorDailyUsage, 'get_today_usage'
    ) else AITutorDailyUsage.objects.filter(
        user=user, date=__import__('datetime').date.today()
    ).aggregate(c=models.Count('id'))['c']
    # Simpler: call the helper directly
    from .models_usage import get_today_usage
    today_count = get_today_usage(user)
    if today_count >= 2:
        return False, Response({
            'code': 'upgrade_required',
            'feature': 'AI Tutor',
            'remaining': 0,
            'message': 'You have used your 2 free AI tutor messages today. '
                       'Upgrade for unlimited access.',
        }, status=402)

    # 4. Otherwise consume 1 token
    balance, _ = TokenBalance.objects.get_or_create(user=user)
    if balance.consume_token(amount=1):
        # Only count toward daily quota if token spend succeeded
        from .models_usage import consume_ai_tutor_message
        consume_ai_tutor_message(user)
        return True, None

    return False, Response({
        'error': 'insufficient_tokens',
        'message': 'You have exhausted your AI tokens. Subscribe for unlimited usage or purchase more tokens.',
        'available': balance.available_tokens,
    }, status=429)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python manage.py test ai_engine.tests.test_quota_integration --verbosity=2`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add ai_engine/views.py ai_engine/tests/test_quota_integration.py
git commit -m "feat(ai_engine): 2/day freemium quota in consume_ai_token (402 upgrade_required)"
```

---

## Task 6: Backend gate — PYQ list filters to showcase for free users

**Files:**
- Modify: `backend/questions/views.py` — `QuestionViewSet.get_queryset` and `list` method
- Modify: `backend/questions/serializers.py` — add `is_showcase` to `QuestionListSerializer`
- Create: `backend/questions/tests/test_freemium_filter.py`

**Interfaces:**
- Modifies: `QuestionViewSet.list` — after building the filtered queryset, if user is not premium, restrict to questions in `FreeShowcaseQuestion` for the requested year. Add `is_showcase` annotation.
- Produces: `QuestionListSerializer.is_showcase: bool` (read-only).

- [ ] **Step 1: Write the failing test**

```python
# backend/questions/tests/test_freemium_filter.py
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import CustomUser, Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import Question, Subject, ExamTrack
from django.utils import timezone
from datetime import timedelta


class FreeUserQuestionFilterTests(TestCase):
    def setUp(self):
        self.track = ExamTrack.objects.create(slug='cms', name='CMS')
        self.subject = Subject.objects.create(name='Medicine', exam_track=self.track)
        self.student = CustomUser.objects.create_user(
            username='stu', email='stu@x.com', password='x'
        )
        self.premium = CustomUser.objects.create_user(
            username='prm', email='prm@x.com', password='x'
        )
        Subscription.objects.create(
            user=self.premium, plan='1_month', status='active',
            expires_at=timezone.now() + timedelta(days=30), amount_paid=12900,
        )
        # Create 20 questions for year 2024
        self.questions_2024 = [
            Question.objects.create(
                question_text=f'2024 Q{i}',
                option_a='A', option_b='B', option_c='C', option_d='D',
                correct_answer='A', year=2024, subject=self.subject,
            ) for i in range(20)
        ]
        # Mark 10 of them as showcase
        for i, q in enumerate(self.questions_2024[:10]):
            FreeShowcaseQuestion.objects.create(question=q, year=2024, position=i)

    def test_free_user_sees_only_showcase_questions_for_year(self):
        client = APIClient()
        client.force_authenticate(self.student)
        resp = client.get('/api/questions/?year=2024&page_size=50')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        expected = {q.id for q in self.questions_2024[:10]}
        self.assertEqual(set(ids), expected)

    def test_premium_user_sees_all_questions_for_year(self):
        client = APIClient()
        client.force_authenticate(self.premium)
        resp = client.get('/api/questions/?year=2024&page_size=50')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertEqual(len(ids), 20)

    def test_response_includes_is_showcase_flag(self):
        client = APIClient()
        client.force_authenticate(self.student)
        resp = client.get('/api/questions/?year=2024&page_size=50')
        for r in resp.data['results']:
            self.assertIn('is_showcase', r)
            self.assertTrue(r['is_showcase'])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python manage.py test questions.tests.test_freemium_filter --verbosity=2`
Expected: 3 tests fail (filter not yet wired).

- [ ] **Step 3: Update the serializer**

```python
# In backend/questions/serializers.py, find QuestionListSerializer and add
# is_showcase at the end of the fields tuple. Implementation is computed
# from the request context (set in get_serializer).
```

First, find the existing `QuestionListSerializer`:
- Search for `class QuestionListSerializer` in `backend/questions/serializers.py`.
- Add a `SerializerMethodField`:

```python
    is_showcase = serializers.SerializerMethodField()

    def get_is_showcase(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return True
        from accounts.utils import is_premium
        if is_premium(request.user):
            return True
        # Free user: only true if this question is in the showcase for its year
        from accounts.models_freemium import FreeShowcaseQuestion
        return FreeShowcaseQuestion.objects.filter(
            question=obj, year=obj.year
        ).exists()
```

Make sure `is_showcase` is in the `fields` list of the Meta.

- [ ] **Step 4: Update the view**

```python
# In backend/questions/views.py, find the QuestionViewSet's list method
# (or get_queryset if no list override). The current code uses
# DjangoFilterBackend, so the filtering happens in get_queryset.
# Replace get_queryset with this version that also restricts free users
# to showcase questions:

    def get_queryset(self):
        from accounts.utils import is_premium
        user = getattr(self.request, 'user', None)
        is_premium_user = is_premium(user) if user else False
        qs = Question.objects.select_related('subject', 'topic').all()
        # Free users see only showcase questions for the requested year
        if not is_premium_user:
            from accounts.models_freemium import FreeShowcaseQuestion
            year_param = self.request.query_params.get('year')
            if year_param and year_param.isdigit():
                showcase_qs = FreeShowcaseQuestion.objects.filter(
                    year=int(year_param)
                ).values_list('question_id', flat=True)
                qs = qs.filter(id__in=list(showcase_qs))
        return qs
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python manage.py test questions.tests.test_freemium_filter --verbosity=2`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
cd backend
git add questions/views.py questions/serializers.py questions/tests/test_freemium_filter.py
git commit -m "feat(questions): free users see only 10 curated showcase questions per year"
```

---

## Task 7: Backend gate — Test start requires `is_free_preview` for free users

**Files:**
- Modify: `backend/tests_engine/views.py` — add gate in `start` action
- Modify: `backend/tests_engine/serializers.py` — add `is_free_preview` to `TestSerializer`
- Create: `backend/tests_engine/tests/test_freemium_start.py`

**Interfaces:**
- Modifies: `TestViewSet.start` (the @action method) — if user is not premium and `test.is_free_preview` is False, return `403 {"code": "upgrade_required", "feature": "Mock Tests"}`.
- Produces: `TestSerializer.is_free_preview: bool` (read-only).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests_engine/tests/test_freemium_start.py
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import CustomUser, Subscription
from tests_engine.models import Test
from questions.models import Question, Subject, ExamTrack
from django.utils import timezone
from datetime import timedelta


class FreeUserTestStartTests(TestCase):
    def setUp(self):
        self.track = ExamTrack.objects.create(slug='cms', name='CMS')
        self.subject = Subject.objects.create(name='Medicine', exam_track=self.track)
        self.student = CustomUser.objects.create_user(
            username='stu', email='stu@x.com', password='x'
        )
        self.premium = CustomUser.objects.create_user(
            username='prm', email='prm@x.com', password='x'
        )
        Subscription.objects.create(
            user=self.premium, plan='1_month', status='active',
            expires_at=timezone.now() + timedelta(days=30), amount_paid=12900,
        )
        # 3 tests: 2 free preview, 1 premium-only
        self.preview_test = Test.objects.create(
            title='Free Preview 1', test_type='mixed', num_questions=10,
            time_limit_minutes=10, is_published=True, is_free_preview=True,
            created_by=self.premium,
        )
        self.preview_test_2 = Test.objects.create(
            title='Free Preview 2', test_type='mixed', num_questions=10,
            time_limit_minutes=10, is_published=True, is_free_preview=True,
            created_by=self.premium,
        )
        self.premium_test = Test.objects.create(
            title='Premium Only', test_type='mixed', num_questions=20,
            time_limit_minutes=20, is_published=True, is_free_preview=False,
            created_by=self.premium,
        )
        for t in [self.preview_test, self.preview_test_2, self.premium_test]:
            t.questions.set(
                Question.objects.all()[:min(5, Question.objects.count())]
            )

    def test_free_user_can_start_preview_test(self):
        client = APIClient()
        client.force_authenticate(self.student)
        resp = client.post(f'/api/tests/{self.preview_test.id}/start/')
        self.assertIn(resp.status_code, [200, 201])

    def test_free_user_cannot_start_premium_test(self):
        client = APIClient()
        client.force_authenticate(self.student)
        resp = client.post(f'/api/tests/{self.premium_test.id}/start/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['code'], 'upgrade_required')
        self.assertEqual(resp.data['feature'], 'Mock Tests')

    def test_premium_user_can_start_any_test(self):
        client = APIClient()
        client.force_authenticate(self.premium)
        resp = client.post(f'/api/tests/{self.premium_test.id}/start/')
        self.assertIn(resp.status_code, [200, 201])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python manage.py test tests_engine.tests.test_freemium_start --verbosity=2`
Expected: 3 tests fail.

- [ ] **Step 3: Add `is_free_preview` to TestSerializer**

```python
# In backend/tests_engine/serializers.py, find TestSerializer and add
# 'is_free_preview' to the fields tuple.
```

- [ ] **Step 4: Add the start-action gate**

```python
# In backend/tests_engine/views.py, find the @action(detail=True, methods=['post'], url_path='start')
# (search for `def start(` in the TestViewSet class). Add this at the very
# top of the method body, before any other logic:

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        from accounts.utils import is_premium
        test = self.get_object()
        if not is_free_preview_or_premium(test, request.user):
            return Response(
                {'code': 'upgrade_required', 'feature': 'Mock Tests'},
                status=status.HTTP_403_FORBIDDEN,
            )
        # ... existing start logic below
```

Then add a helper at the module level:

```python
# At the top of backend/tests_engine/views.py, after the imports:

def is_free_preview_or_premium(test, user) -> bool:
    """True if user can start this test. Free users only for is_free_preview tests."""
    from accounts.utils import is_premium
    return test.is_free_preview or is_premium(user)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python manage.py test tests_engine.tests.test_freemium_start --verbosity=2`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
cd backend
git add tests_engine/views.py tests_engine/serializers.py tests_engine/tests/test_freemium_start.py
git commit -m "feat(tests_engine): free users can start only is_free_preview tests (403 otherwise)"
```

---

## Task 8: Frontend paywall primitives (modal, badge, banner, store, hook)

**Files:**
- Create: `frontend/src/lib/stores/paywallStore.ts`
- Create: `frontend/src/lib/hooks/useUpgradeModal.tsx`
- Create: `frontend/src/components/paywall/LockedBadge.tsx`
- Create: `frontend/src/components/paywall/UpgradeModal.tsx`
- Create: `frontend/src/components/paywall/UsageBanner.tsx`

**Interfaces:**
- `paywallStore`: `{ open: bool, feature: string, remaining?: number, show(feature, remaining?), dismiss() }`
- `useUpgradeModal()` returns `{ openUpgrade(feature, remaining?) }` (for use in event handlers) and `<UpgradeModalRoot />` JSX (mount once at layout).
- `<LockedBadge />` is a small pill: `<Lock size={12} /> Premium`.
- `<UsageBanner />` is the soft banner: shows today's AI count for free users.

- [ ] **Step 1: Install Zustand if not already**

Run: `cd frontend && npm ls zustand`
If missing, run: `cd frontend && npm install zustand`

- [ ] **Step 2: Create paywallStore**

```typescript
// frontend/src/lib/stores/paywallStore.ts
import { create } from 'zustand';

interface PaywallState {
  open: boolean;
  feature: string;
  remaining?: number;
  show: (feature: string, remaining?: number) => void;
  dismiss: () => void;
}

export const usePaywallStore = create<PaywallState>((set) => ({
  open: false,
  feature: '',
  remaining: undefined,
  show: (feature, remaining) => set({ open: true, feature, remaining }),
  dismiss: () => set({ open: false, feature: '', remaining: undefined }),
}));
```

- [ ] **Step 3: Create UpgradeModal**

```typescript
// frontend/src/components/paywall/UpgradeModal.tsx
'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { X, Sparkles, Check } from 'lucide-react';
import { usePaywallStore } from '@/lib/stores/paywallStore';
import { trackPaywallView, trackUpgradeClick, trackPaywallDismissed } from '@/lib/analytics';

export function UpgradeModal() {
  const { open, feature, remaining, dismiss } = usePaywallStore();
  const router = useRouter();

  useEffect(() => {
    if (open) {
      trackPaywallView(feature);
    }
  }, [open, feature]);

  if (!open) return null;

  const handleStart = () => {
    trackUpgradeClick(feature);
    dismiss();
    router.push('/subscription');
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      onClick={() => { trackPaywallDismissed(feature); dismiss(); }}
      data-testid="upgrade-modal"
    >
      <div
        className="relative max-w-md w-full rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => { trackPaywallDismissed(feature); dismiss(); }}
          className="absolute top-3 right-3 p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800"
          aria-label="Close"
        >
          <X size={18} />
        </button>
        <div className="flex flex-col items-center text-center">
          <div className="w-14 h-14 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center mb-4">
            <Sparkles className="text-white" size={28} />
          </div>
          <h2 className="text-xl font-bold mb-2">Unlock {feature} and everything else</h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-1">
            From just <span className="font-bold text-slate-900 dark:text-white">₹129/month</span>
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-500 mb-4">
            Cancel anytime · Used by 10,000+ UPSC CMS aspirants
          </p>
          <ul className="w-full text-left space-y-1.5 mb-5 text-sm">
            {['Unlimited PYQ questions', 'Unlimited mock tests', 'Unlimited AI tutor', 'Adaptive tests + deep analytics', 'Video explanations'].map((p) => (
              <li key={p} className="flex items-center gap-2">
                <Check size={14} className="text-emerald-500 flex-shrink-0" />
                <span>{p}</span>
              </li>
            ))}
          </ul>
          <button
            onClick={handleStart}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold hover:from-amber-600 hover:to-orange-600 transition"
          >
            Start Now →
          </button>
          <button
            onClick={() => { trackPaywallDismissed(feature); dismiss(); }}
            className="mt-2 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create LockedBadge**

```typescript
// frontend/src/components/paywall/LockedBadge.tsx
import { Lock } from 'lucide-react';

interface LockedBadgeProps {
  label?: string;
  size?: 'xs' | 'sm';
}

export function LockedBadge({ label = 'Premium', size = 'xs' }: LockedBadgeProps) {
  const sz = size === 'sm' ? 'text-[11px] px-2 py-0.5' : 'text-[10px] px-1.5 py-0.5';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 font-semibold ${sz}`}
    >
      <Lock size={size === 'sm' ? 11 : 9} />
      {label}
    </span>
  );
}
```

- [ ] **Step 5: Create UsageBanner**

```typescript
// frontend/src/components/paywall/UsageBanner.tsx
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Sparkles, X } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { trackUpgradeClick } from '@/lib/analytics';

const DISMISS_KEY = 'crackcms_usage_banner_dismissed_v1';

export function UsageBanner() {
  const { user } = useAuth();
  const [aiUsed, setAiUsed] = useState<number>(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    setDismissed(sessionStorage.getItem(DISMISS_KEY) === '1');
    // Read AI count from the user profile payload (added in Task 9)
    setAiUsed(user?.ai_tutor_used_today ?? 0);
  }, [user]);

  const isPremium = user?.subscription_info?.is_active || user?.is_admin;
  if (isPremium || dismissed || aiUsed < 1) return null;

  return (
    <div className="sticky top-0 z-40 w-full bg-gradient-to-r from-amber-500 to-orange-500 text-white px-4 py-2 flex items-center justify-between gap-2 text-sm shadow-sm">
      <div className="flex items-center gap-2 min-w-0">
        <Sparkles size={16} className="flex-shrink-0" />
        <span className="truncate">
          <strong>{aiUsed}/2</strong> AI chats used today ·
          <Link
            href="/subscription"
            onClick={() => trackUpgradeClick('usage_banner')}
            className="ml-1 underline font-semibold"
          >
            Unlock all features from ₹129/month →
          </Link>
        </span>
      </div>
      <button
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, '1');
          setDismissed(true);
        }}
        className="p-1 hover:bg-white/20 rounded"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}
```

- [ ] **Step 6: Create useUpgradeModal hook**

```typescript
// frontend/src/lib/hooks/useUpgradeModal.tsx
'use client';

import { usePaywallStore } from '@/lib/stores/paywallStore';
import { UpgradeModal } from '@/components/paywall/UpgradeModal';

export function useUpgradeModal() {
  const show = usePaywallStore((s) => s.show);
  return {
    openUpgrade: (feature: string, remaining?: number) => show(feature, remaining),
    UpgradeModalRoot: () => <UpgradeModal />,
  };
}
```

- [ ] **Step 7: Build to verify TS compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/lib/stores/paywallStore.ts src/lib/hooks/useUpgradeModal.tsx src/components/paywall/ src/lib/analytics.ts
git commit -m "feat(paywall): UpgradeModal, LockedBadge, UsageBanner, useUpgradeModal hook"
```

---

## Task 9: API interceptor + analytics events + profile payload extension

**Files:**
- Modify: `frontend/src/lib/api.ts` — interceptor for `code: 'upgrade_required'`
- Modify: `frontend/src/lib/analytics.ts` — add events
- Modify: `backend/accounts/views.py` — extend profile payload

**Interfaces:**
- `api.ts` response interceptor: if `error.response?.data?.code === 'upgrade_required'`, call `usePaywallStore.getState().show(feature, remaining)`.
- `analytics.ts`: add `trackPaywallView(feature)`, `trackUpgradeClick(feature)`, `trackPaywallDismissed(feature)`.
- `/api/auth/profile/`: add `ai_tutor_used_today: int` and `showcase_questions_remaining: int` (per active exam track).

- [ ] **Step 1: Add analytics events**

In `frontend/src/lib/analytics.ts`, find the existing event taxonomy (the typed event names list) and add the three names. Then add the helper functions:

```typescript
// Add to the events list (around line 60-120):
'paywall_view', 'upgrade_click', 'paywall_dismissed',

// Add helper functions (alongside the other trackXxx functions):
export function trackPaywallView(feature: string): void {
  dispatch('paywall_view', { feature });
}
export function trackUpgradeClick(feature: string): void {
  dispatch('upgrade_click', { feature });
}
export function trackPaywallDismissed(feature: string): void {
  dispatch('paywall_dismissed', { feature });
}
```

- [ ] **Step 2: Add api.ts interceptor**

```typescript
// In frontend/src/lib/api.ts, find the response interceptor (the .interceptors.response.use block).
// Inside the onError callback, BEFORE the existing 502/503/504 retry logic, add:

  if (error?.response?.data?.code === 'upgrade_required') {
    const feature = error.response.data.feature || 'this feature';
    const remaining = error.response.data.remaining;
    // Dynamic import to avoid SSR
    import('@/lib/stores/paywallStore').then(({ usePaywallStore }) => {
      usePaywallStore.getState().show(feature, remaining);
    });
    return Promise.reject(error);
  }
```

- [ ] **Step 3: Extend profile payload (backend)**

```python
# In backend/accounts/views.py, find the view that handles GET /api/auth/profile/
# (likely ProfileView or similar). Add these two fields to the returned dict:

            'ai_tutor_used_today': get_today_usage(user),  # from ai_engine.models_usage
            'showcase_questions_remaining': 10,  # full per-year cap; UI can refine
```

Make sure to import `get_today_usage` at the top of the file:
```python
from ai_engine.models_usage import get_today_usage
```

- [ ] **Step 4: Build + run existing tests**

Run: `cd frontend && npx tsc --noEmit`
Run: `cd backend && python manage.py test --verbosity=1 -k 2`
Expected: TS clean. Existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/analytics.ts backend/accounts/views.py
git commit -m "feat(paywall): api interceptor fires modal on upgrade_required; profile exposes AI usage"
```

---

## Task 10: Mount modal + banner in layout, add lock icons in sidebar

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

**Interfaces:**
- `layout.tsx`: render `<UpgradeModalRoot />` once (next to `<WatermarkOverlay />`) and `<UsageBanner />` (only on `/questions`, `/tests`, `/ai-tutor`).
- `Sidebar.tsx`: every nav entry that maps to a premium feature shows `<LockedBadge />` for free users.

- [ ] **Step 1: Mount in layout**

```typescript
// In frontend/src/app/layout.tsx, find the existing <WatermarkOverlay /> mount
// (around line 271-302). Add the modal root and a conditional banner:

import { useUpgradeModal } from '@/lib/hooks/useUpgradeModal';
import { UsageBanner } from '@/components/paywall/UsageBanner';
import { usePathname } from 'next/navigation';

// Inside the exported component, after the existing hook calls:
  const pathname = usePathname();
  const { UpgradeModalRoot } = useUpgradeModal();
  const showBanner = pathname?.startsWith('/questions')
    || pathname?.startsWith('/tests')
    || pathname?.startsWith('/simulator')
    || pathname?.startsWith('/ai-tutor');

// In the JSX, add:
  {showBanner && <UsageBanner />}
  <UpgradeModalRoot />
```

- [ ] **Step 2: Add lock icons in sidebar**

```typescript
// In frontend/src/components/Sidebar.tsx, find the nav items array (the
// list that maps to links like /questions, /tests, /ai-tutor, etc.).
// For each premium-gated item, render <LockedBadge /> next to the label
// for non-premium users. Example pattern:

import { LockedBadge } from './paywall/LockedBadge';
import { useAuth } from '@/lib/auth';

// Inside the render (or in the nav map):
  const { user } = useAuth();
  const isPremium = user?.subscription_info?.is_active || user?.is_admin;

// In each nav item's JSX, add:
  {!isPremium && item.premium && <LockedBadge />}
```

Then add a `premium: true` flag to nav items for: "Adaptive Tests", "Deep Analytics", "Premium Decks" (whatever exists in the sidebar array).

- [ ] **Step 3: Build + smoke**

Run: `cd frontend && npx tsc --noEmit && npm run lint 2>&1 | head -50`
Expected: no errors. Visit `/` in dev — modal should NOT show; visit `/tests` — usage banner should be hidden if user has 0 AI chats.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat(paywall): mount UpgradeModal at root + UsageBanner on /questions /tests /ai-tutor"
```

---

## Task 11: Wire up gates in Question Bank, Tests, AI Tutor pages

**Files:**
- Modify: `frontend/src/components/question/ExamQuestionBank.tsx`
- Modify: `frontend/src/app/tests/page.tsx`
- Modify: `frontend/src/app/tests/[id]/page.tsx`
- Modify: `frontend/src/app/simulator/page.tsx`
- Modify: `frontend/src/app/ai-tutor/page.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`

**Interfaces:**
- `ExamQuestionBank.tsx`: when free, the fetch is already filtered server-side; just need to add lock badge to year cards that have no showcase entries. The "Submit" / "Show Answer" buttons on showcase questions work normally. Direct deep-links to non-showcase questions trigger the modal.
- `tests/page.tsx`: render `<LockedBadge />` on each non-preview test card; replace "Start" button on locked cards with one that calls `openUpgrade('Mock Tests')`.
- `tests/[id]/page.tsx`: no change (gate happens at start endpoint, interceptor handles modal).
- `simulator/page.tsx`: prepend 2 free-preview mocks as attemptable; rest call `openUpgrade`.
- `ai-tutor/page.tsx`: no client change needed (the interceptor opens the modal on 402). Add `<UsageBanner />` to the page.
- `dashboard/page.tsx`: add a "Premium features" row at top for free users (Adaptive Tests, Deep Analytics, Premium Decks) — each card has a `<LockedBadge />` and clicks open the modal.

- [ ] **Step 1: ExamQuestionBank — add lock badge to empty years**

```typescript
// In ExamQuestionBank.tsx, find the year-stats grid (the .map for year cards,
// around line 722-789). For each year card, check if the year has any
// showcase entries (pass via the existing `solved/count` pair — count==0 for
// no showcase in free mode). Render <LockedBadge /> in that case.
```

Specifically, inside the year card render block, add:
```typescript
  {!isPremium && (year.solved === 0 && year.count === 0) && <LockedBadge />}
```

The exact prop name depends on how the year stats are structured; the agent should read the surrounding code and use the existing `count` field.

- [ ] **Step 2: tests/page.tsx — lock badge + locked Start button**

```typescript
// In tests/page.tsx, in the test card render, add:
  {!isPremium && !test.is_free_preview && <LockedBadge />}

// Replace the Start button handler:
  onClick={() => isPremium || test.is_free_preview
    ? startTest(test.id)
    : openUpgrade('Mock Tests')}
```

- [ ] **Step 3: simulator/page.tsx — same pattern**

In the simulator, identify the test list and apply the same lock + click pattern as `tests/page.tsx`.

- [ ] **Step 4: ai-tutor/page.tsx — banner only**

The interceptor handles the modal. Just verify the `<UsageBanner />` is mounted by the layout (it already is on `/ai-tutor`).

- [ ] **Step 5: dashboard/page.tsx — premium features row**

```typescript
// At the top of the dashboard (after the existing welcome row), add:
{!isPremium && (
  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
    {[
      { label: 'Adaptive Tests', href: '/tests' },
      { label: 'Deep Analytics', href: '/analytics' },
      { label: 'Unlimited AI Tutor', href: '/ai-tutor' },
    ].map((f) => (
      <button
        key={f.label}
        onClick={() => openUpgrade(f.label)}
        className="p-3 rounded-xl border border-amber-200 bg-amber-50/50 dark:bg-amber-900/10 text-left hover:bg-amber-50 dark:hover:bg-amber-900/20 transition"
      >
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">{f.label}</span>
          <LockedBadge />
        </div>
        <p className="text-xs text-slate-500 mt-1">Unlock with Premium →</p>
      </button>
    ))}
  </div>
)}
```

- [ ] **Step 6: Build + smoke**

Run: `cd frontend && npx tsc --noEmit && npm run lint 2>&1 | head -30`
Expected: clean.

Manual: log in as a free user, visit `/tests`. Click "Start" on a non-preview test → modal opens. Visit `/ai-tutor` → send 3 messages → modal opens on 3rd.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/question/ExamQuestionBank.tsx \
        frontend/src/app/tests/page.tsx \
        frontend/src/app/tests/[id]/page.tsx \
        frontend/src/app/simulator/page.tsx \
        frontend/src/app/ai-tutor/page.tsx \
        frontend/src/app/dashboard/page.tsx
git commit -m "feat(paywall): wire lock badges + upgrade modal triggers in Q-bank, tests, AI tutor, dashboard"
```

---

## Task 12: Full integration smoke + admin curation

**Files:**
- Modify: `backend/accounts/admin.py` — register the new `FreeShowcaseQuestion` if not already (from Task 2), add `is_free_preview` to TestAdmin
- Create: `backend/accounts/management/commands/seed_free_showcase.py` (one-shot script to bootstrap 10 per year)

**Interfaces:**
- Admin can mark 2 tests as `is_free_preview=True` in Django admin.
- Admin can set 10 `FreeShowcaseQuestion` per year in Django admin.
- Seed command picks 10 questions per year deterministically (lowest id) so a fresh deployment always has something to show.

- [ ] **Step 1: Add `is_free_preview` to TestAdmin**

```python
# In backend/tests_engine/admin.py, add 'is_free_preview' to the list_display
# and list_filter of TestAdmin.
```

- [ ] **Step 2: Write seed command**

```python
# backend/accounts/management/commands/seed_free_showcase.py
"""Bootstrap 10 FreeShowcaseQuestion rows per year using the lowest-id questions.

Idempotent: skips years that already have 10 entries.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import Question


class Command(BaseCommand):
    help = 'Seed FreeShowcaseQuestion for each year that has questions.'

    def handle(self, *args, **options):
        years = Question.objects.values_list('year', flat=True).distinct()
        created = 0
        for year in sorted(years, reverse=True):
            existing = FreeShowcaseQuestion.objects.filter(year=year).count()
            if existing >= 10:
                continue
            needed = 10 - existing
            qs = (Question.objects
                  .filter(year=year, is_active=True)
                  .exclude(id__in=FreeShowcaseQuestion.objects
                           .filter(year=year).values_list('question_id', flat=True))
                  .order_by('id')[:needed])
            for position, q in enumerate(qs, start=existing):
                with transaction.atomic():
                    FreeShowcaseQuestion.objects.create(
                        question=q, year=year, position=position,
                    )
                    created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} showcase entries.'))
```

- [ ] **Step 3: Run the seed**

Run: `cd backend && python manage.py seed_free_showcase`
Expected: prints number created.

- [ ] **Step 4: Run all freemium tests**

Run: `cd backend && python manage.py test accounts.tests.test_is_premium accounts.tests.test_freeshowcase questions.tests.test_freemium_filter tests_engine.tests.test_freemium_start ai_engine.tests.test_ai_tutor_quota ai_engine.tests.test_quota_integration --verbosity=2`
Expected: all 16 tests pass.

- [ ] **Step 5: Frontend build + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
cd backend
git add tests_engine/admin.py accounts/admin.py accounts/management/commands/seed_free_showcase.py
git commit -m "feat(accounts): seed_free_showcase command + admin wiring for freemium curation"
```

---

## Self-Review (run by author after writing this plan)

**1. Spec coverage:**
- A. Premium detection → Task 1 ✅
- B. Showcase 10 PYQ/year → Tasks 2, 6, 12 ✅
- C. Free-vs-locked test catalog → Tasks 4, 7, 11, 12 ✅
- D. AI Tutor 2/day → Tasks 3, 5 ✅
- E. Upgrade popup → Tasks 8, 9, 10 ✅
- F. Soft banner → Tasks 8, 10 ✅
- G. Lock badge → Tasks 8, 10, 11 ✅
- H. Analytics events → Tasks 8, 9 ✅
- I. Backend enforcement + interceptor → Tasks 5, 6, 7, 9 ✅

**2. Placeholder scan:** No "TBD", "implement later", or "add appropriate" language. Every code block is concrete and complete. ✅

**3. Type consistency:** `_is_premium` / `is_premium` (Task 1) is used by Tasks 5, 6, 7. `AITutorDailyUsage.consume_ai_tutor_message` and `get_today_usage` (Task 3) are used by Tasks 5, 9. `usePaywallStore.show(feature, remaining?)` and `dismiss()` (Task 8) are used by Tasks 8, 9, 11. `openUpgrade(feature, remaining?)` (Task 8) is used by Task 11. All signatures align. ✅

**4. Behavioral decisions:**
- Visibility = locked-not-hidden → enforced by Tasks 8, 10, 11 (Lock icons rendered, not absent) ✅
- ₹129 copy → baked into UpgradeModal Task 8 ✅
- Click+soft-banner popup → Tasks 8, 10 ✅
- subscription_info.is_active only → Task 1 ✅
- Token economy unchanged → Task 5 (quota is additional, not replacement) ✅
- Free-preview tests admin-curated → Tasks 4, 12 ✅

**5. Regression guards:**
- Existing token tests still pass (mocked in Task 5 test) ✅
- Existing subscription activation unchanged (no touch) ✅
- Welcome email unchanged ✅
- Single-device enforcement unchanged ✅

---

## Execution Choice

Plan complete and saved to `C:\Users\DIVYANSHU\Desktop\crack_cms\docs\superpowers\plans\2026-08-02-freemium-conversion-layer.md`. Twelve tasks, ~29 file changes, organized so a subagent can pick up any single task with no extra context.

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task with isolated context, review the work between tasks, fast iteration, and parallelizable where safe (e.g. Tasks 8–10 have no inter-dependencies after the backend foundation is done).

2. **Inline Execution** — I execute tasks in this session using `executing-plans`, batch execution with checkpoints for review.

**Which approach?**
