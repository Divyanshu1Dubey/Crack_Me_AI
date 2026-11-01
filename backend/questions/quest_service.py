"""Daily quest engine.

Quests are generated server-side (idempotently, once per local day), their
progress is computed from real activity rows, and claiming is validated on
the server. Clients can no longer choose their own XP reward, mark an
unfinished quest complete, or re-claim the same quest.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

# quest_type -> (title, description, target, xp, difficulty)
DAILY_QUEST_TEMPLATES = {
    # Progress: DailyActivity.questions_attempted, which the question-bank
    # ``attempt`` endpoint AND practice mode (``practice/attempt``) both
    # increment for a user's first answer to a question.
    'solve_questions': ('Solve 20 questions', 'Answer any 20 questions today (question bank or tests).', 20, 20, 'medium'),
    'complete_tests': ('Finish a test', 'Complete at least one mock or practice test today.', 1, 15, 'medium'),
    'review_mistakes': ('Review 5 mistakes', 'Review 5 entries from your mistake notebook today.', 5, 10, 'easy'),
}


def _end_of_local_day(day):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), tz)


def ensure_daily_quests(user):
    """Create today's quests for ``user`` if they do not exist yet."""
    from questions.models import UserQuest

    today = timezone.localdate()
    expires = _end_of_local_day(today)
    for quest_type, (title, desc, target, xp, difficulty) in DAILY_QUEST_TEMPLATES.items():
        UserQuest.objects.get_or_create(
            user=user, quest_type=quest_type, quest_date=today,
            defaults={
                'title': title, 'description': desc, 'target_value': target,
                'xp_reward': xp, 'difficulty': difficulty, 'expires_at': expires,
            },
        )


def _progress_for(user, quest_type: str, day) -> int | None:
    from analytics.models import DailyActivity
    from questions.models import MistakeNotebook
    from tests_engine.models import TestAttempt

    if quest_type == 'solve_questions':
        row = DailyActivity.objects.filter(user=user, date=day).first()
        return int(row.questions_attempted) if row else 0
    if quest_type == 'complete_tests':
        from django.db.models import Q

        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(day, time.min), tz)
        # Only a test the student actually answered counts: an empty submit
        # earns no XP / DailyActivity, so it must not finish the quest either.
        # Nor does a late submission (TestAttempt.is_late): its XP is
        # withheld, and claiming the quest would pay XP for it after all.
        return TestAttempt.objects.filter(
            Q(correct_count__gt=0) | Q(incorrect_count__gt=0),
            user=user, is_completed=True, is_late=False,
            completed_at__gte=start, completed_at__lt=start + timedelta(days=1),
        ).count()
    if quest_type == 'review_mistakes':
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(day, time.min), tz)
        return MistakeNotebook.objects.filter(
            user=user, last_reviewed_at__gte=start, last_reviewed_at__lt=start + timedelta(days=1),
        ).count()
    return None  # unknown / admin-defined quest types keep their stored value


def refresh_progress(user, quests) -> None:
    """Recompute ``current_value`` for the user's open quests in place."""
    for quest in quests:
        if quest.is_completed:
            continue
        value = _progress_for(user, quest.quest_type, quest.quest_date)
        if value is None:
            continue
        value = min(int(value), int(quest.target_value or 0) or int(value))
        if value != quest.current_value:
            type(quest).objects.filter(pk=quest.pk).update(current_value=value)
            quest.current_value = value


class QuestClaimError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def claim_quest(user, quest_id: int):
    """Mark a finished quest complete and award its (server-defined) XP."""
    from analytics.models import StudyStreak
    from questions.models import QuestStreak, UserQuest

    with transaction.atomic():
        quest = UserQuest.objects.select_for_update().filter(pk=quest_id, user=user).first()
        if quest is None:
            raise QuestClaimError('Quest not found.', status=404)
        if quest.is_completed:
            raise QuestClaimError('Quest already claimed.')
        if quest.expires_at and quest.expires_at < timezone.now():
            raise QuestClaimError('This quest has expired.')
        refresh_progress(user, [quest])
        if quest.current_value < quest.target_value:
            raise QuestClaimError('Quest is not finished yet.')

        now = timezone.now()
        quest.is_completed = True
        quest.is_claimed = True
        quest.completed_at = now
        quest.save(update_fields=['is_completed', 'is_claimed', 'completed_at'])

        streak, _ = QuestStreak.objects.select_for_update().get_or_create(user=user)
        today = timezone.localdate()
        if streak.last_quest_date != today:
            # Streak counts days with at least one claimed quest.
            if streak.last_quest_date == today - timedelta(days=1):
                streak.current_streak += 1
            elif streak.streak_frozen and streak.last_quest_date == today - timedelta(days=2):
                # A freeze covers exactly ONE missed day (it used to bridge
                # a gap of any length, so a streak could never be lost).
                streak.current_streak += 1
                streak.streak_frozen = False  # a freeze protects one gap
            else:
                if streak.last_quest_date is not None:
                    # The streak broke: a freeze still armed from before the
                    # gap lapses with it (it must not bridge a later gap).
                    streak.streak_frozen = False
                streak.current_streak = 1
            streak.last_quest_date = today
        streak.longest_streak = max(streak.longest_streak, streak.current_streak)
        streak.total_quests_completed += 1
        streak.total_xp_earned += int(quest.xp_reward or 0)
        streak.save()

        study_streak, _ = StudyStreak.objects.get_or_create(user=user)
        study_streak.add_xp(int(quest.xp_reward or 0))
    return quest
