#!/usr/bin/env python
"""
Fix wrong answers and enrich with AI-generated explanations.
For each question without a saved explanation:
1. Generate AI explanation and extract correct answer
2. Update both correct_answer and explanation fields
3. Save to database
"""

import os
import re
import sys
import time
import json
import django
from typing import Optional, Dict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question
from ai_engine.services import AIService

def extract_correct_answer_from_ai_response(response_text: str) -> Optional[str]:
    """
    Extract the correct answer from AI response.
    Looks for patterns like:
    - "correct answer is X"
    - "Answer: X"
    - "the answer is X"
    """
    if not response_text:
        return None
    
    # Pattern 1: "correct answer is X" or "Correct Answer: X"
    match = re.search(r'correct\s+answer\s*:?\s*is\s*([A-D])', response_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Pattern 2: "Answer: X" or "Answer is X"
    match = re.search(r'answer\s*:?\s*is\s*([A-D])', response_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Pattern 3: "the answer is X"
    match = re.search(r'the\s+answer\s+is\s+([A-D])', response_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Pattern 4: Line starting with "Answer:" followed by option
    match = re.search(r'^answer\s*:\s*([A-D])', response_text, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).upper()
    
    return None


def create_ai_prompt(question: Question) -> str:
    """Create prompt for AI to analyze question and provide correct answer."""
    
    prompt = f"""Analyze this UPSC CMS medical question and provide the CORRECT answer.
Return strict JSON format ONLY.

Question: {question.question_text}

Options:
A) {question.option_a}
B) {question.option_b}
C) {question.option_c}
D) {question.option_d}

Return JSON object with these keys:
{{
  "correct_answer": "A|B|C|D",
  "explanation": "Brief 2-3 sentence explanation",
  "mnemonic": "Memory trick (optional)",
  "concept_tags": ["tag1", "tag2", "tag3"]
}}

Rules:
- correct_answer must be exactly A, B, C, or D
- Be concise and exam-focused
- Return valid JSON only"""
    
    return prompt


def process_question(question: Question, ai_service: AIService, dry_run: bool = True) -> Dict:
    """
    Process a single question:
    1. Generate AI explanation
    2. Extract correct answer
    3. Update database
    
    Returns dict with processing results.
    """
    
    result = {
        'question_id': question.id,
        'year': question.year,
        'old_answer': question.correct_answer,
        'new_answer': None,
        'answer_changed': False,
        'explanation_added': False,
        'error': None
    }
    
    try:
        # Create prompt and get AI response
        prompt = create_ai_prompt(question)
        ai_response = ai_service._call_ai(
            prompt,
            system="You are a medical data quality assistant. Return valid JSON only.",
            temperature=0.1,
            max_tokens=900
        )
        
        if not ai_response:
            result['error'] = 'Empty AI response'
            return result
        
        # Parse JSON response
        import json
        match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if not match:
            result['error'] = 'No JSON found in AI response'
            return result
        
        payload = json.loads(match.group(0))
        extracted_answer = str(payload.get('correct_answer', '')).strip().upper()
        
        if extracted_answer not in ('A', 'B', 'C', 'D'):
            result['error'] = f'Invalid answer: {extracted_answer}'
            return result
        
        result['new_answer'] = extracted_answer
        
        # Extract other fields from JSON
        explanation = str(payload.get('explanation', '')).strip()
        mnemonic = str(payload.get('mnemonic', '')).strip()
        tags = payload.get('concept_tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',')]
        
        # Check if answer needs updating
        current_stored = question.correct_answer.strip().upper() if question.correct_answer else None
        if current_stored != extracted_answer:
            result['answer_changed'] = True
            
            if not dry_run:
                question.correct_answer = extracted_answer
                question.explanation = explanation[:1000] if explanation else ""
                question.mnemonic = mnemonic[:500] if mnemonic else ""
                question.concept_tags = tags[:5]
                question.save(update_fields=['correct_answer', 'explanation', 'mnemonic', 'concept_tags'])
                result['explanation_added'] = True
        
        elif not question.explanation and explanation:
            # Answer is correct, but add explanation if missing
            if not dry_run:
                question.explanation = explanation[:1000]
                question.mnemonic = mnemonic[:500] if mnemonic else ""
                question.concept_tags = tags[:5]
                question.save(update_fields=['explanation', 'mnemonic', 'concept_tags'])
                result['explanation_added'] = True
        
    except json.JSONDecodeError as e:
        result['error'] = f'JSON parse error: {e}'
    except Exception as e:
        result['error'] = str(e)
    
    return result


def main(year_filter: Optional[int] = None, limit: int = 50, dry_run: bool = True, 
         sleep_ms: int = 1000):
    """
    Main processing function.
    
    Args:
        year_filter: Only process questions from this year (None = all years)
        limit: Maximum number of questions to process
        dry_run: If True, don't save changes
        sleep_ms: Milliseconds to sleep between AI calls
    """
    
    # Initialize AI service
    try:
        ai_service = AIService()
    except Exception as e:
        print(f"❌ Failed to initialize AI service: {e}")
        return
    
    print("=" * 80)
    print("AI ANSWER VALIDATION & ENRICHMENT")
    print("=" * 80)
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be saved")
    else:
        print("⚠️  LIVE MODE - Changes will be saved to database")
    print(f"Year filter: {year_filter or 'All years'}")
    print(f"Limit: {limit} questions")
    print(f"Sleep: {sleep_ms}ms between calls")
    print("=" * 80)
    
    # Query questions
    qs = Question.objects.all().select_related('subject', 'topic')
    
    if year_filter:
        qs = qs.filter(year=year_filter)
    
    # Prioritize questions without explanations
    qs = qs.order_by('explanation', 'year')
    
    total = qs.count()
    qs = qs[:limit]
    
    print(f"\nTotal questions in filter: {total}")
    print(f"Processing: {qs.count()}\n")
    
    results = {
        'processed': 0,
        'answers_changed': 0,
        'explanations_added': 0,
        'errors': 0,
        'changes': []
    }
    
    for i, question in enumerate(qs, 1):
        print(f"\n[{i}/{min(limit, total)}] Processing Q#{question.id} ({question.year})...")
        print(f"   Q: {question.question_text[:80]}...")
        print(f"   Current answer: {question.correct_answer or 'NONE'}")
        
        result = process_question(question, ai_service, dry_run=dry_run)
        results['processed'] += 1
        
        if result['error']:
            print(f"   ❌ Error: {result['error']}")
            results['errors'] += 1
        else:
            if result['answer_changed']:
                print(f"   🔄 Answer: {result['old_answer']} → {result['new_answer']}")
                results['answers_changed'] += 1
                results['changes'].append({
                    'id': question.id,
                    'year': question.year,
                    'old': result['old_answer'],
                    'new': result['new_answer']
                })
            else:
                print(f"   ✅ Answer validated: {result['new_answer']}")
            
            if result['explanation_added']:
                print(f"   📝 Explanation added")
                results['explanations_added'] += 1
        
        # Rate limiting
        if i < min(limit, total):
            time.sleep(sleep_ms / 1000.0)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Questions processed: {results['processed']}")
    print(f"Answers corrected: {results['answers_changed']}")
    print(f"Explanations added: {results['explanations_added']}")
    print(f"Errors: {results['errors']}")
    
    if results['changes']:
        print(f"\n📋 ANSWER CORRECTIONS:")
        for change in results['changes']:
            print(f"   Q#{change['id']} ({change['year']}): {change['old']} → {change['new']}")
    
    if dry_run:
        print(f"\n⚠️  DRY RUN - No changes saved")
        print(f"   Run with --fix to apply {results['answers_changed']} corrections")
    else:
        print(f"\n✅ All changes saved to database")
        print(f"   Run: python _export_fixture.py")
        print(f"   Then commit and deploy")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix wrong answers using AI validation')
    parser.add_argument('--year', type=int, help='Only process this year')
    parser.add_argument('--limit', type=int, default=50, help='Max questions to process')
    parser.add_argument('--fix', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--sleep-ms', type=int, default=1000, 
                       help='Milliseconds between AI calls')
    
    args = parser.parse_args()
    
    dry_run = not args.fix
    
    if not dry_run:
        print("⚠️  WARNING: This will modify the database!")
        print(f"   Year: {args.year or 'All'}")
        print(f"   Limit: {args.limit}")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    main(
        year_filter=args.year,
        limit=args.limit,
        dry_run=dry_run,
        sleep_ms=args.sleep_ms
    )
