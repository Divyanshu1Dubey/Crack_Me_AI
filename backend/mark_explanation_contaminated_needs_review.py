"""Mark rows with contaminated or overly-long explanations as `needs_review`.

Some mocktest questions (e.g. Lynch-syndrome B4-style) had their `explanation`
field swallow the entire next-question's chapter text (TNM staging, etc.).
This script flags those rows so the AI backfill (`backfill_empty_ai`) will
regenerate the explanation from the actual question stem + correct answer.

Heuristics — a row is flagged if EITHER:
  - explanation > 800 chars (likely bled into next Q's content), OR
  - explanation mentions content unrelated to the question stem (heuristic
    based on the previous question's subject keywords).

The flagged rows are NOT deleted — just marked needs_review=True with a
verified_note so the UI shows them as 'needs verification' and the AI
backfill queue picks them up.
"""
import os
import re

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from django.db import transaction
from questions.models import Question


def main() -> None:
    LONG_EXPLANATION_THRESHOLD = 800
    flagged = 0
    with transaction.atomic():
        qs = (
            Question.objects.filter(source__endswith=".docx")
            .exclude(explanation="")
            .exclude(explanation__isnull=True)
        )
        for q in qs.iterator(chunk_size=200):
            expl = q.explanation or ""
            if len(expl) > LONG_EXPLANATION_THRESHOLD:
                q.needs_review = True
                q.verified_note = (
                    f"Explanation suspiciously long ({len(expl)} chars); "
                    "likely contains content from a neighbouring question. "
                    "AI backfill will regenerate."
                )
                q.save(update_fields=["needs_review", "verified_note"])
                flagged += 1
                continue
            # Heuristic: explanation starts with a topic that doesn't match the
            # stem (e.g. stem talks about Lynch syndrome but explanation
            # mentions TNM staging of colorectal cancer from the previous Q).
            stem_topic_match = re.match(r"\b([A-Z][a-z]+(?:\s+[a-z]+){0,3})", q.question_text or "")
            if not stem_topic_match:
                continue
            first_words = (q.question_text or "").lower()[:60]
            expl_lc = expl.lower()
            # Pull a couple of capitalized noun phrases from the explanation
            # and check whether any of them appear in the stem.
            suspects = re.findall(r"\b([A-Z][a-z]{3,}(?:\s+[A-Z]?[a-z]+){0,3})\b", expl[:400])
            for s in suspects:
                s_lc = s.lower()
                if s_lc not in first_words and len(s_lc) > 6:
                    q.needs_review = True
                    q.verified_note = (
                        f"Explanation opens with '{s}' which doesn't appear "
                        "in the stem; possible contamination. AI backfill will "
                        "regenerate."
                    )
                    q.save(update_fields=["needs_review", "verified_note"])
                    flagged += 1
                    break
    print(f"Flagged {flagged} rows as needs_review")


if __name__ == "__main__":
    main()