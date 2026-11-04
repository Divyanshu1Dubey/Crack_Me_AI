/**
 * Question-editor endpoints (backend/questions/views_editorial.py, under /api/questions/<id>/):
 * provenance, answer-key change, key history, evidence-first explanation suggestions, explanation
 * save, key confirmation. Admin only. Types are the backend's payloads; the rules the editor panels
 * apply to them live in app/admin/questions-editor/editorialRules.ts (pure, unit-tested).
 */
import api from '@/lib/api';
import type { EvidenceItem, SourceKeyRow } from '@/lib/keyAudit';

export type ExplanationField = 'explanation' | 'concept_explanation' | 'mnemonic';

export type SuggestionStatus = 'ok' | 'conflict' | 'insufficient_evidence' | 'image_context_missing' | 'failed';

/** A passage from the reference store (never model-written): title, page, a quote of at most 240 characters. */
export interface SuggestionCitation {
  chunk_key: string;
  source_title: string;
  page: number | string | null;
  page_label: string;
  tier: number | null;
  snippet: string;
}

export interface OptionEvidence {
  support: number;
  contradiction: number;
  citations: SuggestionCitation[];
}

export interface SuggestionConflict {
  evidence_supports: string;
  selected: string;
  stored: string;
  margin: number;
  summary: string;
  acknowledged?: boolean;
}

export interface ExplanationSuggestion {
  id: string;
  question_id: number;
  requested_by_username: string;
  created_at: string;
  for_key: string;
  stored_key: string;
  mode: string;
  provider: string;
  model: string;
  /** 'none' = no reference store on the server; 'error' = the check failed. */
  retrieval_mode: string;
  status: SuggestionStatus;
  fields: Partial<Record<ExplanationField, string>>;
  field_citations: Record<string, string[]>;
  citations: SuggestionCitation[];
  dropped_claims: unknown[];
  option_evidence: Record<string, OptionEvidence>;
  conflict: SuggestionConflict | null;
  image_context: { required?: boolean; available?: boolean; missing_reason?: string } | null;
  used_draft: boolean;
  draft_stem_hash: string;
  accepted_at: string | null;
  accepted_by_username: string;
}

export interface AuditSummary {
  status: string;
  status_reason: string;
  stored_key: string;
  original_key: string;
  key_provenance: string;
  suggested_key: string;
  suggested_from: string;
  priority: number;
  is_stale: boolean;
  audited_at: string | null;
  open_signals: string[];
}

export interface ExplanationProvenance {
  /** Computed: absent | stale | conflict | pending_review | ai_generated | human_edited | source_verified | reviewed */
  status: string;
  status_reason: string;
  stored_status: string;
  origin: string;
  for_key: string;
  reviewed_by: string;
  reviewed_at: string | null;
  suggestion_id: string | null;
  has_text: boolean;
  locked: boolean;
}

export interface Verification {
  verified_by: string;
  verified_at: string | null;
  is_verified_by_admin: boolean;
  verified_note: string;
}

export type ProvenanceSourceKey = SourceKeyRow & { current_content: boolean };

export interface Provenance {
  question_id: number;
  correct_answer: string;
  stem_hash: string;
  updated_at: string;
  is_active: boolean;
  is_dropped: boolean;
  is_disputed: boolean;
  needs_review: boolean;
  lock_answer: boolean;
  answer_key_status: string;
  audit: AuditSummary | null;
  verification: Verification;
  explanation: ExplanationProvenance;
  key_change_count: number;
  source_keys: ProvenanceSourceKey[];
  reference_store_available: boolean;
}

export interface KeyChangeRecord {
  id: number;
  question_id: number;
  old_key: string;
  new_key: string;
  changed_at: string;
  changed_by_username: string;
  source: string;
  reason: string;
  evidence: EvidenceItem[];
  explanation_action: string;
  rescore_status: string;
  rescored_at: string | null;
  rescored_by_username: string;
}

export interface KeyChangeResult {
  ok: boolean;
  question_id: number;
  old_key: string;
  new_key: string;
  strong_evidence: boolean;
  answer_key_status: string;
  audit: AuditSummary | null;
  explanation: ExplanationProvenance;
  needs_review: boolean;
  is_disputed: boolean;
  updated_at: string;
  change: KeyChangeRecord;
}

export interface SaveExplanationResult {
  ok: boolean;
  question_id: number;
  explanation_status: string;
  explanation_status_reason: string;
  explanation: ExplanationProvenance;
  answer_key_status: string;
  updated_at: string;
}

export interface VerifyResult {
  ok: boolean;
  action: 'verify' | 'unverify';
  answer_key_status: string;
  is_verified: boolean;
  verification: Verification;
  audit: AuditSummary | null;
  needs_review: boolean;
  is_disputed: boolean;
  updated_at: string;
}

export interface ChangeKeyBody {
  new_key: string;
  reason: string;
  evidence: EvidenceItem[];
  expected_key: string;
  explanation_fields?: Partial<Record<ExplanationField, string>>;
}

export interface ExplainOptionBody {
  selected: string;
  draft?: Record<string, string | boolean>;
  acknowledge_conflict?: boolean;
}

export interface SaveExplanationBody {
  fields: Partial<Record<ExplanationField, string>>;
  for_key: string;
  suggestion_id?: string;
  accepted_fields?: ExplanationField[];
  ai_fields?: ExplanationField[];
}

export const editorialAPI = {
  provenance: (questionId: number) => api.get<Provenance>(`/questions/${questionId}/provenance/`),
  keyHistory: (questionId: number) =>
    api.get<{ question_id: number; current_key: string; changes: KeyChangeRecord[] }>(`/questions/${questionId}/key-history/`),
  changeKey: (questionId: number, body: ChangeKeyBody) =>
    api.post<KeyChangeResult>(`/questions/${questionId}/change-key/`, body),
  explainOption: (questionId: number, body: ExplainOptionBody) =>
    api.post<ExplanationSuggestion>(`/questions/${questionId}/explain-option/`, body),
  saveExplanation: (questionId: number, body: SaveExplanationBody) =>
    api.post<SaveExplanationResult>(`/questions/${questionId}/save-explanation/`, body),
  verifyKey: (questionId: number, body: { action: 'verify' | 'unverify'; reason?: string }) =>
    api.post<VerifyResult>(`/questions/${questionId}/verify-key/`, body),
  reviewExplanation: (questionId: number) =>
    api.post<{ ok: boolean; explanation_status: string; explanation: ExplanationProvenance; updated_at: string }>(
      `/questions/${questionId}/review-explanation/`,
    ),
};
