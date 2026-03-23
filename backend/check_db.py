import sqlite3

db_path = r'c:\Users\DIVYANSHU\Desktop\crack_cms\backend\db.sqlite3'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, question_text, option_a FROM questions_question WHERE year=? LIMIT 20", (2025,))
    rows = cursor.fetchall()
    print(f"Total 2025 questions found (sample 20): {len(rows)}")
    for r in rows:
        print(r)
        
    conn.close()
except Exception as e:
    print("Error:", e)
