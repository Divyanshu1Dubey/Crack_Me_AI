"""
Batch Question Enrichment Script for CrackCMS
Uses Groq (Llama 3.3 70B) to enrich ALL questions with:
- correct_answer (verify/fix)
- explanation
- concept_explanation
- mnemonic
- concept_tags
- concept_keywords
- book_name, chapter
- learning_technique
- shortcut_tip
- difficulty (easy/medium/hard)

Processes 5 questions per API call. Auto-saves progress every batch.
Resume-safe: skips already enriched questions.

Usage:
    python enrich_questions.py                  # enrich all
    python enrich_questions.py --start 100      # start from index 100
    python enrich_questions.py --batch 3        # 3 questions per batch
    python enrich_questions.py --limit 50       # only process 50 questions
"""
import json
import os
import sys
import time
import re
import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

FIXTURE_FILE = Path(__file__).parent / 'questions_fixture.json'
PROGRESS_FILE = Path(__file__).parent / 'enrich_progress.json'
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Rate limit: Groq free tier = 30 req/min, 6000 tokens/min for llama-3.3-70b
REQUESTS_PER_MIN = 25  # stay under limit
DELAY_BETWEEN_BATCHES = 2.5  # seconds


SYSTEM_PROMPT = """You are a UPSC CMS (Combined Medical Services) exam expert with deep knowledge of medical sciences.
You will be given medical MCQs from UPSC CMS Previous Year Papers.

For EACH question, provide a JSON object with these fields:
- "correct_answer": The correct option letter (A, B, C, or D). Use your medical expertise to determine the right answer.
- "explanation": A clear 2-4 sentence explanation of WHY the correct answer is right. Include the key medical fact.
- "concept_explanation": A brief concept overview (1-2 sentences) about the underlying medical topic.
- "mnemonic": A short mnemonic or memory aid if applicable. Use "" if not applicable.
- "concept_tags": Array of 2-4 relevant medical topic tags (e.g., ["Cardiology", "Valvular Heart Disease"]).
- "concept_keywords": Array of 3-6 important keywords from the question/answer (e.g., ["carcinoid", "tricuspid", "serotonin"]).
- "book_name": Most relevant standard textbook (e.g., "Harrison's Principles of Internal Medicine", "Robbins Pathology", "Park's Preventive Medicine", "Bailey & Love's Surgery", "KDT Pharmacology", etc.)
- "chapter": Relevant chapter/section name.
- "difficulty": "easy", "medium", or "hard" based on UPSC CMS standards.
- "learning_technique": One practical study tip for this topic (1 sentence).
- "shortcut_tip": A quick exam trick or elimination strategy if applicable. Use "" if not applicable.

CRITICAL RULES:
1. Answer MUST be A, B, C, or D only.
2. Use standard medical textbook knowledge.
3. If unsure between options, pick the most commonly accepted answer in Indian medical PG exams.
4. Keep explanations concise but accurate.
5. For PSM/Preventive Medicine questions, prefer Park's textbook references.
6. For Pharmacology, prefer KDT or Tripathi.
7. For Pathology, prefer Robbins.
8. For Medicine, prefer Harrison's.
9. For Surgery, prefer Bailey & Love's or SRB.
10. For Anatomy, prefer BD Chaurasia or Gray's.

Return ONLY a JSON array with one object per question. No markdown, no extra text."""


def build_question_prompt(questions_batch):
    """Build the prompt for a batch of questions."""
    parts = []
    for i, q in enumerate(questions_batch):
        f = q['fields']
        text = f.get('question_text', '').strip()
        opts = []
        for letter in ['a', 'b', 'c', 'd']:
            opt = f.get(f'option_{letter}', '').strip()
            if opt:
                opts.append(f"({letter.upper()}) {opt}")
        year = f.get('year', '')
        paper = f.get('paper', '')

        parts.append(f"Q{i+1} [PK={q['pk']}, Year={year}, Paper={paper}]:\n{text}\n" + "\n".join(opts))

    return "Answer ALL the following UPSC CMS MCQs:\n\n" + "\n\n".join(parts)


def call_groq(prompt, retries=3):
    """Call Groq API with retry logic."""
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt}
                ],
                max_tokens=4096,
                temperature=0.1,
            )
            text = response.choices[0].message.content.strip()
            return text
        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate' in err_str.lower():
                wait = 30 * (attempt + 1)
                logger.warning(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"Groq error (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(5)
    return None


def call_gemini(prompt, retries=3):
    """Call Gemini API as fallback."""
    try:
        from google import genai
    except ImportError:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"{SYSTEM_PROMPT}\n\n{prompt}"
            )
            return response.text.strip()
        except Exception as e:
            err_str = str(e)
            if '429' in err_str:
                wait = 45 * (attempt + 1)
                logger.warning(f"Gemini rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"Gemini error (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(5)
    return None


def parse_ai_response(response_text, batch_size):
    """Parse JSON array from AI response. Handles markdown fences and partial JSON."""
    if not response_text:
        return None

    # Strip markdown fences
    text = response_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the text
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Try to find individual JSON objects
    objects = []
    for m in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
        try:
            obj = json.loads(m.group())
            if 'correct_answer' in obj:
                objects.append(obj)
        except json.JSONDecodeError:
            continue

    return objects if objects else None


def is_enriched(q):
    """Check if a question is already fully enriched."""
    f = q['fields']
    return (
        f.get('correct_answer', '').strip() in ('A', 'B', 'C', 'D')
        and len(f.get('explanation', '').strip()) > 10
        and len(f.get('concept_explanation', '').strip()) > 5
    )


def apply_enrichment(question, enrichment):
    """Apply AI enrichment data to a question fixture entry."""
    f = question['fields']

    answer = enrichment.get('correct_answer', '').strip().upper()
    if answer in ('A', 'B', 'C', 'D'):
        f['correct_answer'] = answer

    for field in ['explanation', 'concept_explanation', 'mnemonic', 'book_name',
                  'chapter', 'learning_technique', 'shortcut_tip']:
        val = enrichment.get(field, '').strip()
        if val:
            f[field] = val

    if enrichment.get('difficulty', '').strip().lower() in ('easy', 'medium', 'hard'):
        f['difficulty'] = enrichment['difficulty'].strip().lower()

    for list_field in ['concept_tags', 'concept_keywords']:
        val = enrichment.get(list_field, [])
        if isinstance(val, list) and len(val) > 0:
            f[list_field] = [str(v).strip() for v in val if str(v).strip()]

    # Build ai_explanation as a combined rich text
    parts = []
    if f.get('explanation'):
        parts.append(f"**Answer: {f.get('correct_answer', '?')}**\n{f['explanation']}")
    if f.get('concept_explanation'):
        parts.append(f"**Concept:** {f['concept_explanation']}")
    if f.get('mnemonic'):
        parts.append(f"**Mnemonic:** {f['mnemonic']}")
    if f.get('shortcut_tip'):
        parts.append(f"**Exam Tip:** {f['shortcut_tip']}")
    if parts:
        f['ai_explanation'] = "\n\n".join(parts)


def load_progress():
    """Load set of already processed PKs."""
    if PROGRESS_FILE.exists():
        try:
            return set(json.loads(PROGRESS_FILE.read_text(encoding='utf-8')))
        except Exception:
            return set()
    return set()


def save_progress(processed_pks):
    """Save processed PKs for resume."""
    PROGRESS_FILE.write_text(json.dumps(sorted(processed_pks)), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Batch enrich CrackCMS questions')
    parser.add_argument('--start', type=int, default=0, help='Start from question index')
    parser.add_argument('--limit', type=int, default=0, help='Max questions to process (0=all)')
    parser.add_argument('--batch', type=int, default=5, help='Questions per API call')
    parser.add_argument('--provider', type=str, default='groq', choices=['groq', 'gemini'], help='AI provider')
    parser.add_argument('--force', action='store_true', help='Re-enrich already enriched questions')
    args = parser.parse_args()

    if not GROQ_API_KEY and args.provider == 'groq':
        logger.error("GROQ_API_KEY not set in .env")
        sys.exit(1)

    # Load fixture
    logger.info(f"Loading {FIXTURE_FILE}...")
    data = json.load(open(FIXTURE_FILE, 'r', encoding='utf-8'))
    questions = [x for x in data if x.get('model') == 'questions.question']
    logger.info(f"Found {len(questions)} questions total")

    # Load progress
    processed_pks = load_progress()
    logger.info(f"Already processed: {len(processed_pks)} questions")

    # Filter questions that need enrichment
    to_process = []
    for q in questions:
        pk = q['pk']
        if pk in processed_pks and not args.force:
            continue
        if not args.force and is_enriched(q):
            processed_pks.add(pk)
            continue
        to_process.append(q)

    # Apply start/limit
    to_process = to_process[args.start:]
    if args.limit > 0:
        to_process = to_process[:args.limit]

    logger.info(f"Questions to enrich: {len(to_process)}")
    if not to_process:
        logger.info("Nothing to do!")
        return

    batch_size = args.batch
    total_batches = (len(to_process) + batch_size - 1) // batch_size
    enriched_count = 0
    failed_count = 0

    call_fn = call_groq if args.provider == 'groq' else call_gemini

    for batch_num in range(total_batches):
        batch_start = batch_num * batch_size
        batch = to_process[batch_start:batch_start + batch_size]
        pks = [q['pk'] for q in batch]

        logger.info(f"Batch {batch_num+1}/{total_batches} — PKs: {pks}")

        # Build prompt
        prompt = build_question_prompt(batch)

        # Call AI
        raw_response = call_fn(prompt)
        if not raw_response:
            logger.error(f"  No response for batch {batch_num+1}. Trying fallback...")
            # Try the other provider
            fallback_fn = call_gemini if args.provider == 'groq' else call_groq
            raw_response = fallback_fn(prompt)

        if not raw_response:
            logger.error(f"  Both providers failed for batch {batch_num+1}. Skipping.")
            failed_count += len(batch)
            continue

        # Parse response
        enrichments = parse_ai_response(raw_response, len(batch))
        if not enrichments:
            logger.error(f"  Failed to parse response for batch {batch_num+1}")
            logger.debug(f"  Raw: {raw_response[:300]}")
            failed_count += len(batch)
            continue

        # Apply enrichments
        for i, q in enumerate(batch):
            if i < len(enrichments):
                apply_enrichment(q, enrichments[i])
                processed_pks.add(q['pk'])
                enriched_count += 1
            else:
                logger.warning(f"  No enrichment for PK={q['pk']} (index {i})")
                failed_count += 1

        # Save progress every batch
        save_progress(processed_pks)

        # Save fixture every 10 batches
        if (batch_num + 1) % 10 == 0 or batch_num == total_batches - 1:
            logger.info(f"  Saving fixture... ({enriched_count} enriched so far)")
            with open(FIXTURE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        # Rate limiting
        if batch_num < total_batches - 1:
            time.sleep(DELAY_BETWEEN_BATCHES)

        # Progress
        pct = (batch_num + 1) / total_batches * 100
        logger.info(f"  Progress: {pct:.1f}% | Enriched: {enriched_count} | Failed: {failed_count}")

    # Final save
    logger.info("Saving final fixture file...")
    with open(FIXTURE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    save_progress(processed_pks)

    logger.info(f"\n{'='*60}")
    logger.info(f"DONE! Enriched: {enriched_count} | Failed: {failed_count}")
    logger.info(f"Total processed: {len(processed_pks)}")
    logger.info(f"Run 'python manage.py loaddata questions_fixture.json' to load into DB")


if __name__ == '__main__':
    main()
