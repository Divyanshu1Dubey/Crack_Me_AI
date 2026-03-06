"""Import questions from the markdown database file."""
import os, sys, re, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Subject, Topic, Question

# CMS subject mapping
SUBJECT_MAP = {
    "GENERAL MEDICINE": "MED",
    "PEDIATRICS": "PED",
    "SURGERY": "SUR",
    "OBSTETRICS & GYNAECOLOGY": "OBG",
    "PREVENTIVE & SOCIAL MEDICINE": "PSM",
}

def parse_md_db(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by Subject headers
    subject_sections = re.split(r'## (PAPER \d - .*?)\n', content)
    
    parsed_questions = []
    
    # subject_sections[0] is intro
    for i in range(1, len(subject_sections), 2):
        section_title = subject_sections[i]
        section_body = subject_sections[i+1]
        
        # Determine subject code
        subject_code = "MED"
        for key, code in SUBJECT_MAP.items():
            if key in section_title:
                subject_code = code
                break
        
        # Split by questions: **QX [YEAR Paper Z]**
        q_blocks = re.split(r'\*\*Q(\d+) \[(.*?)\]\*\*', section_body)
        
        # q_blocks[0] is garbage before first question
        for j in range(1, len(q_blocks), 3):
            q_num = q_blocks[j]
            q_meta = q_blocks[j+1] # e.g. "2024 Paper 1"
            q_body = q_blocks[j+2].strip()
            
            # Extract Year
            year_match = re.search(r'\d{4}', q_meta)
            year = int(year_match.group(0)) if year_match else 2024
            
            # Extract Text and Options
            # Text is everything before first "- A)"
            text_match = re.search(r'^(.*?)\n- A\)', q_body, re.DOTALL)
            if not text_match: continue
            q_text = text_match.group(1).strip()
            
            # Options
            opt_a = re.search(r'- A\)\s*(.*?)\n', q_body)
            opt_b = re.search(r'- B\)\s*(.*?)\n', q_body)
            opt_c = re.search(r'- C\)\s*(.*?)\n', q_body)
            opt_d = re.search(r'- D\)\s*(.*?)\n', q_body)
            
            # Answer and Explanation
            ans_match = re.search(r'\*\*Answer:\s*([ABCD])\*\*\s*(.*)', q_body)
            correct_ans = ans_match.group(1) if ans_match else ""
            explanation = ans_match.group(2).strip() if ans_match else ""
            
            # Mnemonic
            mnemonic_match = re.search(r'Memory Trick\s*(.*)', q_body, re.IGNORECASE)
            mnemonic = mnemonic_match.group(1).strip() if mnemonic_match else ""
            
            parsed_questions.append({
                "text": q_text,
                "option_a": opt_a.group(1).strip() if opt_a else "",
                "option_b": opt_b.group(1).strip() if opt_b else "",
                "option_c": opt_c.group(1).strip() if opt_c else "",
                "option_d": opt_d.group(1).strip() if opt_d else "",
                "correct_answer": correct_ans,
                "explanation": explanation,
                "subject_code": subject_code,
                "year": year,
                "mnemonic": mnemonic
            })
            
    return parsed_questions

def main():
    md_path = os.path.join('Medura_Train', 'PYQ', 'cms_pyq_database_2018_2024.md')
    print(f"Parsing {md_path}...")
    
    questions = parse_md_db(md_path)
    print(f"Found {len(questions)} questions in markdown.")
    
    saved = 0
    skipped = 0
    
    for q in questions:
        # Deduplicate
        snippet = q["text"][:50]
        if Question.objects.filter(question_text__icontains=snippet, year=q["year"]).exists():
            skipped += 1
            continue
            
        subj = Subject.objects.filter(code=q["subject_code"]).first()
        if not subj: subj = Subject.objects.first()
        
        Question.objects.create(
            question_text=q["text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            correct_answer=q["correct_answer"],
            explanation=q["explanation"],
            mnemonic=q["mnemonic"],
            subject=subj,
            year=q["year"],
            difficulty="medium",
            source="MD_DATABASE_2018_2024"
        )
        saved += 1
        
    print(f"Import complete: {saved} saved, {skipped} skipped.")
    print(f"Total questions in DB: {Question.objects.count()}")

if __name__ == "__main__":
    main()
