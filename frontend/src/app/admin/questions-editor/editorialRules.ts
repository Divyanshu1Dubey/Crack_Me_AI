/**
 * Rules of the question editor's medical-accuracy panels (key change, evidence-first explanation
 * suggestion, provenance). Pure: no network, no DOM, so tests/unit can import it. Evidence rules and
 * audit labels come from lib/keyAudit (shared with the review queue), not copies of them.
 *
 * Ground rules shown in the UI (docs/audit/MEDICAL_ACCURACY_DESIGN.md §1): a key changes only with a
 * reason and is recorded; "verified" needs strong evidence; evidence first, key second (a conflict is
 * never explained away; weak evidence gives no suggestion); AI output is never a source.
 */
import type {
  ExplanationField,
  ExplanationSuggestion,
  KeyChangeRecord,
  SaveExplanationBody,
  SuggestionCitation,
  SuggestionStatus,
} from '@/lib/editorialAPI';
import {
  EVIDENCE_KINDS,
  LETTERS,
  STATUS_LABELS,
  cleanEvidence,
  describeError,
  evidenceError,
  expectedStatus,
  type AuditStatus,
  type BadgeTone,
  type EvidenceItem,
} from '@/lib/keyAudit';

export const EXPLANATION_FIELDS: readonly ExplanationField[] = ['explanation', 'concept_explanation', 'mnemonic'];
export const EXPLANATION_FIELD_LABELS: Record<ExplanationField, string> = {
  explanation: 'Explanation',
  concept_explanation: 'Concept explanation',
  mnemonic: 'Mnemonic',
};
export const MIN_REASON_CHARS = 10;

/** 'A'-'D' or ''. */
export function normalizeKey(value: unknown): string {
  const key = String(value ?? '').trim().toUpperCase();
  return (LETTERS as readonly string[]).includes(key) ? key : '';
}

// ---------------------------------------------------------------------------- key change

export interface KeyChangeForm {
  storedKey: string;
  newKey: string;
  reason: string;
  evidence: EvidenceItem[];
}

/** What still blocks the change, in the order the admin should fix it ([] = ready). */
export function keyChangeProblems(form: KeyChangeForm): string[] {
  const problems: string[] = [];
  const key = normalizeKey(form.newKey);
  if (!key) problems.push('Choose the new key.');
  else if (key === normalizeKey(form.storedKey)) problems.push(`${key} is already the key.`);
  if (form.reason.trim().length < MIN_REASON_CHARS) {
    problems.push(`Give a reason (at least ${MIN_REASON_CHARS} characters).`);
  }
  const bad = form.evidence.map(evidenceError).find(Boolean);
  if (bad) problems.push(bad);
  return problems;
}

/** The POST change-key/ body, or the first problem. `expected_key` lets the server refuse a stale form. */
export function keyChangePayload(form: KeyChangeForm):
  | { body: { new_key: string; reason: string; evidence: EvidenceItem[]; expected_key: string } }
  | { error: string } {
  const problems = keyChangeProblems(form);
  if (problems.length) return { error: problems[0] };
  return {
    body: {
      new_key: normalizeKey(form.newKey),
      reason: form.reason.trim(),
      evidence: form.evidence.map(cleanEvidence),
      expected_key: normalizeKey(form.storedKey),
    },
  };
}

/** The audit status a key change will lead to (the review queue's rule): verified only with strong evidence. */
export function keyChangeOutcome(evidence: EvidenceItem[]): AuditStatus {
  return expectedStatus({ resolution: 'key_changed', evidence }) === 'verified' ? 'verified' : 'likely_correct';
}

export function keyChangeOutcomeText(evidence: EvidenceItem[]): string {
  return keyChangeOutcome(evidence) === 'verified'
    ? 'Verified: you cite strong evidence (official key, errata, guideline link or a page-cited passage).'
    : 'Likely correct: without strong evidence a changed key is never "verified". Add an official key, errata, '
      + 'a guideline link or a page-cited passage with its quoted sentence to verify it.';
}

// ---------------------------------------------------------------------------- explanation suggestion

export const SUGGESTION_STATUS_LABELS: Record<SuggestionStatus, string> = {
  ok: 'Supported by reference passages',
  conflict: 'Evidence supports another option',
  insufficient_evidence: 'Not enough evidence',
  image_context_missing: 'Figure missing',
  failed: 'Check failed',
};

export function suggestionTone(status: string): BadgeTone {
  switch (status) {
    case 'ok':
      return 'success';
    case 'conflict':
      return 'destructive';
    case 'image_context_missing':
    case 'failed':
      return 'warning';
    default:
      return 'secondary';
  }
}

const MISSING_FIGURE_REASONS: Record<string, string> = {
  no_image_attached: 'no image is attached',
  unresolved_tokens: 'the text points at an image that does not exist',
  no_figure_context: 'the attached figure has no description (alt text, caption or OCR text)',
};

type SuggestionLike = Pick<ExplanationSuggestion, 'status' | 'for_key' | 'stored_key' | 'retrieval_mode' | 'conflict' | 'image_context'>;

/** A plain sentence on what the check found and why there is (or is not) a suggestion. */
export function suggestionMessage(s: SuggestionLike): string {
  const stored = normalizeKey(s.stored_key);
  switch (s.status) {
    case 'ok': {
      const base = `The reference passages below support option ${s.for_key}. The suggested text only quotes them: edit it before saving.`;
      return stored && stored !== s.for_key
        ? `${base} The stored key is ${stored}: change the key first if the evidence convinces you.`
        : base;
    }
    case 'conflict': {
      const other = s.conflict?.evidence_supports || 'another option';
      return `The reference passages support option ${other}, not ${s.for_key}. Nothing is suggested: an explanation must not argue for an option the evidence contradicts.`;
    }
    case 'insufficient_evidence':
      if (s.retrieval_mode === 'none') {
        return 'There is no reference store on this server, so nothing can be checked here and no explanation is suggested. Write it from a source you checked yourself.';
      }
      return `The reference passages found are too weak to support option ${s.for_key}. No explanation is suggested.`;
    case 'image_context_missing': {
      const why = MISSING_FIGURE_REASONS[s.image_context?.missing_reason ?? ''];
      return `This question depends on a figure${why ? `, but ${why}` : ' that is missing'}. Attach or describe the figure first; nothing is suggested.`;
    }
    case 'failed':
      return 'The evidence check failed on the server. Nothing is suggested; try again later.';
    default:
      return '';
  }
}

/** Why the suggestion cannot go into the editor (null = it can). */
export function acceptBlockedReason(s: Pick<ExplanationSuggestion, 'status' | 'for_key' | 'fields'>, storedKey: string): string | null {
  if (s.status !== 'ok') return 'Only a suggestion the evidence supports can be used.';
  const stored = normalizeKey(storedKey);
  if (!stored) return 'Set the answer key first: an explanation is written for a key.';
  if (s.for_key !== stored) return `This suggestion explains option ${s.for_key}; the key is ${stored}. Change the key first if the evidence convinces you, then check again.`;
  if (!acceptableFields(s).length) return 'The suggestion has no text.';
  return null;
}

/** The suggested explanation fields an admin may take into the editor (only fields save-explanation writes). */
export function acceptableFields(s: Pick<ExplanationSuggestion, 'fields'>): { field: ExplanationField; label: string; text: string }[] {
  const fields = (s.fields ?? {}) as Record<string, unknown>;
  return EXPLANATION_FIELDS.flatMap((field) => {
    const value = fields[field];
    return typeof value === 'string' && value.trim() ? [{ field, label: EXPLANATION_FIELD_LABELS[field], text: value }] : [];
  });
}

/** 'Harrison's Principles, PDF p. 1450 · tier 3' (the passage's own metadata only). */
export function citationWhere(c: Pick<SuggestionCitation, 'source_title' | 'page' | 'page_label' | 'tier'>): string {
  const page = c.page_label || (c.page !== null && c.page !== undefined && String(c.page).trim() ? `PDF p. ${c.page}` : '');
  const parts = [c.source_title || 'Reference', page, typeof c.tier === 'number' ? `tier ${c.tier}` : ''];
  return parts.filter(Boolean).join(' · ');
}

export interface OptionSupportRow {
  letter: string;
  support: number;
  passages: number;
  selected: boolean;
  stored: boolean;
  best: boolean;
}

/** One row per option: retrieval support (higher = more matching reference text; not a verdict). */
export function optionSupportRows(s: Pick<ExplanationSuggestion, 'option_evidence' | 'for_key' | 'stored_key'>): OptionSupportRow[] {
  const rows = LETTERS.map((letter) => {
    const entry = s.option_evidence?.[letter];
    const support = typeof entry?.support === 'number' && Number.isFinite(entry.support) ? entry.support : 0;
    return {
      letter,
      support,
      passages: Array.isArray(entry?.citations) ? entry.citations.length : 0,
      selected: letter === s.for_key,
      stored: letter === normalizeKey(s.stored_key),
      best: false,
    };
  });
  const top = Math.max(...rows.map((r) => r.support));
  if (top > 0) rows.forEach((r) => { r.best = r.support === top; });
  return rows;
}

/** The editor's unsaved stem / options / explanation fields, as explain-option's `draft`. */
export function draftFromForm(form: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', ...EXPLANATION_FIELDS]) {
    const value = form[name];
    if (typeof value === 'string') out[name] = value;
  }
  return out;
}

// ---------------------------------------------------------------------------- saving the explanation

export interface SaveExplanationInput {
  fields: Record<string, unknown>;
  forKey: string;
  suggestionId?: string | null;
  acceptedFields?: string[];
  aiFields?: string[];
}

/** The POST save-explanation/ body, or why it cannot be sent. */
export function saveExplanationBody(input: SaveExplanationInput): { body: SaveExplanationBody } | { error: string } {
  const forKey = normalizeKey(input.forKey);
  if (!forKey) return { error: 'Set the answer key first: an explanation is written for a key.' };
  const fields: Partial<Record<ExplanationField, string>> = {};
  for (const field of EXPLANATION_FIELDS) {
    const value = input.fields[field];
    if (typeof value === 'string') fields[field] = value;
  }
  if (!Object.keys(fields).length) return { error: 'Nothing to save.' };
  const body: SaveExplanationBody = { fields, for_key: forKey };
  const accepted = EXPLANATION_FIELDS.filter((f) => (input.acceptedFields ?? []).includes(f) && f in fields);
  if (input.suggestionId && accepted.length) {
    body.suggestion_id = input.suggestionId;
    body.accepted_fields = accepted;
  }
  const ai = EXPLANATION_FIELDS.filter((f) => (input.aiFields ?? []).includes(f) && f in fields);
  if (ai.length) body.ai_fields = ai;
  return { body };
}

/** Explanation fields whose form value differs from what was loaded / last saved. */
export function changedExplanationFields(form: Record<string, unknown>, baseline: Record<string, unknown>): ExplanationField[] {
  return EXPLANATION_FIELDS.filter((f) => String(form[f] ?? '') !== String(baseline[f] ?? ''));
}

// ---------------------------------------------------------------------------- provenance

export const EXPLANATION_STATUS_LABELS: Record<string, string> = {
  absent: 'No explanation',
  none: 'No explanation',
  stale: 'Stale',
  conflict: 'Written for another key',
  pending_review: 'Not reviewed',
  ai_generated: 'AI-generated, not reviewed',
  human_edited: 'Written or edited by an admin',
  source_verified: 'Checked against a source',
  reviewed: 'Reviewed',
};

export const EXPLANATION_STATUS_HINTS: Record<string, string> = {
  absent: 'Students see no curated explanation.',
  stale: 'The key or the question text changed after it was written: rewrite or confirm it.',
  conflict: 'It argues for another option than the stored key: rewrite it for the key.',
  pending_review: 'Saved before provenance was recorded: nobody has checked it for the current key.',
  ai_generated: 'AI text is a draft, not a source: review it before students rely on it.',
};

export function explanationTone(status: string): BadgeTone {
  switch (status) {
    case 'stale':
    case 'conflict':
      return 'destructive';
    case 'pending_review':
    case 'ai_generated':
      return 'warning';
    case 'reviewed':
    case 'source_verified':
    case 'human_edited':
      return 'success';
    default:
      return 'secondary';
  }
}

/** Mark-reviewed is refused for an empty, stale or conflicting explanation (the backend rule). */
export function canMarkReviewed(status: string): boolean {
  return !['absent', 'none', 'stale', 'conflict'].includes(status);
}

export const ORIGIN_LABELS: Record<string, string> = {
  ai: 'AI',
  human: 'Admin',
  mixed: 'Admin, from a suggestion or AI draft',
  import: 'Imported',
  legacy: 'Legacy (unknown)',
};

export function originLabel(origin: string | null | undefined): string {
  return ORIGIN_LABELS[origin ?? ''] ?? 'Not recorded';
}

export const KEY_CHANGE_SOURCE_LABELS: Record<string, string> = {
  editor: 'question editor',
  review_queue: 'review queue',
  resolve_dispute: 'dispute resolution',
  generate_explanation: 'explanation generator',
  undo_revision: 'undo to a revision',
  management_command: 'management command',
  legacy_snapshot: 'recovered from revision history',
};

export function auditStatusLabel(status: string | null | undefined): string {
  if (!status || status === 'unaudited') return 'Not audited yet';
  return STATUS_LABELS[status as AuditStatus] ?? status.replace(/_/g, ' ');
}

/** 'Textbook passage (page + quote) (strong), Note (reasoning, not evidence)' */
export function evidenceSummary(items: EvidenceItem[] | null | undefined): string {
  return (items ?? [])
    .map((item) => {
      const spec = EVIDENCE_KINDS.find((k) => k.kind === item.kind);
      return spec ? `${spec.label}${spec.strong ? ' (strong)' : ''}` : String(item.kind ?? 'unknown');
    })
    .join(', ');
}

export function keyChangeLine(change: Pick<KeyChangeRecord, 'old_key' | 'new_key' | 'changed_by_username' | 'source'>): string {
  const by = change.changed_by_username || 'unknown';
  const where = KEY_CHANGE_SOURCE_LABELS[change.source] ?? change.source;
  return `${change.old_key || '–'} → ${change.new_key} by ${by} (${where})`;
}

/** The review queue has no deep link (it does not read ?q=): the queue plus the id to search for. */
export function reviewQueueLink(questionId: number): { href: string; hint: string } {
  return { href: `/admin/review-queue?q=${questionId}`, hint: `Opens question ${questionId} in the review queue.` };
}

export function formatWhen(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** A readable message for a failed editor request: the server's own sentence for coded errors. */
export function describeEditorialError(err: unknown): string {
  const response = (err as { response?: { status?: number; data?: unknown } })?.response;
  const data = response?.data as Record<string, unknown> | undefined;
  if (response?.status === 409 && data?.code === 'key_changed') {
    return `The key is now ${String(data.current_key || 'not set')}: it changed since you opened this question. Close and reopen it.`;
  }
  if (response?.status === 429) return 'Too many requests: wait a minute and try again.';
  if (data && typeof data === 'object' && typeof data.code === 'string' && typeof data.detail === 'string') {
    return data.detail;
  }
  return describeError(err);
}
