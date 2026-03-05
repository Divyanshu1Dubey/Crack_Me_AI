"""
PYQ Extractor: Uses AI (Gemini/Groq) to extract structured MCQs from PYQ PDFs.
Handles the full pipeline: PDF → raw text → AI parsing → structured questions.
"""
import json
import logging
import re
from typing import Optional

from django.conf import settings

from .document_processor import DocumentProcessor, PYQPDFParser

logger = logging.getLogger(__name__)

# CMS-specific system prompt for PYQ extraction
PYQ_EXTRACTION_PROMPT = """You are a UPSC CMS exam expert. Extract ALL multiple-choice questions from the given text.

For EACH question, return a JSON object with:
- "number": question number (integer)
- "question_text": the full question stem
- "option_a": option A text
- "option_b": option B text
- "option_c": option C text
- "option_d": option D text
- "correct_answer": "A", "B", "C", or "D" (your best medical knowledge)
- "subject": one of "General Medicine", "Pediatrics", "Surgery", "Obstetrics & Gynaecology", "Preventive & Social Medicine"
- "topic": specific medical topic (e.g., "Cardiology", "Neonatology", "Orthopedics")
- "difficulty": "easy", "medium", or "hard"
- "explanation": detailed medical explanation of why the answer is correct (2-4 sentences)
- "mnemonic": a memory trick or acronym to remember this concept (1-2 sentences, creative)
- "concept_tags": list of 2-4 key medical concepts tested
- "book_reference": which standard textbook covers this (Harrison/Ghai/Nelson/Park)
- "learning_technique": brief tip on how to approach this type of question

Return a JSON array of all questions. ONLY return valid JSON, no markdown.
If you cannot determine the correct answer with high confidence, use your best medical judgment.
"""

SIMILAR_QUESTION_PROMPT = """Given this UPSC CMS question, identify which medical concepts it tests.
Return a JSON object with:
- "core_concepts": list of 3-5 core medical concepts
- "keywords": list of 5-10 searchable medical keywords
- "related_topics": list of 2-3 related topics that often appear together

Question: {question_text}

Return ONLY valid JSON."""


class PYQExtractor:
    """Extract and enrich PYQ questions using AI."""

    def __init__(self):
        self.processor = DocumentProcessor()
        self.parser = PYQPDFParser()
        self._init_ai()

    def _init_ai(self):
        """Initialize AI clients."""
        self.gemini_client = None
        self.groq_client = None

        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        groq_key = getattr(settings, 'GROQ_API_KEY', '')

        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self.gemini_client = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("Gemini client initialized for PYQ extraction")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

        if groq_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=groq_key)
                logger.info("Groq client initialized for PYQ extraction")
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

    def extract_from_pdf(self, pdf_path: str) -> list[dict]:
        """
        Full pipeline: PDF → parsed text → AI extraction → structured questions.
        """
        logger.info(f"Starting PYQ extraction from: {pdf_path}")

        # Step 1: Parse PDF
        parsed = self.parser.parse_pyq_pdf(pdf_path)
        if not parsed:
            logger.error(f"Could not parse PDF: {pdf_path}")
            return []

        year = parsed["year"]
        paper = parsed["paper"]
        full_text = parsed["full_text"]

        logger.info(f"PDF parsed: {parsed['page_count']} pages, Year={year}, Paper={paper}")

        # Step 2: Try regex extraction first
        regex_questions = self.parser.detect_questions_with_regex(full_text)
        if len(regex_questions) >= 50:
            logger.info(f"Regex extracted {len(regex_questions)} questions — using AI to enrich")
            return self._enrich_with_ai(regex_questions, year, paper)

        # Step 3: Use AI for full extraction (split into chunks for token limits)
        logger.info("Using AI for full question extraction")
        pages = parsed["pages"]
        all_questions = []

        # Process in batches of ~5 pages (to stay within token limits)
        batch_size = 5
        for i in range(0, len(pages), batch_size):
            batch_pages = pages[i:i + batch_size]
            batch_text = "\n\n".join(p["text"] for p in batch_pages)

            questions = self._ai_extract(batch_text, year, paper)
            if questions:
                all_questions.extend(questions)
                logger.info(f"  Batch {i // batch_size + 1}: extracted {len(questions)} questions")

        # Deduplicate by question number
        seen = set()
        unique_questions = []
        for q in all_questions:
            q_num = q.get("number", 0)
            if q_num not in seen:
                seen.add(q_num)
                unique_questions.append(q)

        logger.info(f"Total unique questions extracted: {len(unique_questions)}")
        return unique_questions

    def _ai_extract(self, text: str, year: int, paper: int) -> list[dict]:
        """Use AI to extract questions from text."""
        prompt = f"{PYQ_EXTRACTION_PROMPT}\n\n--- TEXT FROM {year} PAPER {paper} ---\n{text}"

        response_text = self._call_ai(prompt)
        if not response_text:
            return []

        return self._parse_ai_response(response_text, year, paper)

    def _enrich_with_ai(self, questions: list[dict], year: int, paper: int) -> list[dict]:
        """Enrich regex-extracted questions with AI analysis."""
        enriched = []
        batch = []

        for q in questions:
            q_text = f"Q{q['number']}: {q['text']}"
            if q.get("options"):
                for k, v in q["options"].items():
                    q_text += f"\n{k}) {v}"
            batch.append(q_text)

            # Process in batches of 10
            if len(batch) >= 10:
                result = self._ai_extract("\n\n".join(batch), year, paper)
                if result:
                    enriched.extend(result)
                batch = []

        # Last batch
        if batch:
            result = self._ai_extract("\n\n".join(batch), year, paper)
            if result:
                enriched.extend(result)

        return enriched if enriched else self._basic_enrich(questions, year, paper)

    def _basic_enrich(self, questions: list[dict], year: int, paper: int) -> list[dict]:
        """Basic enrichment without AI (fallback)."""
        enriched = []
        for q in questions:
            enriched.append({
                "number": q.get("number", 0),
                "question_text": q.get("text", ""),
                "option_a": q.get("options", {}).get("A", ""),
                "option_b": q.get("options", {}).get("B", ""),
                "option_c": q.get("options", {}).get("C", ""),
                "option_d": q.get("options", {}).get("D", ""),
                "correct_answer": "",
                "subject": self._guess_subject(paper),
                "topic": "",
                "difficulty": "medium",
                "explanation": "",
                "mnemonic": "",
                "concept_tags": [],
                "year": year,
                "paper": paper,
            })
        return enriched

    def _guess_subject(self, paper: int) -> str:
        """Guess primary subject from paper number."""
        if paper == 1:
            return "General Medicine"
        elif paper == 2:
            return "Surgery"
        return "General Medicine"

    def _call_ai(self, prompt: str) -> Optional[str]:
        """Call AI with fallback chain: Gemini → Groq."""
        # Try Gemini first
        if self.gemini_client:
            try:
                logger.info("Calling Gemini for extraction...")
                response = self.gemini_client.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 8192,
                    },
                    request_options={"timeout": 15.0}
                )
                return response.text
            except Exception as e:
                logger.warning(f"Gemini extraction failed or timed out: {e}")

        # Fallback to Groq
        if self.groq_client:
            try:
                logger.info("Calling Groq for extraction (fallback)...")
                response = self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are a UPSC CMS medical exam expert."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=8192,
                    timeout=15.0
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Groq extraction failed or timed out: {e}")

        logger.error("No AI client available for extraction")
        return None

    def _parse_ai_response(self, text: str, year: int, paper: int) -> list[dict]:
        """Parse AI JSON response into question dicts."""
        try:
            # Clean up response — remove markdown code fences
            cleaned = text.strip()
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

            data = json.loads(cleaned)
            if isinstance(data, dict):
                data = [data]

            # Add year/paper info
            for q in data:
                q["year"] = year
                q["paper"] = paper

            return data
        except json.JSONDecodeError:
            # Try to extract JSON array from text
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    data = json.loads(match.group())
                    for q in data:
                        q["year"] = year
                        q["paper"] = paper
                    return data
                except json.JSONDecodeError:
                    pass
            logger.error(f"Failed to parse AI response as JSON")
            return []

    def get_concept_keywords(self, question_text: str) -> dict:
        """Get concept keywords for similarity matching."""
        prompt = SIMILAR_QUESTION_PROMPT.format(question_text=question_text)
        response = self._call_ai(prompt)
        if response:
            try:
                cleaned = response.strip()
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        return {"core_concepts": [], "keywords": [], "related_topics": []}
