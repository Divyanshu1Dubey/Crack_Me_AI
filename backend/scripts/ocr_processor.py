import os
import argparse
import logging
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Input/Output paths
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
BOOKS_DIR = os.path.join(ROOT_DIR, 'Medura_Train', 'textbooks')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'Medura_Train', 'web_knowledge')

os.makedirs(OUTPUT_DIR, exist_ok=True)

def ocr_pdf_to_md(pdf_path, dpi=200):
    """
    Convert a scanned PDF into images, run OCR, and save as Markdown.
    WARNING: This is extremely CPU intensive for 400MB+ books.
    """
    filename = Path(pdf_path).name
    book_name = Path(pdf_path).stem
    out_file = os.path.join(OUTPUT_DIR, f"{book_name}_ocr.md")
    
    if os.path.exists(out_file):
        logging.info(f"OCR already exists for {book_name}. Skipping.")
        return

    logging.info(f"Starting OCR on {filename}...")
    logging.info("Converting PDF to images (this may take a long time and use massive RAM)...")
    
    try:
        # Convert PDF to list of images
        images = convert_from_path(pdf_path, dpi=dpi)
        logging.info(f"Extracted {len(images)} pages. Running Tesseract OCR...")
        
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(f"# OCR Extraction: {book_name}\n\n")
            
            for i, image in enumerate(images):
                if i % 50 == 0:
                    logging.info(f"Processing page {i}/{len(images)}...")
                
                text = pytesseract.image_to_string(image)
                f.write(f"\n## --- Page {i+1} ---\n\n")
                f.write(text.strip())
                f.write("\n\n")
                
        logging.info(f"✅ Finished OCR for {filename}. Saved to {out_file}.")
        
    except Exception as e:
        logging.error(f"Failed OCR on {filename}: {e}")
        logging.error("Ensure Tesseract-OCR and poppler are installed on Windows!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run OCR on scanned UPSC CMS textbooks.")
    parser.add_argument("--file", help="Specific PDF file to OCR (e.g., 'Harrison.pdf')")
    parser.add_argument("--all", action="store_true", help="Run OCR on all textbooks (WARNING: VERY SLOW)")
    
    args = parser.parse_args()
    
    logging.info(f"Looking for textbooks in: {BOOKS_DIR}")
    
    if args.all:
        for file in os.listdir(BOOKS_DIR):
            if file.endswith('.pdf') and not file.startswith('Copy of'):
                pdf_path = os.path.join(BOOKS_DIR, file)
                ocr_pdf_to_md(pdf_path)
    elif args.file:
        file_path = os.path.join(BOOKS_DIR, args.file)
        if os.path.exists(file_path):
            ocr_pdf_to_md(file_path)
        else:
            logging.error(f"File not found: {file_path}")
    else:
        print("\nUsage:")
        print("  python scripts/ocr_processor.py --file 'Ghai Essential Pediatrics, 9e.pdf'")
        print("  python scripts/ocr_processor.py --all\n")
        print("Note: Ensure you have installed Tesseract for Windows.")
