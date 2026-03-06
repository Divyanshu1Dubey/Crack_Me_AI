"""Import questions from sample_questions.txt and misc remnants."""
import os, sys, re, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'crack_cms.settings'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Subject, Question

def parse_sample_questions(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple parser for sample_questions.txt
    # Pattern: \d+\.\nText\n(a) ... (b) ... (c) ... (d) ...
    q_blocks = re.split(r'(\d+)\.\n', content)
    
    parsed = []
    for i in range(1, len(q_blocks), 2):
        q_num = q_blocks[i]
        q_body = q_blocks[i+1].strip()
        
        # Options
        opt_a = re.search(r'\(a\)\s*(.*?)\n', q_body)
        opt_b = re.search(r'\(b\)\s*(.*?)\n', q_body)
        opt_c = re.search(r'\(c\)\s*(.*?)\n', q_body)
        opt_d = re.search(r'\(d\)\s*(.*?)\n', q_body)
        
        if not opt_a or not opt_b: continue
        
        # Text
        q_text = q_body[:opt_a.start()].strip()
        
        parsed.append({
            "text": q_text,
            "option_a": opt_a.group(1).strip() if opt_a else "",
            "option_b": opt_b.group(1).strip() if opt_b else "",
            "option_c": opt_c.group(1).strip() if opt_c else "",
            "option_d": opt_d.group(1).strip() if opt_d else "",
            "year": 2018, # From header
            "source": "SAMPLE_QUESTIONS_TXT"
        })
    return parsed

def main():
    q_file = 'sample_questions.txt'
    print(f"Parsing {q_file}...")
    questions = parse_sample_questions(q_file)
    print(f"Found {len(questions)} questions.")
    
    subj = Subject.objects.filter(code='MED').first() or Subject.objects.first()
    
    saved = 0
    for q in questions:
        snippet = q["text"][:50]
        if Question.objects.filter(question_text__icontains=snippet).exists():
            continue
            
        Question.objects.create(
            question_text=q["text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            subject=subj,
            year=q["year"],
            source=q["source"],
            difficulty="medium"
        )
        saved += 1
    
    print(f"Saved {saved} questions.")
    print(f"Total in DB: {Question.objects.count()}")

if __name__ == "__main__":
    main()
