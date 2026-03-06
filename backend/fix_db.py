import sqlite3
import re

db_path = r'c:\Users\DIVYANSHU\Desktop\crack_cms\backend\db.sqlite3'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Fix "w, hite"
    cursor.execute("SELECT id, question_text FROM questions_question")
    rows = cursor.fetchall()
    count_hite = 0
    for ids, q in rows:
        if q:
            # Replace w, hite or w,hite to white
            new_q = re.sub(r'w\s*,\s*hite', 'white', q, flags=re.IGNORECASE)
            # Replace '8*' -> '8.'
            new_q = re.sub(r'(?<=\s)8\*(?=\s|$)', '8.', new_q)
            if new_q != q:
                cursor.execute("UPDATE questions_question SET question_text = ? WHERE id = ?", (new_q, ids))
                count_hite += 1
    
    # 2. Fix '*' in options
    cursor.execute("SELECT id, option_a, option_b, option_c, option_d FROM questions_question")
    rows2 = cursor.fetchall()
    count_opt = 0
    for r in rows2:
        ids = r[0]
        a, b, c, d = r[1], r[2], r[3], r[4]
        
        def clean_opt(opt):
            if not opt: return opt
            # remove starting '* (a)', '(a)', '* '
            opt = re.sub(r'^\*\s*\([a-d]\)\s*', '', opt, flags=re.IGNORECASE)
            opt = re.sub(r'^\*\s*', '', opt)
            opt = opt.strip()
            return opt

        new_a, new_b, new_c, new_d = clean_opt(a), clean_opt(b), clean_opt(c), clean_opt(d)
        
        if new_a != a or new_b != b or new_c != c or new_d != d:
            cursor.execute("UPDATE questions_question SET option_a=?, option_b=?, option_c=?, option_d=? WHERE id = ?", (new_a, new_b, new_c, new_d, ids))
            count_opt += 1
            
    conn.commit()
    conn.close()
    print(f"Fixed 'w, hite' or '8*' in {count_hite} questions.")
    print(f"Cleaned options (removed asterisks) in {count_opt} questions.")
except Exception as e:
    print("Error:", e)
