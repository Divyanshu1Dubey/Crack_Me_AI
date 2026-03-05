import os
import sys
import json
import re
import time
import logging

import fitz  # PyMuPDF
import google.generativeai as genai

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')

import django
django.setup()

from django.conf import settings
from questions.models import Subject, Topic, Question

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

SUBJECT_MAP = {
    "General Medicine": "MED",
    "Pediatrics": "PED",
    "Surgery": "SUR",
    "Obstetrics & Gynaecology": "OBG",
    "Preventive & Social Medicine": "PSM",
}

VISION_PROMPT = """You are a UPSC CMS expert. The attached image is a page from a UPSC CMS PYQ exam paper.
Extract ALL multiple-choice questions visible in this image accurately.

Return a JSON array where each object has exactly these keys:
- "number": question number (integer)
- "question_text": the exact question text
- "option_a": option A
- "option_b": option B
- "option_c": option C
- "option_d": option D
- "correct_answer": "A", "B", "C", or "D" (use your medical knowledge to determine this)
- "subject": "General Medicine", "Pediatrics", "Surgery", "Obstetrics & Gynaecology", or "Preventive & Social Medicine"
- "topic": specific medical topic
- "difficulty": "easy", "medium", or "hard"
- "explanation": concise medical explanation of the correct answer
- "concept_tags": list of 2-3 clinical concepts

ONLY return a valid JSON array. No markdown formatting, no text before or after the JSON."""

def setup_gemini():
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.error("GEMINI_API_KEY not set in Django settings")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash')

def extract_questions_from_page(model, page_pixmap):
    image_part = {
        "mime_type": "image/png",
        "data": page_pixmap.tobytes("png")
    }
    
    try:
        response = model.generate_content(
            [VISION_PROMPT, image_part],
            generation_config={"temperature": 0.1, "max_output_tokens": 8192},
            request_options={"timeout": 30.0}
        )
        text = response.text
        # Clean JSON
        cleaned = text.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        
        data = json.loads(cleaned)
        if isinstance(data, dict):
            data = [data]
            
        return data
    except Exception as e:
        logger.error(f"Vision API extraction failed: {e}")
        return []

def save_questions(questions, source_file, year, paper_num):
    saved = 0
    for q in questions:
        try:
            subject_name = q.get("subject", "General Medicine")
            subject_code = SUBJECT_MAP.get(subject_name, "MED")
            subject = Subject.objects.filter(code=subject_code).first()
            if not subject:
                subject = Subject.objects.first()

            topic_name = q.get("topic", "General")
            topic = None
            if topic_name and subject:
                topic, _ = Topic.objects.get_or_create(
                    name=topic_name[:100],
                    subject=subject,
                    defaults={"description": f"{topic_name} - {subject.name}"}
                )

            q_text = q.get("question_text", "").strip()

            if not q_text or len(q_text) < 10:
                continue

            if Question.objects.filter(year=year, question_text__icontains=q_text[:50]).exists():
                continue

            Question.objects.create(
                question_text=q_text,
                option_a=str(q.get("option_a", "")),
                option_b=str(q.get("option_b", "")),
                option_c=str(q.get("option_c", "")),
                option_d=str(q.get("option_d", "")),
                correct_answer=q.get("correct_answer", "A"),
                explanation=q.get("explanation", ""),
                subject=subject,
                topic=topic,
                year=year,
                paper=paper_num,
                difficulty=q.get("difficulty", "medium"),
                source=f"VISION_{source_file}",
            )
            saved += 1
        except Exception as e:
            logger.error(f"Failed to save Q{q.get('number', '?')}: {e}")
            
    return saved

def run():
    model = setup_gemini()
    if not model: return
    
    pyq_dir = os.path.join(backend_dir, "Medura_Train", "PYQ")
    pdf_files = [f for f in os.listdir(pyq_dir) if f.endswith(".pdf") and not f.startswith("Copy")]
    
    total_saved = 0
    for f in pdf_files:
        if "2024" not in f:
            continue
            
        pdf_path = os.path.join(pyq_dir, f)
        year = 2024
        paper_match = re.search(r'Paper\s*(\d)', f, re.IGNORECASE)
        paper_num = int(paper_match.group(1)) if paper_match else 1
        
        logger.info(f"Processing {f} via Gemini Vision...")
        doc = fitz.open(pdf_path)
        
        # Only process first 10 pages to avoid ratelimits during this demonstration
        pages_to_process = min(len(doc), 10) 
        for i in range(pages_to_process):
            logger.info(f"  -> Extracting Page {i+1}/{pages_to_process}...")
            page = doc[i]
            # 150 DPI is a good balance of crisp text and small payload size
            pix = page.get_pixmap(dpi=150)
            
            questions = extract_questions_from_page(model, pix)
            if questions:
                logger.info(f"     Found {len(questions)} questions on page {i+1}")
                saved = save_questions(questions, f, year, paper_num)
                total_saved += saved
            else:
                logger.warning(f"     No questions found on page {i+1}")
                
            time.sleep(4) # Rate limit protection
            
    logger.info(f"\n✅ Total {total_saved} new questions successfully populated directly via AI Vision!")

if __name__ == "__main__":
    run()
