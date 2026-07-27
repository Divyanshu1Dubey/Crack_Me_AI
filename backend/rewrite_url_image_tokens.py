"""
One-shot cleanup: rewrite Question.question_text / option_a..d / explanation
tokens from `[[img:https://…/foo.png]]` to `[[img:N]]` where N is the matching
QuestionImage row id (matched by URL).

Root cause: `import_mocktests.py` used to write `[[img:{full_url}]]` into
question_text instead of `[[img:{QuestionImage.id}]`. The frontend regex only
matched integer IDs, so 761+ Expert Curated rows leaked the raw token text
into the UI ("Question image" alt + nothing visible). The parser has since
been patched to write IDs; this script backfills the rows already imported.

Heuristics:
  - For every Question that has `[[img:<url>]]` tokens, build a URL→id map
    from its QuestionImage rows.
  - Replace each URL token with `[[img:{id}]]` when the URL matches a row;
    leave it untouched when no match (and emit a warning so we can audit
    orphan URLs).
  - Also touches `option_a..d`, `explanation`, and `mnemonic` — image tokens
    can legitimately appear in any of these fields.

Run:
    PYTHONIOENCODING=utf-8 python rewrite_url_image_tokens.py [--dry-run]
"""
from __future__ import annotations

import os
import re
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Question  # noqa: E402

# Match either a full http(s) URL or just an integer ID — we replace the
# URL forms and leave IDs alone. `[^]]+` keeps the bracket scope correct.
URL_TOKEN_RE = re.compile(r"\[\[img:(https?://[^\]]+)\]\]")
TEXT_FIELDS = ("question_text", "option_a", "option_b", "option_c", "option_d",
               "explanation", "mnemonic", "concept_explanation")


def rewrite_field(text: str, url_to_id: dict[str, int], orphans: list[str]) -> str:
    if not text:
        return text
    def repl(match: re.Match) -> str:
        url = match.group(1)
        img_id = url_to_id.get(url)
        if img_id is None:
            orphans.append(url)
            return match.group(0)
        return f"[[img:{img_id}]]"
    return URL_TOKEN_RE.sub(repl, text)


def main(dry_run: bool = False) -> int:
    # Pre-load every QuestionImage.url + id mapping once (idempotent for big DBs).
    from questions.models import QuestionImage
    url_to_id: dict[str, int] = {}
    for img in QuestionImage.objects.exclude(url="").only("id", "url").iterator(chunk_size=2000):
        if img.url and img.url not in url_to_id:
            url_to_id[img.url] = img.id
    print(f"Loaded {len(url_to_id)} URL→id mappings from QuestionImage")

    qs = Question.objects.all().only("id", *TEXT_FIELDS)
    total = qs.count()
    print(f"Scanning {total} questions for [[img:URL]] tokens…")
    touched = 0
    orphan_total = 0
    samples: list[tuple[int, str, str]] = []

    for q in qs.iterator(chunk_size=500):
        per_question_urls = {img.url: img.id for img in q.images.exclude(url="").only("id", "url")}
        # Merge with the global map (in case the same URL is shared across Qs)
        merged = {**url_to_id, **per_question_urls}
        orphans: list[str] = []
        changed = False
        updates: dict[str, str] = {}
        for field in TEXT_FIELDS:
            original = getattr(q, field) or ""
            new = rewrite_field(original, merged, orphans)
            if new != original:
                changed = True
                updates[field] = new
        if orphan_total < 5:
            for u in orphans:
                samples.append((q.id, u, ""))
        if not changed:
            continue
        orphan_total += len(orphans)
        touched += 1
        if not dry_run:
            for k, v in updates.items():
                setattr(q, k, v)
            q.save(update_fields=list(updates.keys()))
    print(f"\nDry run: {dry_run}")
    print(f"Questions touched : {touched}")
    print(f"Orphan URLs left  : {orphan_total}")
    for qid, url, _ in samples[:5]:
        print(f"  orphan @ Q{qid}: {url[:90]}…")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry))