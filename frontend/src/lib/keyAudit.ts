/**
 * Answer-key review queue: types, labels and the rules the admin page shares with the backend
 * (backend/key_audit). Pure (no network, no DOM) so tests/unit can import it.
 *
 * Ground rules shown in the UI: an AI review is a review signal, never evidence; nothing changes a key
 * except an admin decision; "verified" needs strong evidence (official key, errata, guideline, a
 * page-cited passage). A printed source key or a note gives "likely correct".
 */

export type AuditStatus =
  | 'verified'
  | 'likely_correct'
  | 'needs_review'
  | 'contradictory_sources'
  | 'insufficient_evidence'
  | 'image_context_missing';

export const STATUS_ORDER: AuditStatus[] = [
  'needs_review',
  'contradictory_sources',
  'image_context_missing',
  'insufficient_evidence',
  'likely_correct',
  'verified',
];

export const STATUS_LABELS: Record<AuditStatus, string> = {
  needs_review: 'Needs review',
  contradictory_sources: 'Contradictory sources',
  image_context_missing: 'Image missing',
  insufficient_evidence: 'Insufficient evidence',
  likely_correct: 'Likely correct',
  verified: 'Verified',
};

export const STATUS_HINTS: Record<AuditStatus, string> = {
  needs_review: 'A risk signal is open: the key may be wrong.',
  contradictory_sources: 'Sources that count support different options.',
  image_context_missing: 'The question needs a figure that is not attached.',
  insufficient_evidence: 'Nothing settles the key either way. One AI opinion or one printed key is not enough.',
  likely_correct: 'Independent signals agree, or an admin confirmed it without citing strong evidence.',
  verified: 'Official key, or an admin decision that cites strong evidence.',
};

export type BadgeTone = 'destructive' | 'warning' | 'success' | 'secondary' | 'outline';

export function statusTone(status: string): BadgeTone {
  switch (status) {
    case 'needs_review':
    case 'contradictory_sources':
      return 'destructive';
    case 'image_context_missing':
      return 'warning';
    case 'likely_correct':
    case 'verified':
      return 'success';
    default:
      return 'secondary';
  }
}

export function severityTone(severity: string): BadgeTone {
  if (severity === 'critical') return 'destructive';
  if (severity === 'high' || severity === 'medium') return 'warning';
  return 'outline';
}

/** Labels for signal codes and status reasons (key_audit/classify.py). */
export const SIGNAL_LABELS: Record<string, string> = {
  official_key_disagrees: 'Official key names another option',
  source_key_mismatch: 'Printed key differs (checked)',
  source_key_mismatch_unverified: 'Printed key differs (not checked)',
  evidence_conflict: 'Reference passages support another option',
  invalid_or_missing_key: 'Key is not A-D',
  explanation_states_other: 'Explanation names another option',
  label_key_conflict: 'Answer label in the text disagrees',
  label_hold: 'Answer label needs a manual repair',
  human_requested_review: 'An admin asked for a review',
  key_changed_after_review: 'Key changed after an admin decision',
  open_wrong_answer_report: 'Open student report',
  ai_review_disagrees: 'AI review signal disagrees',
  duplicate_key_conflict: 'A duplicate has another key',
  skewed_key_distribution: 'Possible importer default key',
  is_disputed: 'Marked disputed',
  ai_no_correct_option: 'AI: no / several correct options',
  ai_content_defect: 'AI: options incomplete or garbled',
  ai_ambiguous: 'AI: ambiguous or guideline-dependent',
  image_context_missing: 'Figure missing',
  explanation_conflicts_with_reviewed_key: 'Explanation contradicts the reviewed key',
  ai_chosen_key: 'Key was chosen by an AI importer',
  needs_review_flag: 'needs_review flag set',
  ai_answer_in_text: 'AI: answer given away in the text',
  ai_wrong_subject: 'AI: wrong subject',
  source_year_differs: 'Source files it under another year',
  stale_reviews_ignored: 'Reviews of an earlier version ignored',
  // status reasons that are not signal codes
  official_key_match: 'Official key matches',
  human_verified_with_evidence: 'Admin decision with strong evidence',
  human_confirmed: 'Admin confirmed (no strong evidence)',
  new_signal_after_review: 'New signal after an admin decision',
  source_keys_disagree: 'Printed keys disagree with each other',
  evidence_contradictory: 'Reference passages contradict each other',
  evidence_verified: 'Verified passages + two agreements',
  evidence_supported: 'Verified passages support the key',
  independent_agreement: 'Two independent signals agree',
  no_independent_agreement: 'Only one signal agrees',
  no_evidence: 'No evidence either way',
};

export function signalLabel(code: string | null | undefined): string {
  if (!code) return '';
  return SIGNAL_LABELS[code] ?? code.replace(/_/g, ' ');
}

export interface Signal {
  code: string;
  severity: string;
  detail: string;
  opens_review: boolean;
  priority: number;
  suggested_key?: string;
  at?: string;
  data?: Record<string, unknown>;
  settled_by_review?: boolean;
}

export interface PrintedKey {
  id: number;
  letter: string;
  printed_letter?: string;
  source_file?: string;
  question_page?: number;
  question_number?: number;
  answer_page?: number | null;
}

export interface QueueRow {
  id: number;
  question_id: number;
  status: AuditStatus;
  status_reason: string;
  stored_key: string;
  suggested_key: string;
  suggested_from: string;
  priority: number;
  open_signals: string[];
  is_stale: boolean;
  audited_at: string;
  question_text: string;
  exam_type: string;
  year: number | null;
  subject: string;
  claimed_by: string | null;
  printed_key: PrintedKey | null;
}

export interface SourceKeyRow {
  id: number;
  source_file: string;
  question_page: number;
  question_number: number;
  answer_page: number | null;
  chapter: string;
  source_exam: string;
  source_year: number | null;
  printed_letter: string;
  letter: string;
  option_order: 'same' | 'reordered' | 'assumed_same';
  method: 'answer_key_table' | 'inline_answer';
  located: boolean;
  confident: boolean;
}

export interface ReviewRow {
  reviewer: string;
  kind: 'ai' | 'official' | 'human' | 'evidence';
  label: string;
  pass: number;
  verdict: string;
  best_option: string;
  confidence: string;
  explanation_check: string;
  issues: string[];
  reason: string;
  stored_key: string;
  at: string;
  official_source?: string;
}

export interface AuditDetail {
  id: number;
  question_id: number;
  status: AuditStatus;
  status_reason: string;
  stored_key: string;
  original_key: string;
  key_provenance: string;
  suggested_key: string;
  priority: number;
  signals: Signal[];
  evidence_summary: {
    suggested_from?: string;
    agreements?: { kind: string; detail: string }[];
    human_decision?: { reviewer: string; verdict: string; best_option: string; strong_evidence: boolean; at: string | null; source: string } | null;
  };
  is_stale: boolean;
  audited_at: string;
  question: {
    id: number;
    question_text: string;
    option_a: string;
    option_b: string;
    option_c: string;
    option_d: string;
    correct_answer: string;
    explanation: string;
    exam_type: string;
    year: number | null;
    subject: string;
    topic: string;
    source: string;
    is_active: boolean;
    is_dropped: boolean;
    is_disputed: boolean;
    answer_key_status: string;
    image_ids: number[];
  };
  reviews: ReviewRow[];
  source_keys: SourceKeyRow[];
  resolutions: { id: number; resolution: string; reason: string; evidence: EvidenceItem[]; status_before: string; stored_key: string; resolved_by: string; resolved_at: string }[];
  key_changes: { id: number; old_key: string; new_key: string; source: string; reason: string; changed_by: string; changed_at: string }[];
  claim: { claimed_by: string; mine: boolean; expires_at: string } | null;
}

export const LETTERS = ['A', 'B', 'C', 'D'] as const;
export type Letter = (typeof LETTERS)[number];

// ---------------------------------------------------------------------------- evidence

export type EvidenceKind = 'official_key' | 'errata' | 'guideline_url' | 'passage' | 'source_key' | 'note';

export interface EvidenceItem {
  kind: EvidenceKind;
  source_title?: string;
  edition?: string;
  page_label?: string;
  quote?: string;
  url?: string;
  text?: string;
  source_key_id?: number;
  supports_option?: string;
}

export const EVIDENCE_KINDS: { kind: EvidenceKind; label: string; strong: boolean; required: (keyof EvidenceItem)[] }[] = [
  { kind: 'official_key', label: 'Official answer key', strong: true, required: ['source_title'] },
  { kind: 'errata', label: 'Official errata', strong: true, required: ['source_title'] },
  { kind: 'guideline_url', label: 'Guideline (link)', strong: true, required: ['source_title', 'url'] },
  { kind: 'passage', label: 'Textbook passage (page + quote)', strong: true, required: ['source_title', 'page_label', 'quote'] },
  { kind: 'source_key', label: 'Printed source key', strong: false, required: ['source_key_id'] },
  { kind: 'note', label: 'Note (reasoning, not evidence)', strong: false, required: ['text'] },
];

const URL_RE = /^https?:\/\/[^\s<>"']{3,}$/i;

/** The backend's rule for one item (key_audit/serializers.py clean_evidence_item); null when valid. */
export function evidenceError(item: EvidenceItem): string | null {
  const spec = EVIDENCE_KINDS.find((k) => k.kind === item.kind);
  if (!spec) return 'Choose the kind of evidence.';
  const missing = spec.required.filter((field) => {
    const value = item[field];
    return value === undefined || value === null || String(value).trim() === '';
  });
  if (missing.length) return `${spec.label} needs ${missing.join(', ').replace(/_/g, ' ')}.`;
  if (item.url && !URL_RE.test(item.url.trim())) return 'The link must start with http:// or https://.';
  if (item.kind === 'passage' && (item.quote ?? '').trim().length < 10) {
    return 'Quote the sentence that states the answer (at least 10 characters).';
  }
  return null;
}

export function hasStrongEvidence(items: EvidenceItem[]): boolean {
  return items.some((item) => EVIDENCE_KINDS.find((k) => k.kind === item.kind)?.strong && !evidenceError(item));
}

export function sourceKeyEvidence(row: Pick<SourceKeyRow, 'id' | 'source_file' | 'question_page'>): EvidenceItem {
  return { kind: 'source_key', source_key_id: row.id, source_title: row.source_file, page_label: `PDF p. ${row.question_page}` };
}

/** Only the fields the backend keeps for the item's kind (empty strings dropped). */
export function cleanEvidence(item: EvidenceItem): EvidenceItem {
  const out: EvidenceItem = { kind: item.kind };
  (['source_title', 'edition', 'page_label', 'quote', 'url', 'text', 'supports_option'] as const).forEach((field) => {
    const value = item[field];
    if (typeof value === 'string' && value.trim()) out[field] = value.trim();
  });
  if (typeof item.source_key_id === 'number') out.source_key_id = item.source_key_id;
  return out;
}

// ---------------------------------------------------------------------------- decisions

export type Resolution =
  | 'key_confirmed'
  | 'key_changed'
  | 'deferred'
  | 'image_requested'
  | 'explanation_fixed'
  | 'dropped'
  | 'question_deactivated';

export const RESOLUTIONS: { value: Resolution; label: string; hint: string }[] = [
  { value: 'key_confirmed', label: 'Confirm the stored key', hint: 'Verified with strong evidence; likely correct without.' },
  { value: 'key_changed', label: 'Change the key', hint: 'Records the old key, you, the reason and the evidence.' },
  { value: 'deferred', label: 'Defer', hint: 'Keeps the question in the queue (needs review).' },
  { value: 'image_requested', label: 'Request the figure', hint: 'Notes that the image must be attached first.' },
  { value: 'explanation_fixed', label: 'Fix the explanation', hint: 'Saves the corrected explanation for the stored key.' },
  { value: 'dropped', label: 'Drop from scoring', hint: 'For a question with no single correct answer.' },
  { value: 'question_deactivated', label: 'Deactivate the question', hint: 'Hides it from students.' },
];

export interface ResolveForm {
  resolution: Resolution;
  reason: string;
  newKey?: string;
  expectedKey: string;
  evidence: EvidenceItem[];
  explanation?: string;
}

/** The request body for POST queue/<id>/resolve/, or an error message for the form. */
export function resolvePayload(form: ResolveForm): { body: Record<string, unknown> } | { error: string } {
  const reason = form.reason.trim();
  if (reason.length < 10) return { error: 'Give a reason (at least 10 characters).' };
  const bad = form.evidence.map(evidenceError).find(Boolean);
  if (bad) return { error: bad };
  const body: Record<string, unknown> = {
    resolution: form.resolution,
    reason,
    expected_key: form.expectedKey,
    evidence: form.evidence.map(cleanEvidence),
  };
  if (form.resolution === 'key_changed') {
    const key = (form.newKey ?? '').toUpperCase();
    if (!(LETTERS as readonly string[]).includes(key)) return { error: 'Choose the new key (A-D).' };
    if (key === form.expectedKey) return { error: 'The new key is the stored key: confirm it instead.' };
    body.new_key = key;
  }
  if (form.resolution === 'explanation_fixed') {
    if (!(form.explanation ?? '').trim()) return { error: 'Write the corrected explanation.' };
    body.explanation_fields = { explanation: form.explanation };
  }
  return { body };
}

export function expectedStatus(form: Pick<ResolveForm, 'resolution' | 'evidence'>): string {
  if (form.resolution === 'key_confirmed' || form.resolution === 'key_changed') {
    return hasStrongEvidence(form.evidence) ? 'verified' : 'likely_correct';
  }
  if (form.resolution === 'deferred') return 'needs_review';
  return '';
}

/** A readable message for a failed queue request (axios-style error). */
export function describeError(err: unknown): string {
  const response = (err as { response?: { status?: number; data?: unknown } })?.response;
  const data = response?.data as Record<string, unknown> | undefined;
  if (response?.status === 409) {
    if (data?.code === 'claimed') return `Claimed by ${String(data.claimed_by ?? 'another admin')} — pick another question.`;
    if (data?.code === 'key_changed') return `The key changed to ${String(data.current_key || '?')} since you opened it — reload.`;
  }
  if (response?.status === 403) return 'Admin access is needed.';
  if (data && typeof data === 'object') {
    const parts = Object.entries(data).map(([field, value]) => {
      const text = Array.isArray(value) ? value.join(' ') : typeof value === 'string' ? value : JSON.stringify(value);
      return field === 'detail' ? text : `${field}: ${text}`;
    });
    if (parts.length) return parts.join(' · ').slice(0, 400);
  }
  return (err as Error)?.message || 'Request failed.';
}

// ---------------------------------------------------------------------------- batch

export interface BatchItem {
  question_id: number;
  expected_key: string;
  source_key_id: number;
}

/** Rows eligible for "accept printed key": a confident printed key behind the suggestion, not claimed by someone else. */
export function batchEligible(row: QueueRow, me: string | null | undefined): boolean {
  return !!row.printed_key && row.suggested_from === 'source_key_mismatch' && !!row.stored_key
    && row.printed_key.letter === row.suggested_key && (!row.claimed_by || row.claimed_by === me);
}

export function batchItems(rows: QueueRow[], selected: Set<number>, me: string | null | undefined): BatchItem[] {
  return rows
    .filter((row) => selected.has(row.question_id) && batchEligible(row, me))
    .slice(0, 25)
    .map((row) => ({ question_id: row.question_id, expected_key: row.stored_key, source_key_id: (row.printed_key as PrintedKey).id }));
}

export function optionText(question: AuditDetail['question'], letter: string): string {
  const key = `option_${letter.toLowerCase()}` as 'option_a' | 'option_b' | 'option_c' | 'option_d';
  return question[key] ?? '';
}
