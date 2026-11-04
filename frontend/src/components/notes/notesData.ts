/**
 * PYQ topic notes: types, labels and the pure rules the student pages (app/topic-notes) and the
 * admin builder (app/admin/notes) share with the backend (questions/notes_builder.py,
 * questions/views_notes.py). No network and no DOM, so tests/unit/notes-data.test.ts imports it.
 *
 * Ground rules the UI shows (docs/audit/MEDICAL_ACCURACY_DESIGN.md):
 * - a point is "provisional" while the answer key behind it is not verified; it is never shown
 *   as certain;
 * - excluded PYQs (no key, disputed, scholarship, open wrong-answer report, ...) never feed a note;
 * - a textbook line is a verbatim quote (at most 240 characters) with its citation, never a page;
 * - a free account reads only the points whose PYQs are all free questions (the server filters).
 */

export type KeyStatus = 'verified' | 'provisional' | 'excluded';

export interface NoteSource {
  id: number;
  label: string;
  year: number | null;
  exam_type: string;
  key_status: string;
}

export interface NoteEvidence {
  title?: string;
  edition?: string;
  year?: number | null;
  page_label?: string;
  page_start?: number | null;
  page_end?: number | null;
  excerpt: string;
  truncated?: boolean;
  label?: string;
}

export interface NotePoint {
  id: string;
  kind: 'fact' | 'practice' | string;
  stem: string;
  answer: string;
  key_status: string;
  question_ids: number[];
  asked_in: string[];
  frequency: number;
  sources?: NoteSource[];
  latest_year?: number;
  why?: string;
  practice_reason?: string;
  evidence?: NoteEvidence[];
}

export interface NoteSection {
  id?: string;
  title: string;
  kind?: string;
  points: string[];
}

export interface NoteCounts {
  cited?: number;
  verified?: number;
  provisional?: number;
  points?: number;
  facts?: number;
  practice?: number;
  repeated_points?: number;
  evidence_points?: number;
  sections?: number;
}

/** A note as students read it (GET topic-notes/published/ and .../published/<id>/). */
export interface PublishedNote {
  id: number;
  title: string;
  subject: number | null;
  subject_name: string;
  topic: number | null;
  topic_name: string;
  exam_type: string;
  is_combined: boolean;
  content: string;
  content_preview: string;
  source_question_ids: number[];
  source_question_count: number;
  ai_generated: boolean;
  is_published: boolean;
  generation_method: string;
  builder_version: string;
  built_at: string | null;
  is_stale: boolean;
  verified_source_count: number;
  provisional_source_count: number;
  answers_locked: boolean;
  locked_points: number | null;
  hidden_points: number;
  counts?: NoteCounts;
  created_at?: string;
  updated_at?: string;
  /** Detail only, and only for notes built from PYQs. */
  sections?: NoteSection[] | null;
  points?: NotePoint[] | null;
}

export interface NoteFacets {
  total: number;
  exams: { value: string; count: number }[];
  subjects: { id: number; name: string; count: number; topics: { id: number; name: string; count: number }[] }[];
}

// ---------------------------------------------------------------------------- labels

export const EXAM_LABELS: Record<string, string> = {
  cms: 'UPSC CMS',
  neet_pg: 'NEET PG',
  ini_cet: 'INI-CET',
  all: 'All exams',
  usmle: 'USMLE',
  fmge: 'FMGE',
  other: 'Other',
};

/** Exam filter of the student list; an exam also lists the cross-exam ('all') notes. */
export const EXAM_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'All notes' },
  { value: 'cms', label: 'UPSC CMS' },
  { value: 'neet_pg', label: 'NEET PG' },
  { value: 'ini_cet', label: 'INI-CET' },
  { value: 'all', label: 'Cross-exam' },
];

export const PROVISIONAL_LABEL = 'Provisional — answer key not yet verified';
export const VERIFIED_LABEL = 'Verified key';
export const PROVISIONAL_HINT =
  'Nothing contradicts this answer key, but it has not been verified yet (official key, guideline or a cited ' +
  'textbook page). Check it before you rely on it.';
/** The reader's legend above a note with provisional points. */
export const PROVISIONAL_LEGEND =
  'points come from PYQs whose answer key has not been verified yet (official key, guideline or a cited textbook ' +
  'page). Check them before you rely on them.';

export function examLabel(exam: string | null | undefined, isCombined = false): string {
  if (isCombined || exam === 'all') return EXAM_LABELS.all;
  return EXAM_LABELS[exam ?? ''] ?? (exam ? exam.toUpperCase() : '');
}

export function isProvisional(status: string | null | undefined): boolean {
  return status !== 'verified';
}

export function keyStatusLabel(status: string | null | undefined): string {
  if (status === 'verified') return VERIFIED_LABEL;
  if (status === 'excluded') return 'Excluded';
  return PROVISIONAL_LABEL;
}

export type BadgeTone = 'success' | 'warning' | 'destructive' | 'secondary' | 'outline';

export function keyStatusTone(status: string | null | undefined): BadgeTone {
  if (status === 'verified') return 'success';
  if (status === 'excluded') return 'destructive';
  return 'warning';
}

/** Why a point lists PYQs to practise instead of an answer. */
export function practiceReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case 'image':
      return 'Image-based: practise it with the figure';
    case 'needs_options':
      return 'The answer only makes sense with the options';
    case 'provisional_hidden':
      return 'Answer hidden until its key is verified';
    default:
      return 'Practise these PYQs';
  }
}

/** Labels for the key-status reasons (questions/key_status.py) shown to admins. */
export const REASON_LABELS: Record<string, string> = {
  admin_verified: 'Verified by an admin',
  audit_verified: 'Verified by the answer-key audit',
  verification_stale: 'Key changed after the admin verification',
  audit_stale: 'Audit made for an older version',
  key_changed: 'Key was changed earlier',
  ai_solved_import: 'Key chosen by an AI importer',
  needs_review: 'Flagged needs review',
  audit_likely_correct: 'Audit: likely correct',
  audit_insufficient_evidence: 'Audit: insufficient evidence',
  recall_key: 'Recall question key',
  unverified: 'Not verified',
  no_key: 'No answer key',
  inactive: 'Inactive or dropped',
  scholarship: 'Scholarship question (never shown)',
  disputed: 'Disputed',
  controversial: 'Controversial',
  open_wrong_answer_report: 'Open wrong-answer report',
  label_hold: 'Answer label in the text (held)',
  label_key_conflict: 'Answer label disagrees with the key',
  image_context_missing: 'Needs a figure that is not attached',
  duplicate_key_conflict: 'A duplicate has another answer',
  audit_needs_review: 'Audit: needs review',
  audit_contradictory_sources: 'Audit: contradictory sources',
  audit_image_context_missing: 'Audit: figure missing',
  repeat_key_conflict: 'Repeated PYQs disagree on the answer',
  provisional_skipped: 'Left out (verified-only build)',
  over_cap: 'Over the point limit of one note',
};

export function reasonLabel(code: string | null | undefined): string {
  if (!code) return '';
  return REASON_LABELS[code] ?? code.replace(/_/g, ' ');
}

// ---------------------------------------------------------------------------- reading

export function practiceHref(questionId: number): string {
  return `/practice?id=${encodeURIComponent(String(questionId))}`;
}

/** True for a note the builder made (its points and sources come from the detail route). */
export function isBuiltNote(note: Pick<PublishedNote, 'builder_version'> | null | undefined): boolean {
  return Boolean(note && typeof note.builder_version === 'string' && note.builder_version.trim());
}

/** The sources of a point: per question when the build recorded them, else ids only. */
export function pointSources(point: Pick<NotePoint, 'sources' | 'question_ids' | 'key_status'>): NoteSource[] {
  if (Array.isArray(point.sources) && point.sources.length) return point.sources;
  return (point.question_ids ?? []).map((id) => ({ id, label: '', year: null, exam_type: '', key_status: point.key_status }));
}

/** 'CMS 2019 P1' -> 'CMS 2019 Paper 1' (screen readers read "P1" as a letter and a digit). */
export function spokenSittingLabel(label: string): string {
  return label.replace(/\bP([12])\b/, 'Paper $1');
}

export function sourceChipLabel(source: NoteSource): string {
  return source.label ? `${source.label}` : `Q${source.id}`;
}

/** "Asked 3× · CMS 2022 P2, NEET PG 2021" / "Asked in CMS 2019 P1". */
export function askedLine(point: Pick<NotePoint, 'frequency' | 'asked_in'>, max = 6): string {
  const labels = (point.asked_in ?? []).slice(0, max);
  const more = (point.asked_in ?? []).length > max ? ' …' : '';
  if (!labels.length) return '';
  return point.frequency > 1 ? `Asked ${point.frequency}× · ${labels.join(', ')}${more}` : `Asked in ${labels.join(', ')}${more}`;
}

/** The sections of a built note with their points, in order (points the viewer may not read are absent). */
export function sectionsWithPoints(note: Pick<PublishedNote, 'sections' | 'points'>): { section: NoteSection; points: NotePoint[] }[] {
  const byId = new Map((note.points ?? []).map((point) => [point.id, point]));
  const out: { section: NoteSection; points: NotePoint[] }[] = [];
  for (const section of note.sections ?? []) {
    const points = (section.points ?? []).map((id) => byId.get(id)).filter((p): p is NotePoint => Boolean(p));
    if (points.length) out.push({ section, points });
  }
  return out;
}

/** "12 PYQs · 3 verified, 9 provisional" for a built note; source count for a manual one. */
export function noteSummary(note: Pick<PublishedNote, 'builder_version' | 'verified_source_count' | 'provisional_source_count' | 'source_question_count' | 'counts'>): string {
  if (!isBuiltNote(note)) {
    return note.source_question_count > 0 ? `${note.source_question_count} source PYQs` : '';
  }
  const cited = note.counts?.cited ?? note.verified_source_count + note.provisional_source_count;
  return `${cited} PYQs · ${note.verified_source_count} verified, ${note.provisional_source_count} provisional`;
}

export function lockedTeaser(lockedPoints: number | null | undefined): string {
  const n = Number(lockedPoints) || 0;
  if (n <= 0) return '';
  return `${n} more point${n === 1 ? '' : 's'} with Premium`;
}

export function hiddenNotice(hiddenPoints: number | null | undefined): string {
  const n = Number(hiddenPoints) || 0;
  if (n <= 0) return '';
  return `${n} point${n === 1 ? ' is' : 's are'} hidden until this note is rebuilt: a source question changed since it was built.`;
}

/** True when the reader shows an unverified key anywhere in the note. */
export function hasProvisionalPoints(note: Pick<PublishedNote, 'points' | 'provisional_source_count'>): boolean {
  if (Array.isArray(note.points) && note.points.length) {
    return note.points.some((point) => point.kind === 'fact' && isProvisional(point.key_status));
  }
  return (note.provisional_source_count ?? 0) > 0;
}

/** Query parameters of the student list. */
export function noteListParams(filters: { exam?: string; subject?: string | number; topic?: string | number; q?: string; page?: number }): Record<string, string | number> {
  const params: Record<string, string | number> = { page: filters.page && filters.page > 0 ? filters.page : 1 };
  if (filters.exam) params.exam_type = filters.exam;
  if (filters.subject !== undefined && filters.subject !== '' && /^\d+$/.test(String(filters.subject))) params.subject = Number(filters.subject);
  if (filters.topic !== undefined && filters.topic !== '' && /^\d+$/.test(String(filters.topic))) params.topic = Number(filters.topic);
  const q = (filters.q ?? '').trim().replace(/\s+/g, ' ');
  if (q) params.q = q.slice(0, 80);
  return params;
}

export function facetTopics(facets: NoteFacets | null | undefined, subjectId: string | number | null | undefined) {
  if (!facets || subjectId === undefined || subjectId === null || subjectId === '') return [];
  return facets.subjects.find((subject) => String(subject.id) === String(subjectId))?.topics ?? [];
}

// ---------------------------------------------------------------------------- errors

interface AxiosLikeError {
  response?: { status?: number; data?: unknown };
  message?: string;
}

/** The builder routes answer 404 {code: 'feature_disabled'} while TOPIC_NOTES_BUILDER is off. */
export function isFeatureDisabled(err: unknown): boolean {
  const response = (err as AxiosLikeError)?.response;
  return response?.status === 404 && (response.data as { code?: string } | undefined)?.code === 'feature_disabled';
}

export function describeNotesError(err: unknown, fallback = 'Request failed.'): string {
  const response = (err as AxiosLikeError)?.response;
  if (isFeatureDisabled(err)) return 'The PYQ notes builder is switched off on this server (TOPIC_NOTES_BUILDER).';
  if (response?.status === 401) return 'Please sign in again.';
  if (response?.status === 403) return 'Admin access is needed.';
  if (response?.status === 429) return 'Too many requests. Wait a minute and try again.';
  const data = response?.data as Record<string, unknown> | undefined;
  if (data && typeof data === 'object') {
    for (const key of ['error', 'detail', 'message']) {
      if (typeof data[key] === 'string' && (data[key] as string).trim()) return (data[key] as string).trim().slice(0, 400);
    }
    const parts = Object.entries(data)
      .filter(([, value]) => typeof value === 'string' || Array.isArray(value))
      .map(([field, value]) => `${field}: ${Array.isArray(value) ? value.join(' ') : String(value)}`);
    if (parts.length) return parts.join(' · ').slice(0, 400);
  }
  return (err as AxiosLikeError)?.message || fallback;
}

// ---------------------------------------------------------------------------- admin builder

export type BuildScope = 'topic' | 'subject' | 'subject_topics';
export type BuildExam = 'cms' | 'neet_pg' | 'ini_cet' | 'each' | 'combined';
export type BuildMode = 'extractive' | 'llm' | 'auto';

export const BUILD_EXAMS: { value: BuildExam; label: string; hint: string }[] = [
  { value: 'cms', label: 'UPSC CMS', hint: 'CMS PYQs only.' },
  { value: 'neet_pg', label: 'NEET PG', hint: 'NEET PG PYQs only.' },
  { value: 'ini_cet', label: 'INI-CET', hint: 'INI-CET PYQs only.' },
  { value: 'each', label: 'Each exam separately', hint: 'One note per exam that has enough PYQs.' },
  { value: 'combined', label: 'Cross-exam (combined)', hint: 'One note from the PYQs of every exam (needs PYQs from two exams).' },
];

export const BUILD_MODES: { value: BuildMode; label: string; hint: string }[] = [
  { value: 'extractive', label: 'Extractive (no AI)', hint: 'Template facts from the PYQs; always available.' },
  { value: 'auto', label: 'Auto', hint: 'Tries a checked AI rewrite, keeps the extractive note when it fails the checks.' },
  { value: 'llm', label: 'AI rewrite', hint: 'Like Auto, but reports a fallback. Never available in offline mode.' },
];

export interface BuildForm {
  exam: BuildExam;
  subjectId: string;
  topicId: string;
  scope: BuildScope;
  mode: BuildMode;
  includeProvisional: boolean;
  verifiedOnly: boolean;
  minQuestions: number;
  force: boolean;
}

export const DEFAULT_BUILD_FORM: BuildForm = {
  exam: 'cms',
  subjectId: '',
  topicId: '',
  scope: 'topic',
  mode: 'extractive',
  includeProvisional: true,
  verifiedOnly: false,
  minQuestions: 3,
  force: false,
};

/** POST topic-notes/build/ body for the form, or an error for the form. */
export function buildPayload(form: BuildForm, dryRun: boolean): { body: Record<string, unknown> } | { error: string } {
  if (!/^\d+$/.test(form.subjectId)) return { error: 'Choose a subject.' };
  if (form.scope === 'topic' && !/^\d+$/.test(form.topicId)) return { error: 'Choose a topic, or build the whole subject.' };
  const min = Math.round(Number(form.minQuestions));
  if (!Number.isFinite(min) || min < 1 || min > 50) return { error: 'Minimum PYQs must be between 1 and 50.' };
  const body: Record<string, unknown> = {
    exam_type: form.exam === 'each' || form.exam === 'combined' ? 'all' : form.exam,
    combined: form.exam === 'combined',
    level: form.scope === 'subject' ? 'subject' : 'topic',
    subject: Number(form.subjectId),
    mode: form.mode,
    include_provisional: form.includeProvisional,
    verified_only: form.verifiedOnly,
    min_questions: min,
    force: form.force,
    dry_run: dryRun,
  };
  if (form.scope === 'topic') body.topic = Number(form.topicId);
  return { body };
}

export interface BuildReportRow {
  exam_type: string;
  is_combined: boolean;
  level: string;
  subject_id: number;
  subject: string;
  topic_id: number | null;
  topic: string;
  eligible_pyqs: number;
  note_id: number | null;
  action: 'create' | 'update' | 'unchanged' | 'skipped' | string;
  method: string;
  error: string;
  counts: Record<string, number>;
  warnings: string[];
  excluded_reasons?: Record<string, number>;
  counts_by_reason?: Record<string, number>;
  evidence_state?: string;
  preview?: { markdown: string };
}

export interface BuilderStatus {
  enabled: boolean;
  builder_version: string;
  ai_offline: boolean;
  evidence_state: string;
  async_threshold: number;
}

/** A row of the admin library (questions.serializers_notes.AdminTopicNoteSerializer). */
export interface LibraryNote {
  id: number;
  title: string;
  content: string;
  content_preview?: string;
  subject: number | null;
  topic: number | null;
  subject_name?: string;
  topic_name?: string;
  exam_type: string;
  is_combined: boolean;
  is_active?: boolean;
  ai_generated?: boolean;
  is_published?: boolean;
  source_question_ids?: number[];
  source_question_count?: number;
  generation_method?: string;
  builder_version?: string;
  built_at?: string | null;
  is_stale?: boolean;
  verified_source_count?: number;
  provisional_source_count?: number;
  excluded_source_count?: number;
  is_built?: boolean;
  build_counts?: Record<string, number>;
  excluded_reasons?: Record<string, number>;
  evidence_state?: string;
  created_at?: string;
  updated_at?: string;
}

/** A row of GET topic-notes/library/<id>/sources/ (admin). */
export interface NoteSourceRow {
  question: number;
  key_status: string;
  reason: string;
  cited: boolean;
  answer_at_build: string;
  current_key: string;
  is_active: boolean;
  changed_since_build: boolean;
  stem_preview: string;
  asked_in: string;
}

export interface BuildReport {
  builder_version: string;
  apply: boolean;
  mode: string;
  notes: BuildReportRow[];
  totals: Record<string, number>;
}

const ACTION_LABELS: Record<string, [string, string]> = {
  create: ['created', 'would be created'],
  update: ['updated', 'would be updated'],
  unchanged: ['unchanged', 'unchanged'],
  skipped: ['skipped', 'would be skipped'],
};

export function buildActionLabel(action: string, applied: boolean): string {
  const labels = ACTION_LABELS[action];
  return labels ? labels[applied ? 0 : 1] : action;
}

/** "2 notes created, 1 unchanged" (or "would be created" for a dry run). */
export function summarizeBuild(report: Pick<BuildReport, 'totals' | 'apply'>): string {
  const parts = Object.entries(report.totals ?? {})
    .filter(([, n]) => n > 0)
    .map(([action, n]) => `${n} note${n === 1 ? '' : 's'} ${buildActionLabel(action, report.apply)}`);
  return parts.length ? parts.join(', ') : 'Nothing to build.';
}

export function buildErrorLabel(code: string | null | undefined): string {
  if (code === 'not_enough_pyqs') return 'Not enough usable PYQs (see the reasons)';
  if (code === 'no_subject_or_topic') return 'No subject or topic';
  return code ? code.replace(/_/g, ' ') : '';
}

export function warningLabel(code: string): string {
  if (code === 'llm_skipped_offline_mode') return 'AI rewrite skipped: offline mode';
  if (code === 'llm_unavailable') return 'AI rewrite unavailable: extractive note kept';
  if (code === 'llm_fallback_extractive') return 'AI rewrite failed the checks: extractive note kept';
  if (code === 'llm_skipped_too_many_facts') return 'Too many facts for an AI rewrite: extractive note kept';
  if (code === 'llm_skipped_no_facts') return 'No facts to rewrite';
  if (code.startsWith('llm_validation_failed')) return `AI rewrite rejected ${code.slice('llm_validation_failed'.length).trim()}`;
  return code.replace(/_/g, ' ');
}

/** The warning mark of a provisional point (questions/notes_builder.py MARK). */
export const PROVISIONAL_MARK = '⚠';

export function countMarks(text: string | null | undefined): number {
  return (text ?? '').split(PROVISIONAL_MARK).length - 1;
}

/** Shown before an admin saves a hand edit of a note's content. */
export function contentEditWarning(
  note: { is_built?: boolean; builder_version?: string; content?: string },
  draft: string,
): string | null {
  const built = note.is_built ?? isBuiltNote({ builder_version: note.builder_version ?? '' });
  const notes: string[] = [];
  if (built && draft !== (note.content ?? '')) {
    notes.push('Saving turns this built note into a manual note: students then read your text as written, the free plan only '
      + 'sees it when every source PYQ is free, and a rebuild replaces it.');
  }
  const lost = countMarks(note.content) - countMarks(draft);
  if (lost > 0) {
    notes.push(`${lost} ${PROVISIONAL_MARK} mark${lost === 1 ? '' : 's'} removed: keep the mark on every point whose key is not verified.`);
  }
  return notes.length ? notes.join(' ') : null;
}
