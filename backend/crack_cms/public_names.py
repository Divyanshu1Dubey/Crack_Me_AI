"""Names one learner may see of another.

``public_handle(user)`` is the single rule for every payload that shows a
person to other learners (question discussions, the leaderboard, ...): only a
username the person chose, never a first/last name and never anything taken
from their email address.

New accounts get the username chosen at sign-up (when it passes the
Settings rules) or a generated ``learner_<hex>`` handle, never the email's
local part; migration accounts.0027 renamed older email-derived student
usernames. A username that still equals the email's local part (or contains
an '@') gets ``None``: the UI shows a neutral label instead.

Same rule as ``analytics.views._public_name`` (the leaderboard).
"""
from __future__ import annotations

from typing import Optional


def public_handle(user) -> Optional[str]:
    """The handle other learners see, or ``None`` to show no name."""
    name = (getattr(user, 'username', '') or '').strip()
    if not name or '@' in name:
        return None
    local = (getattr(user, 'email', '') or '').strip().lower().split('@', 1)[0].strip()
    if local:
        lowered = name.lower()
        stems = {lowered}
        head, sep, tail = lowered.rpartition('_')
        if sep and tail.isdigit():
            stems.add(head)  # a collision suffix
        # Derived names are cut to 140 (130 before a suffix) characters.
        if stems & {local, local[:140], local[:130]}:
            return None
    return name
