#!/usr/bin/env python
"""
Manually fix known wrong answers based on medical accuracy.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

# Known corrections (question_id, correct_answer, explanation)
CORRECTIONS = [
    {
        'id': 35,  # Upper motor neuron lesion question
        'correct_answer': 'C',  # Clonus is correct, not Fasciculations
        'explanation': 'The characteristic features of upper motor neuron (UMN) lesions include clonus, hyperreflexia, spasticity, and positive Babinski sign. Clonus is rhythmic muscle contractions occurring with sustained stretch. Fasciculations and muscle wasting are features of lower motor neuron lesions.',
        'mnemonic': 'CLONUS mnemonic: C-Clonus, L-Loss of inhibition, O-Overactive reflexes, N-No muscle wasting initially, U-Upper motor damage, S-Spasticity.',
        'concept_tags': ['Upper Motor Neuron', 'Neurological Examination', 'Clonus', 'Spasticity', 'Pyramidal Signs']
    },
    # Add more corrections here as you identify them
]

def apply_corrections(dry_run=True):
    """Apply manual corrections to questions with wrong answers."""
    
    print("=" * 80)
    print("MANUAL ANSWER CORRECTIONS")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE - Will save changes'}")
    print(f"Total corrections to apply: {len(CORRECTIONS)}\n")
    
    applied = 0
    not_found = 0
    
    for correction in CORRECTIONS:
        qid = correction['id']
        try:
            q = Question.objects.get(pk=qid)
            
            print(f"\nQuestion #{qid} ({q.year})")
            print(f"   Text: {q.question_text[:80]}...")
            print(f"   Old answer: {q.correct_answer}")
            print(f"   New answer: {correction['correct_answer']}")
            
            if not dry_run:
                q.correct_answer = correction['correct_answer']
                if 'explanation' in correction:
                    q.explanation = correction['explanation']
                if 'mnemonic' in correction:
                    q.mnemonic = correction['mnemonic']
                if 'concept_tags' in correction:
                    q.concept_tags = correction['concept_tags']
                q.save()
                print(f"   ✅ APPLIED")
                applied += 1
            else:
                print(f"   🔍 Would apply (dry run)")
            
        except Question.DoesNotExist:
            print(f"\n❌ Question #{qid} not found")
            not_found += 1
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total corrections: {len(CORRECTIONS)}")
    print(f"Applied: {applied}")
    print(f"Not found: {not_found}")
    
    if dry_run:
        print(f"\n⚠️  DRY RUN - No changes saved")
        print(f"   Run with --fix to apply changes")
    else:
        print(f"\n✅ Changes saved!")
        print(f"   Run: python _export_fixture.py")
        print(f"   Then commit and deploy")

if __name__ == '__main__':
    import sys
    dry_run = '--fix' not in sys.argv
    
    if not dry_run:
        print("⚠️  This will modify the database!")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    apply_corrections(dry_run=dry_run)
