/**
 * Pure helpers shared by the admin pages (no React, no API client imports,
 * so they can be unit-tested with `node --test`; see
 * frontend/tests/unit/admin-helpers.test.ts).
 *
 * `_lib` is a Next.js private folder: nothing in here is routable.
 */

// ── DRF pagination ──────────────────────────────────────────────────────────
//
// settings.py sets PageNumberPagination with PAGE_SIZE=20 for every list
// endpoint, so a single GET of /questions/subjects/ or /questions/topics/
// only returns the first 20 rows. Admin pickers and lists walk the pages
// instead (incrementing ?page while the payload has a `next` link, the same
// way ExamQuestionBank loads subjects). We ask for page_size=100; a backend
// that ignores page_size still works, it just takes more pages.

/** Page size requested from paginated admin list endpoints. */
export const ADMIN_PAGE_SIZE = 100;

/** Hard stop so a misbehaving `next` pointer can't loop forever. */
export const MAX_LIST_PAGES = 50;

/** Rows of a DRF list payload: a paginated `{results}` object or a bare array. */
export function listRows<T = any>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  const results = (payload as { results?: unknown } | null | undefined)?.results;
  return Array.isArray(results) ? (results as T[]) : [];
}

/** True when a paginated payload says there is another page. */
export function hasNextPage(payload: unknown): boolean {
  if (!payload || Array.isArray(payload)) return false;
  return Boolean((payload as { next?: unknown }).next);
}

/** Total row count of a paginated payload (falls back to the rows present). */
export function listCount(payload: unknown): number {
  if (payload && !Array.isArray(payload)) {
    const count = Number((payload as { count?: unknown }).count);
    if (Number.isFinite(count) && count >= 0) return count;
  }
  return listRows(payload).length;
}

/**
 * Fetch every page of a paginated DRF list endpoint.
 *
 * `fetchPage(page)` must resolve to the response payload (axios `res.data`).
 * Stops when the payload has no `next` link, a page comes back empty, the
 * endpoint is not paginated (bare array), or `maxPages` is reached.
 */
export async function fetchAllPages<T = any>(
  fetchPage: (page: number) => Promise<unknown>,
  maxPages: number = MAX_LIST_PAGES,
): Promise<T[]> {
  const rows: T[] = [];
  for (let page = 1; page <= maxPages; page += 1) {
    const payload = await fetchPage(page);
    const pageRows = listRows<T>(payload);
    rows.push(...pageRows);
    if (Array.isArray(payload) || pageRows.length === 0 || !hasNextPage(payload)) break;
  }
  return rows;
}

/**
 * Admin-facing copy for a failed request, keyed on the HTTP status of an
 * axios error (`what` names the data, e.g. "import jobs"). Raw axios text
 * ("Request failed with status code 500") is never shown.
 */
export function loadErrorMessage(error: unknown, what: string): string {
  const status = Number((error as { response?: { status?: unknown } } | null | undefined)?.response?.status);
  if (status === 429) return 'Too many requests. Try again in a minute.';
  if (status === 401 || status === 403) return `You do not have access to ${what}.`;
  if (status >= 500) return `Couldn't load ${what} (server error).`;
  if (!Number.isFinite(status) || status <= 0) return `Couldn't load ${what}. Check your connection and retry.`;
  return `Couldn't load ${what}.`;
}

// ── Numbers ─────────────────────────────────────────────────────────────────

/** A count with thousands separators (en-IN, like the rest of the admin UI); '0' when missing. */
export function formatCount(value: unknown): string {
  if (value === null || value === undefined || value === '') return '0';
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString('en-IN') : '0';
}

/** `part` as a percentage of `total`, clamped to 0-100; 0 when the total is missing or zero. */
export function percentOf(part: unknown, total: unknown): number {
  const p = Number(part);
  const t = Number(total);
  if (!Number.isFinite(p) || !Number.isFinite(t) || t <= 0) return 0;
  return Math.min(100, Math.max(0, (p / t) * 100));
}

// ── Tests tab ───────────────────────────────────────────────────────────────

/**
 * Which tests the admin Tests tab lists. GET /tests/ returns every test to an
 * admin, newest first, so the library was buried under students' generated
 * practice tests and only the first page (20) was shown.
 *  - library: the published official library (?scope=library)
 *  - drafts:  the admin's own unpublished tests, e.g. manual drafts
 *  - all:     everything, including students' practice tests
 */
export type AdminTestScope = 'library' | 'drafts' | 'all';

export function adminTestListParams(scope: AdminTestScope, page: number): Record<string, string> {
  const params: Record<string, string> = { page: String(Math.max(1, Math.floor(page) || 1)) };
  if (scope === 'library') params.scope = 'library';
  if (scope === 'drafts') {
    params.scope = 'mine';
    params.is_published = 'false';
  }
  return params;
}

// ── Stale responses ─────────────────────────────────────────────────────────

/**
 * Ticket counter for a list that can be requested again while an older
 * request is still in flight (the admin switches the Tests scope, or
 * switches after "Load more"). Each request takes a ticket with `next()`;
 * when its response arrives, `isCurrent(ticket)` says whether it is still
 * the latest request. Superseded responses are dropped: they used to replace
 * (page 1) or extend (Load more) the rows of the newer scope.
 */
export interface RequestSequence {
  next(): number;
  isCurrent(ticket: number): boolean;
}

export function createRequestSequence(): RequestSequence {
  let current = 0;
  return {
    next: () => {
      current += 1;
      return current;
    },
    isCurrent: (ticket: number) => ticket === current,
  };
}

// ── Related PYQ ids (Question.similar_questions) ───────────────────────────

/** Parse "12, 45,90" into [12, 45, 90]; ignores anything that isn't a positive integer. */
export function parseRelatedIds(value: string): number[] {
  return String(value || '')
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((id) => Number.isInteger(id) && id > 0);
}

/** Order- and duplicate-insensitive id comparison. */
export function sameIdSet(a: number[], b: number[]): boolean {
  const left = new Set(a);
  const right = new Set(b);
  if (left.size !== right.size) return false;
  for (const id of left) {
    if (!right.has(id)) return false;
  }
  return true;
}

/** GET /questions/<id>/similar/ returns at most this many rows (views.py LIMIT). */
export const SIMILAR_ENDPOINT_LIMIT = 8;

/** Ids of the admin-curated (`similarity_reason === 'curated'`) rows of a /similar/ response. */
export function curatedRelatedIds(similarRows: unknown): number[] {
  return listRows<{ id?: unknown; similarity_reason?: unknown }>(similarRows)
    .filter((row) => row && row.similarity_reason === 'curated')
    .map((row) => Number(row.id))
    .filter((id) => Number.isInteger(id) && id > 0);
}

// ── Question fields ─────────────────────────────────────────────────────────

const ANSWER_LETTERS = ['A', 'B', 'C', 'D'];

/** True for a usable correct-answer letter (Question.correct_answer choices). */
export function isValidAnswerLetter(value: unknown): boolean {
  return ANSWER_LETTERS.includes(String(value ?? '').trim().toUpperCase());
}

/**
 * Question.concept_keywords is a JSON list. The editor shows it as a
 * comma-separated string; convert back to a list before saving so consumers
 * that expect an array (keyword chips, video focus terms) keep working.
 */
export function parseConceptKeywords(value: unknown): string[] {
  const parts = Array.isArray(value) ? value.map((v) => String(v ?? '')) : String(value ?? '').split(',');
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of parts) {
    const keyword = part.trim();
    if (!keyword || seen.has(keyword)) continue;
    seen.add(keyword);
    out.push(keyword);
  }
  return out;
}

/**
 * Query params for the admin question search box. A bare number (or "Q123" /
 * "#123") is an id lookup and is sent as `question_id` only: the backend ANDs
 * `question_id` with the `search` text filter, so sending both only matched
 * questions whose text happened to contain the number.
 */
export function questionSearchParams(term: string): Record<string, string | number> {
  const trimmed = String(term || '').trim();
  if (!trimmed) return {};
  const idMatch = trimmed.match(/^(?:q|#)?\s*(\d+)$/i);
  if (idMatch) return { question_id: Number(idMatch[1]) };
  return { search: trimmed };
}

/** The remove-from-bank dialog asks for "Q123"; accept "Q123", "q123" or "123". */
export function matchesQuestionConfirm(input: string, questionId: number | string): boolean {
  const typed = String(input || '').trim().replace(/^q/i, '');
  return typed !== '' && typed === String(questionId);
}

// ── Destructive platform-wide actions ───────────────────────────────────────

/** Phrase an admin must type before a platform-wide (scope=all) system action. */
export const PLATFORM_WIDE_CONFIRM_PHRASE = 'RESET ALL';

export function isPlatformWideConfirmed(text: string): boolean {
  return String(text || '').trim() === PLATFORM_WIDE_CONFIRM_PHRASE;
}

export interface SystemActionPayload {
  scope: 'all' | 'user';
  user_id?: number;
  confirm?: string;
}

export type SystemActionRequest =
  | { ok: true; payload: SystemActionPayload; target: string }
  | { ok: false; message: string };

/**
 * Body of a reset-attempts / clear-analytics / rerun-evaluation call.
 * scope 'user' needs a positive user id. scope 'all' needs the typed phrase,
 * and the phrase the admin typed is sent as `confirm`: the backend requires
 * confirm === 'RESET ALL' for every platform-wide call, and callers pass it
 * themselves (api.ts no longer supplies a default).
 */
export function buildSystemActionRequest(
  scope: 'all' | 'user',
  userIdText: string,
  confirmText: string,
): SystemActionRequest {
  if (scope === 'user') {
    const raw = String(userIdText ?? '').trim();
    const id = raw === '' ? Number.NaN : Number(raw);
    if (!Number.isInteger(id) || id <= 0) {
      return { ok: false, message: 'Enter the user ID for a single-user action.' };
    }
    return { ok: true, payload: { scope: 'user', user_id: id }, target: `user #${id}` };
  }
  if (!isPlatformWideConfirmed(confirmText)) {
    return { ok: false, message: `Type ${PLATFORM_WIDE_CONFIRM_PHRASE} to run a platform-wide action.` };
  }
  return {
    ok: true,
    payload: { scope: 'all', confirm: String(confirmText).trim() },
    target: 'ALL USERS (platform-wide)',
  };
}

/**
 * The sentence a failed admin request carries in `error` (then `detail`,
 * then `message`), or null when it has none. The system, backup and restore
 * endpoints answer {error, code}, e.g. 503 {code: 'backup_not_configured'}
 * when a production deployment has no CORE_DATA_BACKUP_PATH, or 400
 * {code: 'confirmation_required'}. extractApiErrorMessage joins every string
 * value, so the admin read the sentence with ", backup_not_configured"
 * appended. Callers fall back to extractApiErrorMessage for other payloads
 * (HTML error pages, field errors).
 */
export function apiErrorSentence(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  const data = payload as Record<string, unknown>;
  for (const key of ['error', 'detail', 'message']) {
    const value = data[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

// ── Year options ────────────────────────────────────────────────────────────

/**
 * Year filter options: the years the bank actually has (GET /questions/years/),
 * newest first. Falls back to the last 30 years up to the current one so new
 * papers (e.g. 2026) are never missing from the list.
 */
export function buildYearOptions(apiYears: unknown, now: Date = new Date()): number[] {
  const fromApi = listRows<unknown>(apiYears)
    .map((y) => Number(y))
    .filter((y) => Number.isInteger(y) && y > 1900 && y < 3000);
  const unique = Array.from(new Set(fromApi)).sort((a, b) => b - a);
  if (unique.length > 0) return unique;
  const current = now.getFullYear();
  return Array.from({ length: 30 }, (_, i) => current - i);
}

// ── Questions editor list query ────────────────────────────────────────────

export interface QuestionEditorFilters {
  needsReview?: boolean;
  isDropped?: boolean;
  examType?: string;
  year?: string;
  subjectId?: string;
  topicId?: string;
  difficulty?: string;
  isControversial?: boolean;
  isImageBased?: boolean;
  /** Only the scholarship challenge's questions (an admin-only filter on the backend). */
  inScholarshipPool?: boolean;
  search?: string;
}

/**
 * Drag-to-reorder rewrites student-facing display numbers, which are scoped
 * by exam/year/paper, so it is only offered when the list is narrowed to one
 * exam and one year with no other filter: a drag then renumbers questions of
 * a single paper instead of an arbitrary mix of papers and years.
 */
export function isReorderMode(filters: QuestionEditorFilters): boolean {
  const f = filters || {};
  return (
    !!f.examType && !!f.year && !f.search && !f.subjectId && !f.topicId && !f.difficulty &&
    !f.needsReview && !f.isDropped && !f.isControversial && !f.isImageBased && !f.inScholarshipPool
  );
}

/**
 * GET /questions/ params of the questions editor list.
 *
 * In reorder mode every page must be a contiguous slice of a paper in
 * display order, so it sends `ordering=paper,display_number,id` (the id
 * breaks ties: rows with equal keys could otherwise move across page
 * boundaries between requests) and `is_active=true` (removed questions are
 * hidden from students and take no part in the numbering; admins otherwise
 * list every row). Other views keep the default newest-first order instead
 * of mixing every paper's #1 together.
 */
export function questionEditorListParams(
  filters: QuestionEditorFilters,
  page: number,
  pageSize: number,
): Record<string, string | number> {
  const f = filters || {};
  const params: Record<string, string | number> = {
    page: Math.max(1, Math.floor(page) || 1),
    page_size: pageSize,
  };
  const reorder = isReorderMode(f);
  if (reorder) params.ordering = 'paper,display_number,id';
  if (f.needsReview) params.needs_review = 'true';
  if (f.isDropped) params.is_dropped = 'true';
  if (f.examType) params.exam_type = f.examType;
  if (f.year) params.year = f.year;
  if (f.subjectId) params.subject = f.subjectId;
  if (f.topicId) params.topic = f.topicId;
  if (f.difficulty) params.difficulty = f.difficulty;
  if (f.isControversial) params.is_controversial = 'true';
  if (f.isImageBased) params.is_image_based = 'true';
  if (f.inScholarshipPool) params.is_scholarship_eligible = 'true';
  if (f.search) params.search = f.search;
  if (reorder) params.is_active = 'true';
  return params;
}

// ── Scholarship challenge toggle (questions editor) ────────────────────────

/**
 * Message for a failed PATCH /questions/<id>/scholarship/: the server's reason when it refused the
 * question (400 scholarship_refused: a figure, the free showcase, no key ...), else a generic one.
 */
export function scholarshipToggleError(err: unknown): string {
  const data = (err as { response?: { data?: { detail?: unknown; error?: unknown } } } | null)?.response?.data;
  if (data && typeof data.detail === 'string' && data.detail.trim()) return data.detail;
  if (data && typeof data.error === 'string' && data.error.trim()) return data.error;
  return 'The scholarship setting could not be saved. Please try again.';
}

// ── Drag-to-reorder display numbers (questions editor) ─────────────────────

export interface ReorderRow {
  id: number;
  display_number?: number | null;
  paper?: number | null;
  /**
   * Removed questions (is_active=false) are not shown to students. The
   * reorder list asks for is_active=true (questionEditorListParams); rows
   * that still say false are refused below.
   */
  is_active?: boolean | null;
}

export type RenumberResult<T extends ReorderRow> =
  | { ok: true; rows: T[]; changes: { id: number; display_number: number }[] }
  | { ok: false; reason: string };

/**
 * Move `rows[fromIdx]` to `toIdx` and renumber within the dragged row's paper.
 *
 * display_number is "Number shown to students (scoped by year/paper)", so the
 * rows of that paper keep the *same set* of display numbers they already had;
 * the numbers are just re-assigned in the new visual order. Only rows whose
 * number actually changes are returned in `changes`. Rows of other papers
 * are left untouched, and a drop across papers is refused.
 *
 * The page may only show part of a paper (other pages, other filters), so the
 * paper's visible numbers must form one unbroken run (e.g. 41..60). With a
 * gap (10, 49, 50, 98) other questions sit between them, and dragging #98 to
 * the top would make it #10 and push the old #10 to #49, past 38 questions
 * the admin never saw; that is refused. Removed (inactive) rows are refused
 * too: students never see them, so they must not take part in the numbering.
 * (The list request already leaves them out with is_active=true; this check
 * covers rows that carry is_active=false anyway. Rows without the field are
 * treated as active.)
 */
export function computeDisplayRenumber<T extends ReorderRow>(
  rows: T[],
  fromIdx: number,
  toIdx: number,
): RenumberResult<T> {
  if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0 || fromIdx >= rows.length || toIdx >= rows.length) {
    return { ok: true, rows, changes: [] };
  }
  const paperOf = (row: T) => Number(row.paper ?? 0) || 0;
  const dragged = rows[fromIdx];
  const target = rows[toIdx];
  if (paperOf(dragged) !== paperOf(target)) {
    return { ok: false, reason: 'Drag-reorder only works between questions of the same paper.' };
  }
  const paper = paperOf(dragged);
  const reordered = [...rows];
  reordered.splice(fromIdx, 1);
  reordered.splice(toIdx, 0, dragged);

  const group = reordered.filter((row) => paperOf(row) === paper);
  if (group.some((row) => row.is_active === false)) {
    return {
      ok: false,
      reason: 'Removed questions of this paper are listed here. Only active questions can be drag-renumbered; reload the list and try again.',
    };
  }
  const numbers = group.map((row) => row.display_number);
  if (numbers.some((n) => typeof n !== 'number' || !Number.isFinite(n))) {
    return {
      ok: false,
      reason: 'Some questions of this paper have no display number yet. Set them in the number field first.',
    };
  }
  const sortedNumbers = (numbers as number[]).slice().sort((a, b) => a - b);
  const lowest = sortedNumbers[0];
  const highest = sortedNumbers[sortedNumbers.length - 1];
  const isUnbrokenRun =
    new Set(sortedNumbers).size === sortedNumbers.length && highest - lowest + 1 === sortedNumbers.length;
  if (!isUnbrokenRun) {
    return {
      ok: false,
      reason:
        `The numbers shown for this paper (${lowest}-${highest}) skip or repeat values, so other questions of ` +
        'the paper may sit between them. Drag-reorder needs an unbroken run of numbers; use the number field instead.',
    };
  }
  const assigned = new Map<number, number>();
  group.forEach((row, idx) => assigned.set(row.id, sortedNumbers[idx]));

  const changes: { id: number; display_number: number }[] = [];
  const nextRows = reordered.map((row) => {
    if (!assigned.has(row.id)) return row;
    const number = assigned.get(row.id) as number;
    if (number === row.display_number) return row;
    changes.push({ id: row.id, display_number: number });
    return { ...row, display_number: number };
  });
  return { ok: true, rows: nextRows, changes };
}

// ── Question edit modal payload ─────────────────────────────────────────────

/**
 * Fields older question serializers did not round-trip (the detail and
 * admin-list serializers now return all of them). If one of them was edited
 * but is missing from the PATCH response, the server silently dropped it and
 * the editor tells the admin instead of reporting a clean save.
 */
export const SERVER_OPTIONAL_EDIT_FIELDS = [
  'why_correct',
  'why_wrong_a',
  'why_wrong_b',
  'why_wrong_c',
  'why_wrong_d',
  'is_controversial',
] as const;

/**
 * PATCH body for the question edit modal.
 *
 * - `concept_keywords` is sent as a list (the model field is a JSON list).
 * - `correct_answer` is only sent when it is a real letter: the model field
 *   has no blank choice, and defaulting an unset answer to "A" asserted a
 *   wrong key.
 * - `is_controversial` is only sent when the admin toggled it: a row from a
 *   serializer without the field starts the checkbox unchecked, and the save
 *   must not clear a real flag then (the admin-list and detail serializers
 *   now return it, so the checkbox normally starts from the real value).
 */
export function buildQuestionEditPayload(
  form: Record<string, unknown>,
  baseline: Record<string, unknown>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...form, admin_edited: true };
  payload.concept_keywords = parseConceptKeywords(form.concept_keywords);
  if (isValidAnswerLetter(form.correct_answer)) {
    payload.correct_answer = String(form.correct_answer).trim().toUpperCase();
  } else {
    delete payload.correct_answer;
  }
  if (Boolean(form.is_controversial) === Boolean(baseline.is_controversial)) {
    delete payload.is_controversial;
  }
  return payload;
}

/** Edited SERVER_OPTIONAL_EDIT_FIELDS that the save response does not contain. */
export function unpersistedEditFields(
  payload: Record<string, unknown>,
  baseline: Record<string, unknown>,
  response: unknown,
): string[] {
  const data = response && typeof response === 'object' ? (response as Record<string, unknown>) : {};
  return SERVER_OPTIONAL_EDIT_FIELDS.filter(
    (field) => field in payload && payload[field] !== baseline[field] && !(field in data),
  );
}

/**
 * Apply a generate-explanation response to the edit form.
 *
 * Dry-run output (`saved` false) becomes unsaved edits: the form changes and
 * the baseline does not, so Save PATCHes the generated fields (and Cancel
 * drops them). Output the server already stored (`saved` true) goes into the
 * baseline too, with the answer the generation was told is correct. Keys the
 * form does not have are ignored; concept_keywords lists become the form's
 * comma-separated text.
 */
export function mergeGeneratedFields<F extends Record<string, unknown>>(
  form: F,
  baseline: F,
  response: unknown,
  correctAnswer: string,
): { form: F; baseline: F; applied: string[]; saved: boolean } {
  const data = response && typeof response === 'object' ? (response as Record<string, unknown>) : {};
  const generated =
    data.generated_fields && typeof data.generated_fields === 'object'
      ? (data.generated_fields as Record<string, unknown>)
      : {};
  const saved = data.saved === true;
  const nextForm: Record<string, unknown> = { ...form };
  const nextBaseline: Record<string, unknown> = { ...baseline };
  const applied: string[] = [];
  for (const [key, value] of Object.entries(generated)) {
    if (!(key in nextForm)) continue;
    const formValue = key === 'concept_keywords' && Array.isArray(value) ? value.join(', ') : value;
    nextForm[key] = formValue;
    if (saved) nextBaseline[key] = formValue;
    applied.push(key);
  }
  if (!saved) return { form: nextForm as F, baseline, applied, saved };
  nextBaseline.correct_answer = correctAnswer;
  return { form: nextForm as F, baseline: nextBaseline as F, applied, saved };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

/** Admin copy when saved AI output removed a question's "Verified by Admin" mark. */
export const VERIFICATION_CLEARED_NOTE = '"Verified by Admin" was removed - review the new text and verify again.';

/**
 * Result line of the Questions list "AI Explain" action
 * (POST /questions/<id>/generate-explanation/, not a dry run).
 *
 * The endpoint never marks a question verified, and when it stores new
 * content for a verified question it removes the mark and returns
 * `verification_cleared: true` (the line used to say the question kept its
 * earlier mark). `detail` is the server's own summary. A question that is
 * still verified afterwards (the stored text did not change, or a server
 * without `verification_cleared`) is named as such: the returned row decides,
 * and `wasVerified` (the list row) only when the response has no row.
 */
export function aiExplainResultMessage(questionId: number, response: unknown, wasVerified: boolean): string {
  const data = asRecord(response);
  const label = `Q#${questionId}`;
  if (data.saved === false) {
    return `AI explanation generated for ${label} but not saved. Open the question in the editor to review and save it.`;
  }
  if (data.verification_cleared === true) {
    return `AI explanation generated and saved for ${label}. ${VERIFICATION_CLEARED_NOTE}`;
  }
  const row = asRecord(data.question);
  const stillVerified = typeof row.is_verified_by_admin === 'boolean' ? row.is_verified_by_admin : wasVerified;
  if (stillVerified) {
    return `AI explanation generated and saved for ${label}. It is still marked "Verified by Admin": review the text, and use Unverify if it needs work.`;
  }
  const detail = typeof data.detail === 'string' && data.detail.trim()
    ? data.detail.trim()
    : 'AI explanation generated and saved (not marked verified).';
  return `${label}: ${detail} Review it, then use Verify once it is correct.`;
}

/**
 * Result line of the Questions list "Regenerate AI" action
 * (POST /questions/<id>/force-regenerate/). New AI text there also removes
 * an earlier "Verified by Admin" mark (`verification_cleared: true`), and the
 * list dropped the badge without a word. Null when there is nothing to
 * report: a plain success stays silent, as before.
 */
export function regenerateResultMessage(questionId: number, response: unknown): string | null {
  return asRecord(response).verification_cleared === true
    ? `AI regeneration completed for Q#${questionId}. ${VERIFICATION_CLEARED_NOTE}`
    : null;
}

// ── Campaigns / announcements (Admin > Broadcast, /admin/announcements) ────

/** The Announcement fields these helpers read (AnnouncementSerializer). */
export interface CampaignRow {
  id?: number | string;
  title?: string | null;
  delivery_status?: string | null;
  delivery_count?: number | null;
  is_active?: boolean | null;
  is_expired?: boolean | null;
  expires_at?: string | null;
  scheduled_for?: string | null;
}

function timeOf(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const t = new Date(String(value)).getTime();
  return Number.isFinite(t) ? t : null;
}

/**
 * Past its expiry: the serializer's `is_expired`, re-checked against `now`
 * because a list loaded a while ago can hold rows that expired since.
 */
export function campaignIsExpired(row: CampaignRow | null | undefined, now: Date = new Date()): boolean {
  if (!row) return false;
  if (row.is_expired === true) return true;
  const expires = timeOf(row.expires_at);
  return expires !== null && expires <= now.getTime();
}

/**
 * True when students see the campaign right now. Mirrors
 * analytics.views._live_announcements: sent, active, not expired and not
 * scheduled for later. (A sent row used to count as live even when it had
 * expired, so it showed no publish button and "Publish again" claimed it was
 * live while students saw nothing.)
 */
export function campaignIsLive(row: CampaignRow | null | undefined, now: Date = new Date()): boolean {
  if (!row || row.delivery_status !== 'sent' || row.is_active === false) return false;
  if (campaignIsExpired(row, now)) return false;
  const scheduled = timeOf(row.scheduled_for);
  return scheduled === null || scheduled <= now.getTime();
}

export type AnnouncementStatus = 'live' | 'scheduled' | 'draft' | 'inactive' | 'expired' | 'failed';

/** One status per announcement row for the admin lists ('live' = what students see now). */
export function announcementStatus(row: CampaignRow | null | undefined, now: Date = new Date()): AnnouncementStatus {
  if (campaignIsLive(row, now)) return 'live';
  if (row?.is_active === false) return 'inactive';
  if (campaignIsExpired(row, now)) return 'expired';
  const status = String(row?.delivery_status || 'draft');
  if (status === 'failed') return 'failed';
  // 'sent' but not live while active and unexpired: its scheduled time is ahead.
  if (status === 'scheduled' || status === 'sent') return 'scheduled';
  return 'draft';
}

export interface CampaignNotice {
  type: 'ok' | 'warn';
  text: string;
}

/**
 * Message after "Publish now" (POST /analytics/admin/campaigns/<id>/send-now/).
 * The endpoint marks the row sent and active, moves a future scheduled time
 * to now, and refuses an expired row (400 code 'expired', see
 * campaignPublishErrorNotice). The expired and scheduled-later branches below
 * are therefore only defensive (browser and server clocks can disagree);
 * "is live" is still only claimed when the returned row is live.
 */
export function campaignPublishNotice(
  updated: CampaignRow | null | undefined,
  id: number,
  now: Date = new Date(),
  formatDate: (date: Date) => string = (date) => date.toLocaleString(),
): CampaignNotice {
  const title = `"${updated?.title || `Campaign #${id}`}"`;
  const audience = `${formatCount(updated?.delivery_count)} users`;
  if (campaignIsExpired(updated, now)) {
    const expires = timeOf(updated?.expires_at);
    const when = expires !== null ? ` on ${formatDate(new Date(expires))}` : '';
    return {
      type: 'warn',
      text: `${title} is marked published, but it expired${when}, so students still do not see it. ` +
        'Set a later expiry in Admin > Announcements to show it again.',
    };
  }
  const scheduled = timeOf(updated?.scheduled_for);
  if (scheduled !== null && scheduled > now.getTime()) {
    return {
      type: 'warn',
      text: `${title} is published in-app for ${audience}, but students only see it from ` +
        `${formatDate(new Date(scheduled))} (its scheduled time).`,
    };
  }
  if (!campaignIsLive(updated, now)) {
    return { type: 'warn', text: `${title} was published, but it is not live yet. Refresh the list to check its status.` };
  }
  return { type: 'ok', text: `${title} is live in-app for ${audience}.` };
}

/**
 * Message when "Publish now" is refused because the campaign has expired, or
 * null for any other failure (the page then shows extractApiErrorMessage).
 * send-now answers an expired row with 400 {error, code: 'expired'};
 * extractApiErrorMessage joins every string value, so the admin read the
 * server sentence with ", expired" appended. The list hides the publish
 * button on rows it knows are expired, so this answer means the list was
 * stale (the row expired after it loaded, or its expiry changed elsewhere).
 */
export function campaignPublishErrorNotice(payload: unknown, id: number): CampaignNotice | null {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  if ((payload as { code?: unknown }).code !== 'expired') return null;
  return {
    type: 'warn',
    text: `Could not publish campaign #${id}: it has expired, so students would not see it. ` +
      'Set a later expiry in Admin > Announcements, then publish it.',
  };
}

/** `<input type="datetime-local">` value (local time, to the minute) of a timestamp; '' when missing or invalid. */
export function toDateTimeLocalValue(value: unknown): string {
  const t = timeOf(value);
  if (t === null) return '';
  const d = new Date(t);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * New expiry typed into a datetime-local field (local time) as an ISO
 * timestamp. It must lie in the future: a past expiry hides the
 * announcement (Deactivate does that explicitly).
 */
export function parseExpiryInput(
  value: string,
  now: Date = new Date(),
): { ok: true; iso: string } | { ok: false; message: string } {
  const raw = String(value || '').trim();
  if (!raw) return { ok: false, message: 'Pick a new expiry date and time, or remove the expiry.' };
  const t = new Date(raw).getTime();
  if (!Number.isFinite(t)) return { ok: false, message: 'Expiry date is not valid.' };
  if (t <= now.getTime()) {
    return { ok: false, message: 'Pick a time in the future: an expiry in the past hides the announcement.' };
  }
  return { ok: true, iso: new Date(t).toISOString() };
}
