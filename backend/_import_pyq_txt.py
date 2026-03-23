"""Import all PYQ .txt files into the questions database."""
import os, sys, re, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Subject, Topic, Question

# CMS subject mapping
SUBJECT_MAP = {
    "General Medicine": "MED",
    "Medicine": "MED",
    "Pediatrics": "PED",
    "Paediatrics": "PED",
    "Surgery": "SUR",
    "Obstetrics & Gynaecology": "OBG",
    "Obstetrics and Gynaecology": "OBG",
    "Gynaecology": "OBG",
    "Preventive & Social Medicine": "PSM",
    "Preventive and Social Medicine": "PSM",
    "PSM": "PSM",
    "Community Medicine": "PSM",
}

# Ensure all subjects exist
subjects_data = [
    ("General Medicine", "MED", "#06b6d4"),
    ("Pediatrics", "PED", "#8b5cf6"),
    ("Surgery", "SUR", "#10b981"),
    ("Obstetrics & Gynaecology", "OBG", "#ec4899"),
    ("Preventive & Social Medicine", "PSM", "#f59e0b"),
]
for name, code, color in subjects_data:
    Subject.objects.get_or_create(code=code, defaults={"name": name, "color": color})

# Improved pattern: Match questions that have 4 options (a), (b), (c), (d)
# This prevents matching numbered statements (1., 2., 3., 4.) within questions
QUESTION_PATTERN = re.compile(
    r'(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,3})[.)]\s*(.+?Options:\s*\([a-dA-D]\).+?\([a-dA-D]\).+?\([a-dA-D]\).+?\([a-dA-D]\)[^()]*?)(?=\n\s*(?:Q\.?\s*)?\d{1,3}[.)]\s[A-Z]|\nSection:|\n_{3,}|\Z)',
    re.DOTALL | re.IGNORECASE
)
# Alternative simpler pattern for questions without "Options:" prefix
QUESTION_PATTERN_SIMPLE = re.compile(
    r'(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,3})[.)]\s*([^:]+:\s*\([a-dA-D]\).+?\([a-dA-D]\).+?\([a-dA-D]\).+?\([a-dA-D]\)[^()]*?)(?=\n\s*(?:Q\.?\s*)?\d{1,3}[.)]\s[A-Z]|\nSection:|\n_{3,}|\Z)',
    re.DOTALL | re.IGNORECASE
)
OPTION_PATTERN = re.compile(
    r'\(\s*([a-dA-D])\s*\)\s*(.+?)(?=\(\s*[a-dA-D]\s*\)|\Z)',
    re.DOTALL
)

# Section headers to detect subject
SECTION_PATTERN = re.compile(
    r'Section:\s*(.*?)(?:\n|$)', re.IGNORECASE
)

def detect_subject_from_text(text, position):
    """Find the most recent Section: header before this position."""
    sections = list(SECTION_PATTERN.finditer(text))
    current_subject = "General Medicine"
    for s in sections:
        if s.start() <= position:
            current_subject = s.group(1).strip()
        else:
            break
    # Map to code
    for key, code in SUBJECT_MAP.items():
        if key.lower() in current_subject.lower():
            return code
    return "MED"

def parse_questions(text, year, paper):
    """Parse questions from text content.

    Improved parsing that handles statement-based questions like:
    '38. Which of the following are correct about X?
    1. Statement one.
    2. Statement two.
    3. Statement three.
    4. Statement four. Options: (a) 1,2,3; (b) 2,3,4...'
    """
    questions = []
    seen_numbers = set()

    # Try both patterns - with and without "Options:" prefix
    all_matches = []
    for match in QUESTION_PATTERN.finditer(text):
        all_matches.append(match)
    for match in QUESTION_PATTERN_SIMPLE.finditer(text):
        # Avoid duplicates
        if not any(m.start() == match.start() for m in all_matches):
            all_matches.append(match)

    # Sort by position in text
    all_matches.sort(key=lambda m: m.start())

    for match in all_matches:
        q_num = int(match.group(1))
        q_body = match.group(2).strip()

        # Skip if we've already seen this question number (duplicate match)
        if q_num in seen_numbers:
            continue
        seen_numbers.add(q_num)

        # Extract options
        options = {}
        opt_matches = list(OPTION_PATTERN.finditer(q_body))
        if len(opt_matches) >= 4:
            for om in opt_matches[:4]:
                letter = om.group(1).upper()
                opt_text = om.group(2).strip().rstrip(';,.')
                options[letter] = opt_text
        
        if not options or len(options) < 4:
            continue
        
        # Get question text (before first option)
        first_opt = opt_matches[0] if opt_matches else None
        if first_opt:
            q_text = q_body[:first_opt.start()].strip()
        else:
            q_text = q_body.strip()
        
        # Clean up question text
        q_text = re.sub(r'\s+', ' ', q_text).strip()
        q_text = re.sub(r'Options:\s*$', '', q_text).strip()
        q_text = re.sub(r'Select the correct answer.*$', '', q_text, flags=re.IGNORECASE).strip()
        
        if len(q_text) < 10:
            continue
        
        # Detect subject from section headers
        subject_code = detect_subject_from_text(text, match.start())
        
        questions.append({
            "number": q_num,
            "text": q_text,
            "options": options,
            "subject_code": subject_code,
            "year": year,
            "paper": paper,
        })
    
    return questions

def save_questions(questions, source_file):
    """Save questions to database with deduplication."""
    saved = 0
    skipped = 0
    
    for q in questions:
        subject = Subject.objects.filter(code=q["subject_code"]).first()
        if not subject:
            subject = Subject.objects.first()
        
        text_snippet = q["text"][:50]
        
        # Check for duplicate
        if Question.objects.filter(year=q["year"], question_text__icontains=text_snippet).exists():
            skipped += 1
            continue
        
        try:
            Question.objects.create(
                question_text=q["text"],
                option_a=q["options"].get("A", ""),
                option_b=q["options"].get("B", ""),
                option_c=q["options"].get("C", ""),
                option_d=q["options"].get("D", ""),
                correct_answer="",  # Will need AI or manual entry
                subject=subject,
                year=q["year"],
                paper=q["paper"],
                difficulty="medium",
                source=f"PYQ_TXT_{source_file}",
            )
            saved += 1
        except Exception as e:
            print(f'  Error saving Q{q["number"]}: {e}')
    
    return saved, skipped


# Main
pyq_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Medura_Train', 'PYQ')
txt_files = sorted([f for f in os.listdir(pyq_dir) if f.endswith('.txt') and re.match(r'\d{4}paper\d\.txt', f)])

print(f'Found {len(txt_files)} PYQ text files')
print(f'Existing questions in DB: {Question.objects.count()}\n')

grand_total_saved = 0
grand_total_skipped = 0

for f in txt_files:
    filepath = os.path.join(pyq_dir, f)
    m = re.match(r'(\d{4})paper(\d)', f)
    year = int(m.group(1))
    paper = int(m.group(2))
    
    with open(filepath, 'r', encoding='utf-8') as fp:
        text = fp.read()
    
    questions = parse_questions(text, year, paper)
    saved, skipped = save_questions(questions, f)
    grand_total_saved += saved
    grand_total_skipped += skipped
    
    print(f'{f}: parsed {len(questions)} questions, saved {saved}, skipped {skipped} duplicates')

print(f'\n=== IMPORT COMPLETE ===')
print(f'Total saved: {grand_total_saved}')
print(f'Total skipped (duplicates): {grand_total_skipped}')
print(f'Total questions in DB now: {Question.objects.count()}')
