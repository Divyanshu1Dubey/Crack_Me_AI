"""
Enhanced AI Service Layer for UPSC CMS Platform.
Orchestrates Gemini + Groq with RAG-backed textbook grounding.
"""
import json
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Gemini models in order of preference (each has separate quota on free tier)
GEMINI_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
]

# CMS-specific system prompt
CMS_SYSTEM_PROMPT = """You are an expert UPSC CMS (Combined Medical Services) exam tutor and medical educator.

Your knowledge covers the complete CMS syllabus:
- Paper 1: General Medicine (Cardiology, Nephrology, Endocrinology, Neurology, etc.) + Pediatrics
- Paper 2: Surgery + Obstetrics & Gynaecology + Preventive & Social Medicine (PSM)

Standard textbooks you reference:
- Harrison's Principles of Internal Medicine (Medicine)
- Ghai Essential Pediatrics (Pediatrics)
- Nelson Textbook of Pediatrics (Pediatrics)
- Park's Textbook of Preventive & Social Medicine (PSM)
- Bailey & Love (Surgery)
- Dutta's Textbook of Obstetrics & Gynaecology (OBG)

When answering:
1. Be precise, exam-focused, and cite specific textbook references using exactly: **Textbook Reference: [Book Name], [Chapter]**
2. Important concepts MUST be tagged with exactly **[High Yield]**
3. If related to past questions, tag with **[PYQ YYYY]** (e.g., [PYQ 2021])
4. Provide mnemonics and memory tricks when helpful
5. Explain concepts from basics for deep understanding
6. Give clinical correlations when relevant
"""


class AIService:
    """Enhanced AI service with RAG pipeline integration."""

    def __init__(self):
        self.gemini_client = None
        self.groq = None
        self.deepseek = None
        self._rag = None
        self._init_clients()

    def _init_clients(self):
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        groq_key = getattr(settings, 'GROQ_API_KEY', '')
        deepseek_key = getattr(settings, 'DEEPSEEK_API_KEY', '')

        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self.gemini_client = genai
                logger.info("Gemini AI initialized (google.generativeai SDK)")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

        if groq_key:
            try:
                from groq import Groq
                self.groq = Groq(api_key=groq_key)
                logger.info("Groq AI initialized")
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

        if deepseek_key:
            try:
                from openai import OpenAI
                self.deepseek = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
                logger.info("DeepSeek AI initialized")
            except Exception as e:
                logger.warning(f"DeepSeek init failed: {e}")

    @property
    def rag(self):
        """Lazy-load RAG pipeline."""
        if self._rag is None:
            try:
                from ai_engine.rag_pipeline import RAGPipeline
                self._rag = RAGPipeline()
            except Exception as e:
                logger.warning(f"RAG init failed: {e}")
        return self._rag

    def _call_ai(self, prompt: str, system: str = CMS_SYSTEM_PROMPT,
                 temperature: float = 0.3, max_tokens: int = 2048, is_complex: bool = False) -> str:
        """Call AI with routing: DeepSeek for complex, Groq for fast, Gemini as fallback."""
        
        # --- FAST / SIMPLE OPTION (Priority: Groq) ---
        if not is_complex and self.groq:
            try:
                logger.info("Calling Groq AI (Fast Option)...")
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                response = self.groq.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=20.0
                )
                logger.info("Groq responded successfully.")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Groq fast call failed: {e}")

        # --- COMPLEX / DEEP REASONING OPTION (Priority: DeepSeek) ---
        if is_complex and self.deepseek:
            try:
                logger.info("Calling DeepSeek AI (Complex Task)...")
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                response = self.deepseek.chat.completions.create(
                    model="deepseek-reasoner", # Best for deep, time-taking logical analysis
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60.0
                )
                logger.info("DeepSeek responded successfully.")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"DeepSeek call failed: {e}")

        # --- GENERAL FALLBACK ---
        if self.gemini_client:
            genai = self.gemini_client
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            for model_name in GEMINI_MODELS:
                try:
                    logger.info(f"Calling Gemini model: {model_name}...")
                    model = genai.GenerativeModel(model_name=model_name)
                    response = model.generate_content(
                        full_prompt,
                        generation_config={
                            "temperature": temperature,
                            "max_output_tokens": max_tokens,
                        }
                    )
                    if response and response.text:
                        logger.info(f"Gemini [{model_name}] responded successfully.")
                        return response.text
                except Exception as e:
                    error_str = str(e)
                    if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower():
                        logger.warning(f"Gemini [{model_name}] quota exhausted, trying next model...")
                        continue
                    logger.warning(f"Gemini [{model_name}] failed: {e}")
                    continue

        # If Groq was not the primary, try it as fallback
        if self.groq and is_complex:
            try:
                logger.info("Calling Groq AI (fallback)...")
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                response = self.groq.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=20.0
                )
                logger.info("Groq responded successfully.")
                return response.choices[0].message.content
            except Exception as e:
                import traceback
                print(f"Groq error details: {e}")
                logger.warning(f"Groq call failed: {e}")

        # If DeepSeek was not the primary, try it as fallback
        if self.deepseek and not is_complex:
            try:
                logger.info("Calling DeepSeek AI (fallback)...")
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                response = self.deepseek.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=30.0
                )
                logger.info("DeepSeek responded successfully.")
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"DeepSeek fallback failed: {e}")

        return "⚠️ All AI services are temporarily unavailable (quota exceeded or API key issues). Please try again in a few minutes."

    # ─── CORE AI ENDPOINTS ───────────────────────────────

    def ask_tutor(self, question: str, context: str = "") -> str:
        """RAG-enhanced AI tutor — answers grounded in textbook content."""
        # Try RAG first for textbook-grounded answers
        rag_context = ""
        citations = []
        if self.rag:
            try:
                results = self.rag.search(question, n_results=3)
                if results:
                    rag_context = "\n\nRELEVANT TEXTBOOK CONTENT:\n"
                    for r in results:
                        rag_context += f"\n[{r['book']} p.{r['page']}]: {r['text']}\n"
                        citations.append(f"{r['book']} p.{r['page']}")
            except Exception as e:
                logger.warning(f"RAG search failed: {e}")

        prompt = f"""Student's Question: {question}

{f'Additional Context: {context}' if context else ''}
{rag_context}

Provide a comprehensive, exam-focused answer. Include:
1. Direct answer with explanation
2. Key points for CMS exam revision (Tag must-know points with [High Yield])
3. Exact textbook reference formatted as: **Textbook Reference: [Book Name] p.[Page] OR [Chapter]**
4. Any helpful mnemonic
5. Mention if this is a repeat topic using [PYQ YYYY] if applicable"""

        answer = self._call_ai(prompt)

        if citations:
            answer += f"\n\n📚 **References**: {', '.join(citations)}"

        return answer

    def generate_mnemonic(self, topic: str, concept: str = "") -> str:
        """Generate exam-focused mnemonics with textbook grounding."""
        rag_context = ""
        if self.rag:
            try:
                results = self.rag.search(f"{topic} {concept}", n_results=2)
                if results:
                    rag_context = "\nTextbook context:\n" + results[0]["text"][:500]
            except Exception:
                pass

        prompt = f"""Create a memorable mnemonic for UPSC CMS exam preparation:
Topic: {topic}
{f'Specific concept: {concept}' if concept else ''}
{rag_context}

Provide a well-structured response using markdown formatting:

## Mnemonic for {topic}
Give a clear mnemonic name (e.g., "I GET SMASHED")

### What each letter stands for:
- **Letter** — Full form (brief explanation)

### Clinical Pearl
One powerful clinical correlation

### Alternative Memory Tricks
- Story association technique
- Categorization approach (group items logically)

### Textbook Reference
**Textbook Reference: [Book Name], [Chapter]**

Tag important points with **[High Yield]** and past question references with **[PYQ YYYY]**"""

        return self._call_ai(prompt)

    def explain_concept(self, concept: str, level: str = "basic") -> str:
        """Explain a medical concept from basics, grounded in textbooks."""
        rag_context = ""
        if self.rag:
            try:
                results = self.rag.search(concept, n_results=3)
                if results:
                    rag_context = "\nTextbook references:\n"
                    for r in results:
                        rag_context += f"[{r['book']} p.{r['page']}]: {r['text'][:300]}\n"
            except Exception:
                pass

        prompt = f"""Explain this medical concept for a UPSC CMS aspirant:
Concept: {concept}
Level: {level} (basic = from scratch, intermediate = assume MBBS knowledge, advanced = exam-specific)
{rag_context}

Structure your explanation as:
1. **What is it?** (Definition in simple words)
2. **Why is it important?** (Clinical significance)
3. **How does it work?** (Mechanism/Pathophysiology)
4. **CMS Exam Relevance** (How asked, traps. Tag with [High Yield] and [PYQ YYYY] if highly tested)
5. **Key Points to Remember** (Bullet points)
6. **Mnemonic** (If applicable)
7. **Textbook Reference: [Book Name, Chapter/Page]** (Must use this exact formatting)"""

        return self._call_ai(prompt, max_tokens=3000)

    def analyze_question(self, question_text: str, options: dict = None,
                         correct_answer: str = "") -> str:
        """Analyze a CMS question — identify concepts, predict topics."""
        prompt = f"""Analyze this UPSC CMS question:
Question: {question_text}
{f'Options: {json.dumps(options)}' if options else ''}
{f'Correct Answer: {correct_answer}' if correct_answer else ''}

Provide:
1. **Core Concept** being tested
2. **Subject & Topic** classification
3. **Why the correct answer is right** (detailed reasoning)
4. **Why other options are wrong** (elimination technique)
5. **Similar Concepts** that are often confused
6. **Textbook Reference** (exact book & chapter if possible)
7. **Exam Strategy** (How to approach this type of question)
8. **Mnemonic** for remembering this concept"""

        return self._call_ai(prompt, max_tokens=2500)

    # ─── RAG-SPECIFIC ENDPOINTS ──────────────────────────

    def rag_search(self, query: str, book_filter: str = None,
                   n_results: int = 5) -> dict:
        """Search textbooks using RAG."""
        if not self.rag:
            return {"results": [], "error": "RAG pipeline not initialized"}

        results = self.rag.search(query, n_results=n_results,
                                  book_filter=book_filter if book_filter else None)
        return {"results": results}

    def rag_answer(self, question: str) -> dict:
        """Get a RAG-grounded answer with citations."""
        if not self.rag:
            return {
                "answer": "RAG pipeline not initialized. Run: python manage.py index_textbooks",
                "citations": [],
            }
        return self.rag.rag_answer(question)

    def find_textbook_reference(self, question_text: str) -> list:
        """Find where a topic is discussed in standard textbooks."""
        if not self.rag:
            return []
        return self.rag.find_textbook_reference(question_text)

    # ─── STUDY PLANNER ───────────────────────────────────

    def generate_study_plan(self, weak_topics: list, days_remaining: int = 60,
                            user_analytics: dict = None) -> str:
        """Generate personalized CMS study plan."""
        analytics_str = ""
        if user_analytics:
            analytics_str = f"\nUser Performance Data: {json.dumps(user_analytics)}"

        prompt = f"""Create a personalized UPSC CMS study plan:

Weak Topics: {', '.join(weak_topics) if weak_topics else 'Not identified yet'}
Days Remaining: {days_remaining}
{analytics_str}

CMS Exam Structure:
- Paper 1: General Medicine (96 Qs) + Pediatrics (24 Qs) = 120 Qs, 250 marks
- Paper 2: Surgery (40 Qs) + OBG (40 Qs) + PSM (40 Qs) = 120 Qs, 250 marks
- Negative marking: -0.33 for wrong answers

Create a structured study plan with:
1. **Phase 1 (Foundation)**: Core subject revision schedule
2. **Phase 2 (Deep Dive)**: Weak area focused intensive study
3. **Phase 3 (Practice)**: PYQ solving, mock tests
4. **Phase 4 (Revision)**: Quick revision strategy
5. **Daily Schedule**: Recommended hours per subject
6. **High Yield Topics**: Must-study topics based on PYQ analysis
7. **Revision Strategy**: Spaced repetition schedule
8. **Tips**: Subject-specific preparation strategies"""

        return self._call_ai(prompt, max_tokens=3000)

    def generate_questions(self, subject: str, topic: str = "",
                           difficulty: str = "medium", count: int = 5) -> list:
        """Generate AI practice MCQs on a given subject/topic."""
        rag_context = ""
        if self.rag and topic:
            try:
                results = self.rag.search(f"{subject} {topic}", n_results=3)
                if results:
                    rag_context = "\nTextbook context for question generation:\n"
                    for r in results:
                        rag_context += f"[{r['book']}]: {r['text'][:400]}\n"
            except Exception:
                pass

        prompt = f"""Generate {count} original UPSC CMS-style MCQs.

Subject: {subject}
{f'Topic: {topic}' if topic else ''}
Difficulty: {difficulty}
{rag_context}

Each question MUST follow this exact JSON format. Return ONLY a valid JSON array:
[
  {{
    "question_text": "...",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_answer": "A",
    "explanation": "...",
    "difficulty": "{difficulty}",
    "subject": "{subject}",
    "topic": "{topic or 'General'}"
  }}
]

Rules:
- Questions must be exam-realistic, testing clinical reasoning
- Each option should be plausible
- Explanation must cite textbook reference
- Return ONLY the JSON array, no markdown fences"""

        raw = self._call_ai(prompt, max_tokens=4000, temperature=0.5)

        # Parse JSON from response
        try:
            import re
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            text = match.group(0) if match else raw
            questions = json.loads(text)
            if isinstance(questions, list):
                return questions[:count]
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse generated questions: {e}")

        return [{"error": "Failed to generate questions. Try again.", "raw": raw[:500]}]

    def predict_high_yield_topics(self) -> str:
        """Predict high-yield topics for next CMS exam based on PYQ trends."""
        prompt = """Based on UPSC CMS PYQ trends (2018-2024), predict the most likely topics for the next exam.

Analyze:
1. Topics that appear almost every year (guaranteed questions)
2. Topics with increasing frequency
3. Topics due for a repeat (asked 2-3 years ago but not recently)
4. New important topics (COVID, updated WHO guidelines, etc.)

For each subject (Medicine, Pediatrics, Surgery, OBG, PSM):
- List top 10 high-yield topics
- Assign priority (★★★ = must study, ★★ = important, ★ = good to know)
- Mention standard textbook chapter to study"""

        return self._call_ai(prompt, max_tokens=3000)

    # ─── POST-ANSWER DEEP EXPLANATION ────────────────────

    def explain_after_answer(self, question_text: str, options: dict = None,
                             correct_answer: str = "", selected_answer: str = "",
                             subject: str = "", topic: str = "") -> dict:
        """Generate a rich AI explanation after the user answers a question.
        Returns textbook location, mnemonic, around-concepts, and deep explanation."""
        rag_context = ""
        citations = []
        if self.rag:
            try:
                search_query = f"{subject} {topic} {question_text}" if subject else question_text
                results = self.rag.search(search_query, n_results=3)
                if results:
                    rag_context = "\n\nRELEVANT TEXTBOOK CONTENT:\n"
                    for r in results:
                        rag_context += f"\n[{r['book']} p.{r['page']}]: {r['text'][:400]}\n"
                        citations.append({"book": r.get('book', ''), "page": r.get('page', ''), "text": r.get('text', '')[:150]})
            except Exception as e:
                logger.warning(f"RAG search failed: {e}")

        is_correct = selected_answer == correct_answer
        options_str = ""
        if options:
            options_str = "\n".join([f"  {k}: {v}" for k, v in options.items()])

        prompt = f"""A UPSC CMS aspirant just answered a question. Provide a POWERFUL explanation that teaches them deeply.

Question: {question_text}
Options:
{options_str}
Correct Answer: {correct_answer}
Student Selected: {selected_answer} ({'CORRECT ✅' if is_correct else 'WRONG ❌'})
{f'Subject: {subject}' if subject else ''}
{f'Topic: {topic}' if topic else ''}
{rag_context}

You MUST respond in this EXACT JSON format (no markdown fences, just raw JSON):
{{
  "why_correct": "4-5 line detailed explanation of why {correct_answer} is the right answer. Include mechanism/pathophysiology. Explain clearly as if teaching a student from scratch. Be thorough and include clinical reasoning.",
  "why_wrong": {{ {', '.join([f'"{opt}": "2-3 lines: Why this is wrong, the key differentiator, and a quick trick to avoid picking this"' for opt in ['A','B','C','D'] if opt != correct_answer])} }},
  "textbook_reference": {{
    "book": "Name of standard textbook (Harrison/Ghai/Park/Bailey & Love/Dutta etc.)",
    "chapter": "Chapter name or number",
    "page": "Page number or range if known",
    "section": "Specific section within the chapter"
  }},
  "mnemonic": "A creative, catchy mnemonic to remember this concept FOREVER. Use a memorable acronym, story, or funny association. Explain each letter/word. Make it impossible to forget. ALWAYS provide one, never leave blank.",
  "core_concept": "The fundamental concept being tested — stated clearly in 1 line",
  "topic_deep_dive": "A comprehensive 6-8 line paragraph that acts as a MINI LECTURE NOTE. Cover: (1) What is this topic about? (2) Key classifications/stages/types (3) Important numbers/values to remember (4) How it connects to clinical practice (5) Common exam traps. Write as if you are a teacher giving a quick but thorough overview to a student who needs to understand the entire topic from this one explanation.",
  "key_differentiators": [
    "5-7 one-line comparisons that help differentiate commonly confused conditions/drugs/values in this topic. Format: 'X vs Y — key difference'. These should be HIGH YIELD comparisons."
  ],
  "category": "{subject or 'General'}",
  "sub_category": "{topic or 'General'}",
  "question_type": "One of: Factual Recall / Clinical Scenario / Calculation / Image-based / Conceptual / Pharmacology / Differential Diagnosis",
  "around_concepts": [
    "5-8 closely related concepts that are frequently tested alongside this topic in CMS exams"
  ],
  "high_yield_points": [
    "5-8 bullet points that are the MOST frequently tested facts from this topic in CMS. Each point should be a standalone fact a student can memorize."
  ],
  "clinical_pearl": "One powerful real-world clinical correlation that makes this concept click — something a doctor would know from practice",
  "exam_tip": "A strategic tip for approaching this type of question in the exam — how to eliminate options, time-saving tricks",
  "quick_revision": "3-4 line ultra-concise summary with the most important facts. A student should be able to read JUST THIS and recall the entire concept before the exam.",
  "pyq_frequency": "How often this topic appears in CMS PYQs (e.g., 'Asked every year since 2018', 'Asked 4 times in 2018-2024', etc.)",
  "similar_pyq": "Describe 1-2 similar questions from UPSC CMS PYQs with year and brief description (e.g., 'CMS 2022 Paper 1: Asked about the initial investigation for Cushing syndrome'). If none known, say 'Similar concepts tested in CMS 2020-2024'."
}}"""
        # Generate Deep Analysis via DeepSeek (complex flag)
        raw = self._call_ai(prompt, max_tokens=3000, temperature=0.3, is_complex=True)

        try:
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            text = match.group(0) if match else raw
            result = json.loads(text)
            result['citations'] = citations
            result['is_correct'] = is_correct
            # Ensure new fields have defaults
            result.setdefault('category', subject or '')
            result.setdefault('sub_category', topic or '')
            result.setdefault('question_type', '')
            result.setdefault('similar_pyq', '')
            result.setdefault('topic_deep_dive', '')
            result.setdefault('key_differentiators', [])
            result.setdefault('quick_revision', '')
            return result
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse explain_after_answer JSON: {e}")
            return {
                "why_correct": raw[:500] if raw else "AI explanation unavailable.",
                "why_wrong": {},
                "textbook_reference": {"book": "", "chapter": "", "page": "", "section": ""},
                "mnemonic": "",
                "core_concept": "",
                "category": subject or "",
                "sub_category": topic or "",
                "question_type": "",
                "around_concepts": [],
                "high_yield_points": [],
                "clinical_pearl": "",
                "exam_tip": "",
                "topic_deep_dive": "",
                "key_differentiators": [],
                "quick_revision": "",
                "pyq_frequency": "",
                "similar_pyq": "",
                "citations": citations,
                "is_correct": is_correct,
                "raw_response": raw[:800] if raw else "",
            }
