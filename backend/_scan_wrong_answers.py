#!/usr/bin/env python
"""
Identify potentially wrong answers using medical knowledge patterns.
Flags questions that need human review.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

# Common medical knowledge patterns
PATTERNS = {
    # Upper Motor Neuron signs (UMN)
    'umn_features': {
        'keywords': ['upper motor neuron', 'umn lesion', 'pyramidal tract'],
        'correct_features': ['clonus', 'hyperreflexia', 'spasticity', 'babinski', 'hyperactive reflex'],
        'wrong_features': ['fasciculation', 'muscle wasting', 'hyporeflexia', 'flaccid', 'atrophy'],
        'explanation': 'UMN lesions cause hyperreflexia, spasticity, clonus. Fasciculations/wasting are LMN signs.'
    },
    
    # Lower Motor Neuron signs (LMN)
    'lmn_features': {
        'keywords': ['lower motor neuron', 'lmn lesion', 'anterior horn'],
        'correct_features': ['fasciculation', 'muscle wasting', 'hyporeflexia', 'flaccid', 'atrophy'],
        'wrong_features': ['clonus', 'hyperreflexia', 'spasticity', 'babinski'],
        'explanation': 'LMN lesions cause fasciculations, wasting, hyporeflexia. Clonus/hyperreflexia are UMN signs.'
    },
    
    # Type 1 vs Type 2 Diabetes
    'diabetes_type1': {
        'keywords': ['type 1 diabetes', 'iddm', 'juvenile diabetes'],
        'correct_features': ['insulin', 'ketoacidosis', 'autoimmune', 'young', 'dka'],
        'wrong_features': ['metformin', 'lifestyle', 'obesity related', 'adult onset'],
        'explanation': 'Type 1 DM is autoimmune, requires insulin. Type 2 is lifestyle/obesity related.'
    },
    
    # Pleural effusion - transudate vs exudate
    'transudate': {
        'keywords': ['transudate', 'transudative effusion'],
        'correct_features': ['heart failure', 'nephrotic', 'cirrhosis', 'low protein'],
        'wrong_features': ['infection', 'malignancy', 'empyema', 'high protein'],
        'explanation': 'Transudates have low protein (<3g/dL), seen in CHF/cirrhosis. Exudates are high protein (infection/malignancy).'
    },
}

def check_question_pattern(question: Question):
    """
    Check if question matches known medical patterns.
    Returns list of potential issues.
    """
    issues = []
    
    q_text = question.question_text.lower()
    options = [
        question.option_a.lower(),
        question.option_b.lower(),
        question.option_c.lower(),
        question.option_d.lower()
    ]
    
    current_answer_idx = ord(question.correct_answer.upper()) - ord('A') if question.correct_answer else -1
    current_answer_text = options[current_answer_idx] if 0 <= current_answer_idx < 4 else ''
    
    for pattern_name, pattern in PATTERNS.items():
        # Check if question matches pattern keywords
        matches_keywords = any(keyword in q_text for keyword in pattern['keywords'])
        
        if matches_keywords:
            # Check if current answer has WRONG features
            has_wrong_feature = any(
                wrong in current_answer_text 
                for wrong in pattern['wrong_features']
            )
            
            if has_wrong_feature:
                # Find options with CORRECT features
                correct_options = []
                for i, opt in enumerate(options):
                    if any(correct in opt for correct in pattern['correct_features']):
                        correct_options.append(chr(ord('A') + i))
                
                issues.append({
                    'pattern': pattern_name,
                    'reason': pattern['explanation'],
                    'current_answer': question.correct_answer,
                    'suspected_correct': correct_options
                })
    
    return issues

def scan_for_wrong_answers(year=None, limit=None):
    """Scan questions for potential wrong answers."""
    
    print("=" * 80)
    print("SCANNING FOR POTENTIALLY WRONG ANSWERS")
    print("=" * 80)
    print("Using medical knowledge patterns to flag suspicious answers")
    print("=" * 80)
    print()
    
    qs = Question.objects.filter(correct_answer__isnull=False).exclude(correct_answer='')
    qs = qs.select_related('subject', 'topic')
    
    if year:
        qs = qs.filter(year=year)
    
    if limit:
        qs = qs[:limit]
    
    flagged = []
    
    for q in qs:
        issues = check_question_pattern(q)
        
        if issues:
            flagged.append({
                'question': q,
                'issues': issues
            })
    
    # Display results
    print(f"Scanned: {qs.count()} questions")
    print(f"Flagged: {len(flagged)} potential issues")
    print()
    
    if flagged:
        print("⚠️  QUESTIONS FLAGGED FOR REVIEW:")
        print("=" * 80)
        
        for i, item in enumerate(flagged, 1):
            q = item['question']
            
            print(f"\n#{i}. Question ID: {q.id} ({q.year}) - {q.subject.name if q.subject else 'N/A'}")
            print(f"   Question: {q.question_text[:100]}...")
            print(f"   Current Answer: {q.correct_answer}")
            print(f"   Options:")
            print(f"      A) {q.option_a}")
            print(f"      B) {q.option_b}")
            print(f"      C) {q.option_c}")
            print(f"      D) {q.option_d}")
            
            for issue in item['issues']:
                print(f"\n   ⚠️  ISSUE: {issue['pattern']}")
                print(f"      Reason: {issue['reason']}")
                print(f"      Current answer: {issue['current_answer']}")
                if issue['suspected_correct']:
                    print(f"      Suspected correct: {', '.join(issue['suspected_correct'])}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Review each flagged question manually")
    print("2. Verify against medical textbooks/references")
    print("3. Add corrections to _manual_fix_answers.py")
    print("4. Run: python _manual_fix_answers.py --fix")
    print("5. Run: python _export_fixture.py")
    print("6. Commit and deploy")
    
    return flagged

if __name__ == '__main__':
    import sys
    
    year = None
    limit = None
    
    if '--year' in sys.argv:
        idx = sys.argv.index('--year')
        year = int(sys.argv[idx + 1])
    
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        limit = int(sys.argv[idx + 1])
    
    scan_for_wrong_answers(year=year, limit=limit)
