"""Transactional email helpers for the accounts app.

Mail used to be sent synchronously inside the request (first sign-in,
order creation, payment verification), so a slow SMTP server (EMAIL_TIMEOUT
is 20 s) stalled sign-in and checkout. ``send_mail_in_background`` sends
after the surrounding transaction commits, on a daemon thread.

With the in-memory test backend (Django's test runner) mail is sent
synchronously so tests stay deterministic.
"""
from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

logger = logging.getLogger(__name__)


def _send(**kwargs) -> None:
    try:
        send_mail(fail_silently=False, **kwargs)
    except Exception:
        logger.warning('Background email failed: subject=%r', kwargs.get('subject'), exc_info=True)


def _sends_synchronously() -> bool:
    return str(getattr(settings, 'EMAIL_BACKEND', '')).endswith('locmem.EmailBackend')


def send_mail_in_background(*, subject: str, message: str, recipient_list: list[str], from_email: str | None = None) -> None:
    """Queue a plain-text email to go out after the current transaction commits."""
    recipients = [r for r in recipient_list if r]
    if not recipients:
        return
    kwargs = {
        'subject': subject,
        'message': message,
        'from_email': from_email or settings.DEFAULT_FROM_EMAIL,
        'recipient_list': recipients,
    }
    if _sends_synchronously():
        transaction.on_commit(lambda: _send(**kwargs))
        return

    def _start():
        threading.Thread(target=_send, kwargs=kwargs, name='accounts-mail', daemon=True).start()

    transaction.on_commit(_start)


def run_in_background(func, *args, **kwargs) -> None:
    """Run ``func`` after commit on a daemon thread (synchronously under the test backend)."""
    def _call():
        try:
            func(*args, **kwargs)
        except Exception:
            logger.warning('Background task %s failed', getattr(func, '__name__', func), exc_info=True)

    if _sends_synchronously():
        transaction.on_commit(_call)
        return
    transaction.on_commit(lambda: threading.Thread(target=_call, name='accounts-bg', daemon=True).start())
