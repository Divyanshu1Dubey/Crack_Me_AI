\copy questions_questionimage (
  id, question_id, recall_source_id, page_number, image_index_in_page,
  file, mime, width, height, bytes, sha256, sha256_short, phash, dhash,
  modality, modality_subtype, body_region, ocr_text, caption, caption_source,
  ocr_confidence, extraction_confidence, has_diagram, has_table,
  is_watermarked, role, is_active, url, created_at, updated_at
) FROM 'backup/sql/questionimage.csv' WITH (FORMAT csv, HEADER true, NULL '');
SELECT 'questionimage COPY done';
