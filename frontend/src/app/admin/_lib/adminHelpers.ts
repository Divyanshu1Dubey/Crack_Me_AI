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

// ── Drag-to-reorder display numbers (questions editor) ─────────────────────

export interface ReorderRow {
  id: number;
  display_number?: number | null;
  paper?: number | null;
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
  const numbers = group.map((row) => row.display_number);
  if (numbers.some((n) => typeof n !== 'number' || !Number.isFinite(n))) {
    return {
      ok: false,
      reason: 'Some questions of this paper have no display number yet. Set them in the number field first.',
    };
  }
  const sortedNumbers = (numbers as number[]).slice().sort((a, b) => a - b);
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
 * Fields the question detail serializer may not round-trip yet. If one of
 * them was edited but is missing from the PATCH response, the server
 * silently dropped it and the editor tells the admin instead of reporting a
 * clean save.
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
 * - `is_controversial` is only sent when the admin toggled it: neither list
 *   nor detail serializer returns it, so the checkbox can start unchecked for
 *   a controversial question and must not clear the flag on every save.
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
