"""
Comprehensive script to fix incomplete/malformed questions in the database.
Features:
1. Identifies questions with missing data (options, correct_answer)
2. Finds short/fragment questions like "It is painless"
3. Validates question-answer consistency
4. Reports issues for manual review
"""
import os, sys, re, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Subject, Question
from django.db.models import Q

# Known bad patterns
BAD_QUESTION_PATTERNS = [
    r'^It is painless\.?$',
    r'^It is \w+\.?$',
    r'^It is \w+ only\.?$',
    r'^\d+\s*$',
    r'^[A-Z][a-z]+ only\.?$',
    r'^True$',
    r'^False$',
    r'^All of the above$',
    r'^None of the above$',
    r'^[A-D]$',
    r'^Option [A-D]$',
]

def find_all_issues():
    """Find all issues with questions in the database."""
    issues = {
        'missing_correct_answer': [],
        'empty_options': [],
        'too_short': [],
        'bad_pattern': [],
        'invalid_answer': [],
        'answer_points_to_empty': [],
        'numbered_options_no_context': [],
    }

    total = Question.objects.count()
    print(f"Scanning {total} questions for issues...")

    for q in Question.objects.all():
        # 1. Missing correct_answer
        if not q.correct_answer or q.correct_answer not in ['A', 'B', 'C', 'D']:
            issues['invalid_answer'].append({
                'id': q.id,
                'year': q.year,
                'text': q.question_text[:100],
                'correct_answer': q.correct_answer,
                'reason': 'Invalid or missing correct_answer'
            })
            continue

        # 2. Check for empty options
        options = {
            'A': (q.option_a or '').strip(),
            'B': (q.option_b or '').strip(),
            'C': (q.option_c or '').strip(),
            'D': (q.option_d or '').strip(),
        }
        empty_opts = [k for k, v in options.items() if not v]
        if empty_opts:
            issues['empty_options'].append({
                'id': q.id,
                'year': q.year,
                'text': q.question_text[:100],
                'empty_options': empty_opts,
                'reason': f'Empty options: {empty_opts}'
            })

        # 3. Answer points to empty option
        if q.correct_answer and not options.get(q.correct_answer):
            issues['answer_points_to_empty'].append({
                'id': q.id,
                'year': q.year,
                'text': q.question_text[:100],
                'correct_answer': q.correct_answer,
                'reason': f'Answer {q.correct_answer} points to empty option'
            })

        # 4. Question text too short
        text = (q.question_text or '').strip()
        if len(text) < 15:
            issues['too_short'].append({
                'id': q.id,
                'year': q.year,
                'text': text,
                'reason': f'Question too short: {len(text)} chars'
            })

        # 5. Bad pattern match
        for pattern in BAD_QUESTION_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                issues['bad_pattern'].append({
                    'id': q.id,
                    'year': q.year,
                    'text': text,
                    'pattern': pattern,
                    'reason': 'Matches bad pattern (likely statement fragment)'
                })
                break

        # 6. Numbered options without proper context
        if re.match(r'^\d+,?\s*\d+\s*(and|&)\s*\d+$', options['A'], re.IGNORECASE):
            if not re.search(r'(which|following|correct|true|false|statement|assertion)', text, re.IGNORECASE):
                issues['numbered_options_no_context'].append({
                    'id': q.id,
                    'year': q.year,
                    'text': text[:100],
                    'options': options,
                    'reason': 'Options like "1,2 and 3" but no context in question'
                })

    return issues


def print_report(issues):
    """Print a detailed report of all issues."""
    print("\n" + "="*70)
    print("QUESTION DATABASE ISSUES REPORT")
    print("="*70)

    total_issues = sum(len(v) for v in issues.values())
    print(f"\nTotal issues found: {total_issues}")

    for category, items in issues.items():
        if items:
            print(f"\n{'='*60}")
            print(f"CATEGORY: {category.replace('_', ' ').upper()} ({len(items)} issues)")
            print('='*60)

            for i, item in enumerate(items[:10], 1):  # Show first 10
                print(f"\n  {i}. Question ID: {item['id']}, Year: {item['year']}")
                print(f"     Text: {item['text']}")
                print(f"     Issue: {item['reason']}")

            if len(items) > 10:
                print(f"\n  ... and {len(items) - 10} more with same issue")


def fix_questions_auto(issues, dry_run=True):
    """Attempt automatic fixes for some issues."""
    fixes_made = 0

    # Fix invalid correct_answers if we can infer them
    for item in issues['invalid_answer']:
        q = Question.objects.filter(id=item['id']).first()
        if not q:
            continue

        # Try to infer from similar questions or explanations
        if q.correct_answer and q.correct_answer.upper() in ['A', 'B', 'C', 'D']:
            if not dry_run:
                q.correct_answer = q.correct_answer.upper()
                q.save()
            fixes_made += 1
            print(f"  Fixed Q{q.id}: normalized correct_answer to {q.correct_answer.upper()}")

    # Deactivate clearly bad questions (fragments)
    for item in issues['bad_pattern']:
        q = Question.objects.filter(id=item['id']).first()
        if not q:
            continue

        if not dry_run:
            q.is_active = False
            q.save()
        fixes_made += 1
        print(f"  Deactivated Q{q.id}: '{item['text']}' (fragment)")

    # Deactivate questions that are too short
    for item in issues['too_short']:
        q = Question.objects.filter(id=item['id']).first()
        if not q:
            continue

        if not dry_run:
            q.is_active = False
            q.save()
        fixes_made += 1
        print(f"  Deactivated Q{q.id}: '{item['text']}' (too short)")

    return fixes_made


def export_for_manual_review(issues, filename='manual_review_needed.txt'):
    """Export issues that need manual review."""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("QUESTIONS NEEDING MANUAL REVIEW\n")
        f.write("=" * 70 + "\n\n")

        for category, items in issues.items():
            if items:
                f.write(f"\n## {category.upper()}\n")
                f.write("-" * 40 + "\n\n")

                for item in items:
                    f.write(f"ID: {item['id']}, Year: {item['year']}\n")
                    f.write(f"Text: {item['text']}\n")
                    f.write(f"Issue: {item['reason']}\n")
                    f.write("\n")

    print(f"\nExported to {filename}")


def main():
    print("="*70)
    print("COMPREHENSIVE QUESTION DATABASE FIX TOOL")
    print("="*70)

    issues = find_all_issues()
    print_report(issues)

    total_issues = sum(len(v) for v in issues.values())

    if total_issues == 0:
        print("\nNo issues found! Database looks clean.")
        return

    print("\n" + "="*70)
    print("OPTIONS:")
    print("1. Export issues for manual review (recommended)")
    print("2. Auto-fix what's possible (dry run - preview only)")
    print("3. Auto-fix and save changes")
    print("4. Exit without changes")
    print("="*70)

    choice = input("\nChoose an option (1-4): ").strip()

    if choice == '1':
        export_for_manual_review(issues)
    elif choice == '2':
        print("\n--- DRY RUN (no changes will be saved) ---")
        fixes = fix_questions_auto(issues, dry_run=True)
        print(f"\nWould fix {fixes} questions")
    elif choice == '3':
        confirm = input("\nThis will modify the database. Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            fixes = fix_questions_auto(issues, dry_run=False)
            print(f"\nFixed {fixes} questions")
        else:
            print("Cancelled.")
    else:
        print("Exiting without changes.")


if __name__ == '__main__':
    main()
