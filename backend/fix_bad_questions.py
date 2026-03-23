"""
Fix incorrectly parsed questions that were split due to statement numbers.
This script finds and removes bad parses like "It is painless" (statement 4 of Q38 about glomus tumour)
and re-imports the correct full questions.
"""
import os, sys, re, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Question

# Known bad parses - questions that are actually statements within other questions
# These have very short text or contain only a single statement
BAD_QUESTION_PATTERNS = [
    r'^It is painless\.?$',       # Statement 4 of Q38 (glomus tumour)
    r'^It is \w+ only\.?$',       # Generic "It is X only" patterns
    r'^\d+\s*$',                   # Just a number
    r'^[A-Z][a-z]+ only\.?$',     # Single word + "only"
]

def find_bad_questions():
    """Find questions that appear to be incorrectly parsed (too short or matching bad patterns)."""
    bad_questions = []

    # Questions with very short text (< 20 chars) are suspicious
    short_questions = Question.objects.filter(question_text__regex=r'^.{1,20}$')

    for q in short_questions:
        text = q.question_text.strip()
        # Check if it matches known bad patterns
        for pattern in BAD_QUESTION_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                bad_questions.append(q)
                break
        else:
            # Also flag very short questions for manual review
            if len(text) < 15:
                bad_questions.append(q)

    # Also find questions that look like they're missing context
    # (questions where options are like "1, 2 and 3", "2, 3 and 4")
    option_pattern_questions = Question.objects.filter(
        option_a__regex=r'^\d+,?\s*\d+\s*(and|&)\s*\d+$'
    )
    for q in option_pattern_questions:
        text = q.question_text.strip()
        # If question text doesn't contain "which" or "following", it's likely a bad parse
        if not re.search(r'(which|following|correct|true|false)', text, re.IGNORECASE):
            if q not in bad_questions:
                bad_questions.append(q)

    return bad_questions


def main():
    print("="*60)
    print("FINDING INCORRECTLY PARSED QUESTIONS")
    print("="*60)

    bad_questions = find_bad_questions()

    if not bad_questions:
        print("No obviously bad questions found!")
        return

    print(f"\nFound {len(bad_questions)} potentially bad questions:\n")

    for i, q in enumerate(bad_questions, 1):
        print(f"{i}. ID={q.id}, Year={q.year}")
        print(f"   Text: {q.question_text[:100]}")
        print(f"   Options: A={q.option_a[:30]}... | B={q.option_b[:30]}...")
        print()

    # Ask for confirmation before deleting
    response = input(f"\nDelete these {len(bad_questions)} bad questions? (yes/no): ")

    if response.lower() == 'yes':
        ids = [q.id for q in bad_questions]
        count = Question.objects.filter(id__in=ids).delete()[0]
        print(f"\nDeleted {count} bad questions.")
        print("\nNow run '_import_pyq_txt.py' to re-import questions with fixed parser.")
    else:
        print("\nNo changes made.")


if __name__ == '__main__':
    main()
