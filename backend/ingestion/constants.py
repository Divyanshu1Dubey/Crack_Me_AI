"""Enums and constants shared across the ingestion app.

Centralising the choices here keeps the model definitions concise and
makes it easy to add new exam types / statuses without touching
business logic.
"""
from __future__ import annotations

# ---------------------------------------------------------------- Exam types

EXAM_NEET_PG = "neet_pg"
EXAM_INI_CET = "ini_cet"
EXAM_FMGE = "fmge"
EXAM_USMLE = "usmle"
EXAM_PLAB = "plab"

EXAM_CHOICES = [
    (EXAM_NEET_PG, "NEET PG"),
    (EXAM_INI_CET, "INI-CET"),
    (EXAM_FMGE, "FMGE"),
    (EXAM_USMLE, "USMLE"),
    (EXAM_PLAB, "PLAB"),
]
EXAM_NAMES = {c[0]: c[1] for c in EXAM_CHOICES}


# ---------------------------------------------------------------- Job status

JOB_QUEUED = "queued"
JOB_PROCESSING = "processing"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_CANCELLED = "cancelled"
JOB_CRASHED = "crashed"

JOB_STATUS_CHOICES = [
    (JOB_QUEUED, "Queued"),
    (JOB_PROCESSING, "Processing"),
    (JOB_COMPLETED, "Completed"),
    (JOB_FAILED, "Failed"),
    (JOB_CANCELLED, "Cancelled"),
    (JOB_CRASHED, "Crashed"),
]

# Allowed state transitions. Frozen table checked by the orchestrator
# before mutating job.status. Any attempt to skip a state raises
# InvalidJobTransitionError.
JOB_TRANSITIONS: dict[str, set[str]] = {
    JOB_QUEUED: {JOB_PROCESSING, JOB_CANCELLED, JOB_FAILED, JOB_CRASHED},
    JOB_PROCESSING: {JOB_COMPLETED, JOB_FAILED, JOB_CANCELLED, JOB_CRASHED},
    JOB_COMPLETED: {JOB_QUEUED},  # retry path
    JOB_FAILED: {JOB_QUEUED},     # retry path
    JOB_CANCELLED: {JOB_QUEUED},  # restart path
    JOB_CRASHED: {JOB_QUEUED},    # resume-after-crash path
}


# ---------------------------------------------------------------- Stage names

STAGE_1_RENDER = "1_render"
STAGE_2_LAYOUT = "2_layout"
STAGE_2B_READING_ORDER = "2b_reading_order"
STAGE_3_IMAGES = "3_images"
STAGE_4_TABLES = "4_tables"
STAGE_5_QUESTION_BLOCKS = "5_question_blocks"
STAGE_6_OCR = "6_ocr"
STAGE_7_STRUCTURED = "7_structured"
STAGE_7_5_LLM = "7_5_llm"
STAGE_8_QA = "8_qa"
STAGE_9_GRAPH = "9_graph"
STAGE_10_RAG = "10_rag"
STAGE_DB_WRITER = "db_writer"
STAGE_CONSERVATIVE_GATE = "conservative_gate"

STAGE_CHOICES = [
    (STAGE_1_RENDER, "Stage 1: Render"),
    (STAGE_2_LAYOUT, "Stage 2: Layout"),
    (STAGE_2B_READING_ORDER, "Stage 2b: Reading Order"),
    (STAGE_3_IMAGES, "Stage 3: Images"),
    (STAGE_4_TABLES, "Stage 4: Tables"),
    (STAGE_5_QUESTION_BLOCKS, "Stage 5: Question Blocks"),
    (STAGE_6_OCR, "Stage 6: OCR"),
    (STAGE_7_STRUCTURED, "Stage 7: Structured"),
    (STAGE_7_5_LLM, "Stage 7.5: LLM"),
    (STAGE_8_QA, "Stage 8: QA"),
    (STAGE_9_GRAPH, "Stage 9: Graph"),
    (STAGE_10_RAG, "Stage 10: RAG"),
    (STAGE_DB_WRITER, "Stage db_writer"),
    (STAGE_CONSERVATIVE_GATE, "Conservative Gate"),
]

# Pipeline order used by the orchestrator. The same order the
# benchmark runner uses for the NEET-PG-2021 PDF.
PIPELINE_ORDER: list[str] = [
    STAGE_1_RENDER,
    STAGE_2_LAYOUT,
    STAGE_2B_READING_ORDER,
    STAGE_3_IMAGES,
    STAGE_4_TABLES,
    STAGE_5_QUESTION_BLOCKS,
    STAGE_6_OCR,
    STAGE_7_STRUCTURED,
    STAGE_7_5_LLM,  # optional, no-op when LLM unavailable
    STAGE_8_QA,
    STAGE_DB_WRITER,
    STAGE_CONSERVATIVE_GATE,
    STAGE_9_GRAPH,
    STAGE_10_RAG,
]


# ---------------------------------------------------------------- Stage status

STAGE_RUNNING = "running"
STAGE_COMPLETED = "completed"
STAGE_FAILED = "failed"
STAGE_SKIPPED = "skipped"

STAGE_STATUS_CHOICES = [
    (STAGE_RUNNING, "Running"),
    (STAGE_COMPLETED, "Completed"),
    (STAGE_FAILED, "Failed"),
    (STAGE_SKIPPED, "Skipped"),
]


# ---------------------------------------------------------------- Batch status

BATCH_OPEN = "open"
BATCH_RUNNING = "running"
BATCH_DONE = "done"
BATCH_CANCELLED = "cancelled"

BATCH_STATUS_CHOICES = [
    (BATCH_OPEN, "Open"),
    (BATCH_RUNNING, "Running"),
    (BATCH_DONE, "Done"),
    (BATCH_CANCELLED, "Cancelled"),
]


# ---------------------------------------------------------------- QA V2 buckets

QA_PRODUCTION_READY = "Production Ready"
QA_NEEDS_REVIEW = "Needs Review"
QA_EXTRACTION_FAILURE = "Extraction Failure"

QA_STATUS_CHOICES = [
    (QA_PRODUCTION_READY, "Production Ready"),
    (QA_NEEDS_REVIEW, "Needs Review"),
    (QA_EXTRACTION_FAILURE, "Extraction Failure"),
]


# ---------------------------------------------------------------- Review status

REVIEW_PENDING = "pending"
REVIEW_IN_REVIEW = "in_review"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"
REVIEW_PROMOTED = "promoted"
REVIEW_BLOCKED = "blocked"

REVIEW_STATUS_CHOICES = [
    (REVIEW_PENDING, "Pending"),
    (REVIEW_IN_REVIEW, "In Review"),
    (REVIEW_APPROVED, "Approved"),
    (REVIEW_REJECTED, "Rejected"),
    (REVIEW_PROMOTED, "Promoted"),
    (REVIEW_BLOCKED, "Blocked"),
]


# ---------------------------------------------------------------- Import strategies

STRATEGY_AUTO_PR_ONLY = "auto-pr-only"
STRATEGY_AUTO_ALL = "auto-all"
STRATEGY_MANUAL = "manual"

STRATEGY_CHOICES = [
    (STRATEGY_AUTO_PR_ONLY, "Auto-import Production Ready only (conservative)"),
    (STRATEGY_AUTO_ALL, "Auto-import Production Ready + Needs Review"),
    (STRATEGY_MANUAL, "Manual approval for every question"),
]


# ---------------------------------------------------------------- Artefact kinds

ARTIFACT_RENDER_PNG = "render_png"
ARTIFACT_LAYOUT_JSON = "layout_json"
ARTIFACT_IMAGE_PNG = "image_png"
ARTIFACT_TABLE_JSON = "table_json"
ARTIFACT_OCR_JSON = "ocr_json"
ARTIFACT_QA_PER_QUESTION_JSON = "qa_per_question_json"
ARTIFACT_QA_SUMMARY_JSON = "qa_summary_json"
ARTIFACT_DB_WRITER_RESULT = "db_writer_result"
ARTIFACT_OVERLAY_PNG = "overlay_png"
ARTIFACT_RAG_CHUNK_JSONL = "rag_chunk_jsonl"
ARTIFACT_GRAPH_NODE_JSONL = "graph_node_jsonl"
ARTIFACT_GRAPH_EDGE_JSONL = "graph_edge_jsonl"

ARTIFACT_KIND_CHOICES = [
    (ARTIFACT_RENDER_PNG, "Render PNG"),
    (ARTIFACT_LAYOUT_JSON, "Layout JSON"),
    (ARTIFACT_IMAGE_PNG, "Image PNG"),
    (ARTIFACT_TABLE_JSON, "Table JSON"),
    (ARTIFACT_OCR_JSON, "OCR JSON"),
    (ARTIFACT_QA_PER_QUESTION_JSON, "QA Per-Question JSON"),
    (ARTIFACT_QA_SUMMARY_JSON, "QA Summary JSON"),
    (ARTIFACT_DB_WRITER_RESULT, "DB Writer Result"),
    (ARTIFACT_OVERLAY_PNG, "Overlay PNG"),
    (ARTIFACT_RAG_CHUNK_JSONL, "RAG Chunk JSONL"),
    (ARTIFACT_GRAPH_NODE_JSONL, "Graph Node JSONL"),
    (ARTIFACT_GRAPH_EDGE_JSONL, "Graph Edge JSONL"),
]


# ---------------------------------------------------------------- Log levels

LOG_LEVEL_CHOICES = [
    ("DEBUG", "Debug"),
    ("INFO", "Info"),
    ("WARNING", "Warning"),
    ("ERROR", "Error"),
]


__all__ = [
    "EXAM_CHOICES",
    "EXAM_NAMES",
    "JOB_STATUS_CHOICES",
    "JOB_TRANSITIONS",
    "STAGE_CHOICES",
    "STAGE_STATUS_CHOICES",
    "BATCH_STATUS_CHOICES",
    "QA_STATUS_CHOICES",
    "REVIEW_STATUS_CHOICES",
    "STRATEGY_CHOICES",
    "ARTIFACT_KIND_CHOICES",
    "LOG_LEVEL_CHOICES",
    "PIPELINE_ORDER",
]
