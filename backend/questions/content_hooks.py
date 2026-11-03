"""One call after any change to a question's key, stem or options (2026-11).

Every code path that changes ``correct_answer``, ``question_text`` or ``option_a``..``option_d`` on an
existing row calls ``on_question_changed`` after the change is committed (use
``transaction.on_commit``). Each subsystem registers its reaction here instead of editing the
call sites:

* evidence      -> ``evidence.services.mark_stale(question)``: evidence recorded for the old
                   content / key is hidden from students until reviewed.
* key_audit     -> ``key_audit.services.queue_question_audit(question_id, reason)``: the audit
                   becomes stale and the question is re-audited.
* topic notes   -> ``questions.notes_builder.mark_notes_stale(question_id)``.

A reaction that fails is logged and does not undo the edit.
"""
from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

# (module, function) -- called as fn(question, old_key=..., old_stem_hash=..., reason=..., actor=...)
HANDLERS = (
    ('evidence.services', 'on_question_changed'),
    ('key_audit.services', 'on_question_changed'),
    ('questions.notes_builder', 'on_question_changed'),
)


def on_question_changed(question, *, old_key: str = '', old_stem_hash: str = '', reason: str = '', actor=None) -> None:
    for module_name, func_name in HANDLERS:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        func = getattr(module, func_name, None)
        if func is None:
            continue
        try:
            func(question, old_key=old_key, old_stem_hash=old_stem_hash, reason=reason, actor=actor)
        except Exception:  # noqa: BLE001 - a reaction must never undo or block the edit
            logger.exception('content hook %s.%s failed for question %s', module_name, func_name,
                             getattr(question, 'pk', question))
