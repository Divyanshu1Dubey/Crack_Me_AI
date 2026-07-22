"""Test pdfplumber on year-wise NEET PG papers."""
import pdfplumber

PDFS = [
    'NEET-PG-2022-Question-Paper-With-Solutions.pdf',
    'NEET-PG-Question-Paper-2018-PDF-With-Solutions.pdf',
    'NEET-PG-Question-Paper-2020-With-Solutions.pdf',
    'NEET-PG-2023-Question-Paper-With-Solutions-PDF-1.pdf',
    'neet-pg-2025-question-paper-pdf-aug-03-2025-1781083284.pdf',
]

for fname in PDFS:
    p = r'C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material' + '\\' + fname
    try:
        chars = 0
        pages = 0
        with pdfplumber.open(p) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages:
                t = page.extract_text() or ''
                chars += len(t)
        print(f'  {chars:7} chars, {pages:3} pages  {fname}')
    except Exception as e:
        print(f'  ERR {fname}: {e}')
