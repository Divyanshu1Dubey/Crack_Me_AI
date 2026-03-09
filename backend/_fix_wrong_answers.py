#!/usr/bin/env python
"""
Fix wrong answers by extracting correct answer from AI-generated explanations.
Detects mismatches between stored correct_answer and what the explanation says.
"""

import os
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

def extract_correct_answer_from_explanation(explanation, concept_explanation):
    """
    Parse explanations to find the correct answer.
    Looks for patterns like:
    - "The correct answer is X"
    - "correct answer is not A" (negative indicator)
    - "X is the correct answer"
    - "Why C is Correct" (section header)
    """
    if not explanation and not concept_explanation:
        return None
    
    combined = f"{explanation or ''}\n{concept_explanation or ''}"
    
    # Pattern 1: "Why X is Correct" (most reliable)
    match = re.search(r'Why\s+([A-D])\s+is\s+Correct', combined, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Pattern 2: "The correct answer is X" or "correct answer is X"
    match = re.search(r'correct answer is\s+([A-D])[:\s]', combined, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Pattern 3: "X is the correct answer"
    match = re.search(r'([A-D])\s+is\s+the\s+correct\s+answer', combined, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Pattern 4: "Option X is correct"
    match = re.search(r'Option\s+([A-D])\s+is\s+correct', combined, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    return None


def detect_mismatches(dry_run=True):
    """Detect and optionally fix answer mismatches."""
    
    questions = Question.objects.all().select_related('topic', 'subject')
    
    total_checked = 0
    has_explanation = 0
    mismatches = []
    fixed = 0
    
    print("=" * 80)
    print("SCANNING FOR ANSWER MISMATCHES")
    print("=" * 80)
    
    for q in questions:
        total_checked += 1
        
        if not q.explanation and not q.concept_explanation:
            continue
        
        has_explanation += 1
        
        # Extract what the explanation says is correct
        extracted_answer = extract_correct_answer_from_explanation(
            q.explanation, 
            q.concept_explanation
        )
        
        if not extracted_answer:
            continue
        
        # Compare with stored correct_answer
        stored_answer = q.correct_answer.strip().upper() if q.correct_answer else None
        
        if stored_answer and extracted_answer != stored_answer:
            mismatch_info = {
                'question_id': q.id,
                'year': q.year,
                'subject': q.subject.name if q.subject else 'N/A',
                'topic': q.topic.name if q.topic else 'N/A',
                'question_text': q.question_text[:100],
                'stored_answer': stored_answer,
                'explanation_says': extracted_answer,
                'question_obj': q
            }
            mismatches.append(mismatch_info)
            
            print(f"\n❌ MISMATCH #{len(mismatches)}")
            print(f"   ID: {q.id} | Year: {q.year} | {q.subject.name if q.subject else 'N/A'}")
            print(f"   Q: {q.question_text[:80]}...")
            print(f"   Options: A={q.option_a[:40]}... | B={q.option_b[:40]}... | C={q.option_c[:40]}... | D={q.option_d[:40]}...")
            print(f"   Database says: {stored_answer}")
            print(f"   Explanation says: {extracted_answer}")
            
            if not dry_run:
                q.correct_answer = extracted_answer
                q.save(update_fields=['correct_answer'])
                fixed += 1
                print(f"   ✅ FIXED: Updated to {extracted_answer}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total questions checked: {total_checked}")
    print(f"Questions with explanations: {has_explanation}")
    print(f"Mismatches found: {len(mismatches)}")
    if not dry_run:
        print(f"Mismatches fixed: {fixed}")
    else:
        print(f"\n⚠️  DRY RUN - No changes made. Run with --fix to apply changes.")
    
    if mismatches:
        print(f"\n📊 Mismatches by year:")
        year_counts = {}
        for m in mismatches:
            year_counts[m['year']] = year_counts.get(m['year'], 0) + 1
        for year in sorted(year_counts.keys()):
            print(f"   {year}: {year_counts[year]} mismatches")
    
    return mismatches


if __name__ == '__main__':
    import sys
    
    dry_run = '--fix' not in sys.argv
    
    if dry_run:
        print("🔍 RUNNING IN DRY-RUN MODE")
        print("   Add --fix flag to apply corrections\n")
    else:
        print("⚠️  FIX MODE ENABLED - Will update database\n")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    mismatches = detect_mismatches(dry_run=dry_run)
    
    if mismatches and dry_run:
        print(f"\n💡 To fix these {len(mismatches)} mismatches, run:")
        print(f"   python _fix_wrong_answers.py --fix")
