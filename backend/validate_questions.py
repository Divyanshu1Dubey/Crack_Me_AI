"""
validate_questions.py — Data quality validation pipeline for CrackCMS question bank.

Checks:
1. Missing correct_answer
2. Duplicate questions (fuzzy matching)
3. Invalid option format (missing options)
4. Answer not in valid options
5. Summary report with actionable items

Usage: cd backend && python validate_questions.py
"""
import os
import sys
import json
from difflib import SequenceMatcher
from collections import Counter

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from questions.models import Question


def check_missing_answers():
    """Find questions with missing or empty correct_answer."""
    missing = Question.objects.filter(correct_answer='')
    blank = Question.objects.filter(correct_answer__isnull=True)
    results = list(missing | blank)
    return results


def check_missing_options():
    """Find questions where any of the 4 options are empty."""
    issues = []
    for q in Question.objects.all():
        missing = []
        if not q.option_a or not q.option_a.strip():
            missing.append('A')
        if not q.option_b or not q.option_b.strip():
            missing.append('B')
        if not q.option_c or not q.option_c.strip():
            missing.append('C')
        if not q.option_d or not q.option_d.strip():
            missing.append('D')
        if missing:
            issues.append((q.id, q.question_text[:80], missing))
    return issues


def check_invalid_answers():
    """Find questions where correct_answer is not A, B, C, or D."""
    valid_answers = {'A', 'B', 'C', 'D', 'a', 'b', 'c', 'd'}
    issues = []
    for q in Question.objects.exclude(correct_answer='').exclude(correct_answer__isnull=True):
        if q.correct_answer.strip() not in valid_answers:
            issues.append((q.id, q.question_text[:80], q.correct_answer))
    return issues


def check_duplicates(threshold=0.85):
    """Find potential duplicate questions using fuzzy matching."""
    questions = list(Question.objects.values_list('id', 'question_text'))
    duplicates = []
    seen = set()

    for i in range(len(questions)):
        if questions[i][0] in seen:
            continue
        for j in range(i + 1, len(questions)):
            if questions[j][0] in seen:
                continue
            ratio = SequenceMatcher(
                None,
                questions[i][1].lower().strip(),
                questions[j][1].lower().strip()
            ).ratio()
            if ratio >= threshold:
                duplicates.append((questions[i][0], questions[j][0], round(ratio, 3)))
                seen.add(questions[j][0])

    return duplicates


def check_answer_option_mismatch():
    """Find questions where correct_answer letter doesn't match any option text."""
    issues = []
    for q in Question.objects.exclude(correct_answer='').exclude(correct_answer__isnull=True):
        answer = q.correct_answer.strip().upper()
        option_map = {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d}
        if answer in option_map and (not option_map[answer] or not option_map[answer].strip()):
            issues.append((q.id, q.question_text[:80], answer, 'Option is empty'))
    return issues


def generate_report():
    """Run all checks and print a summary report."""
    print("=" * 70)
    print("CrackCMS Question Validation Report")
    print("=" * 70)

    total = Question.objects.count()
    print(f"\nTotal questions: {total}")

    # Subject distribution
    print("\n--- Subject Distribution ---")
    for q in Question.objects.values('subject__name').annotate(
        count=__import__('django.db.models', fromlist=['Count']).Count('id')
    ).order_by('-count'):
        print(f"  {q['subject__name'] or 'No Subject'}: {q['count']}")

    # Check 1: Missing answers
    print("\n--- Check 1: Missing Correct Answer ---")
    missing = check_missing_answers()
    print(f"  Found: {len(missing)} questions without correct_answer")
    for q in missing[:10]:
        print(f"    ID {q.id}: {q.question_text[:60]}...")

    # Check 2: Missing options
    print("\n--- Check 2: Missing Options ---")
    options_issues = check_missing_options()
    print(f"  Found: {len(options_issues)} questions with missing options")
    for qid, text, opts in options_issues[:10]:
        print(f"    ID {qid}: Missing option(s) {', '.join(opts)} — {text}...")

    # Check 3: Invalid answer values
    print("\n--- Check 3: Invalid Answer Values ---")
    invalid = check_invalid_answers()
    print(f"  Found: {len(invalid)} questions with non-ABCD answers")
    for qid, text, ans in invalid[:10]:
        print(f"    ID {qid}: Answer='{ans}' — {text}...")

    # Check 4: Answer references empty option
    print("\n--- Check 4: Answer Points to Empty Option ---")
    mismatches = check_answer_option_mismatch()
    print(f"  Found: {len(mismatches)} questions where answer option is empty")
    for qid, text, ans, reason in mismatches[:10]:
        print(f"    ID {qid}: Answer={ans}, {reason} — {text}...")

    # Check 5: Duplicates (can be slow for large datasets)
    print("\n--- Check 5: Duplicate Detection (threshold=0.85) ---")
    print("  Running fuzzy matching (this may take a moment)...")
    dupes = check_duplicates(threshold=0.85)
    print(f"  Found: {len(dupes)} potential duplicate pairs")
    for id1, id2, ratio in dupes[:10]:
        print(f"    IDs {id1} ↔ {id2}: similarity={ratio}")

    # Summary
    total_issues = len(missing) + len(options_issues) + len(invalid) + len(mismatches) + len(dupes)
    print("\n" + "=" * 70)
    print(f"SUMMARY: {total_issues} total issues found across {total} questions")
    if total_issues == 0:
        print("✅ All checks passed — question bank is clean!")
    else:
        print("⚠️  Review the issues above and fix them.")
    print("=" * 70)

    return {
        'total_questions': total,
        'missing_answers': len(missing),
        'missing_options': len(options_issues),
        'invalid_answers': len(invalid),
        'answer_mismatches': len(mismatches),
        'duplicates': len(dupes),
        'total_issues': total_issues,
    }


if __name__ == '__main__':
    report = generate_report()
    # Save report as JSON
    with open('validation_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to validation_report.json")
