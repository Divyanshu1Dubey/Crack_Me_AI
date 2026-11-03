// Display labels shared by the /admin/ingestion pages.

// Same names as backend/ingestion/constants.py EXAM_CHOICES.
export const EXAM_LABEL: Record<string, string> = {
  neet_pg: 'NEET PG',
  ini_cet: 'INI-CET',
  fmge: 'FMGE',
  usmle: 'USMLE',
  plab: 'PLAB',
};

// Pipeline stages (backend/ingestion/constants.py STAGE_CHOICES).
const STAGE_LABEL: Record<string, string> = {
  '1_render': 'Render',
  '2_layout': 'Layout',
  '2b_reading_order': 'Reading order',
  '3_images': 'Images',
  '4_tables': 'Tables',
  '5_question_blocks': 'Question blocks',
  '6_ocr': 'OCR',
  '7_structured': 'Structured',
  '7_5_llm': 'LLM pass',
  '8_qa': 'QA',
  '9_graph': 'Graph',
  '10_rag': 'RAG index',
  db_writer: 'DB writer',
  conservative_gate: 'Import gate',
};

type JobLike = { exam?: string; exam_label?: string; parent_exam?: string };

/** The job's exam name; the API falls back to the material's exam hint. */
export function examLabel(job: JobLike): string {
  if (job.exam_label) return job.exam_label;
  const code = job.exam || job.parent_exam || '';
  return EXAM_LABEL[code] || code || '—';
}

export function stageLabel(stage?: string | null): string {
  if (!stage) return '—';
  return STAGE_LABEL[stage] || stage.replace(/_/g, ' ');
}

export const QA_TITLE = 'Production-ready % / Needs-review % / Extraction-failure %';
