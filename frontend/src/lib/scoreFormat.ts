/**
 * A score or a mark total for display: at most two decimals ("0.34", "2", "1.67"), "–" when missing.
 * Test scores carry negative marking (-0.33 per wrong answer), so the raw float can read 0.33999999999999997.
 *
 * Keep this file free of imports (it is unit-tested directly with Node).
 */
export function formatMarks(value: unknown): string {
    if (value === null || value === undefined || value === '') return '–';
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return '–';
    const rounded = Math.round(n * 100) / 100;
    return String(Object.is(rounded, -0) ? 0 : rounded);
}

/** A reviewed answer of a test attempt, as far as "not scored" goes (GET /api/tests/<id>/review/ rows). */
export interface NotScoredRow {
    dropped_by_upsc?: unknown;
    no_answer_key?: unknown;
    selected_answer?: unknown;
}

/**
 * The review banner of a question the attempt's score leaves out (backend: tests_engine/scoring.py
 * not_scored_reason): UPSC dropped it from evaluation, or it has no answer key, so no answer is right or wrong.
 */
export function notScoredLabel(row: NotScoredRow | null | undefined): string {
    const reason = row?.dropped_by_upsc
        ? 'UPSC dropped this question from evaluation'
        : row?.no_answer_key ? 'this question has no answer key yet' : '';
    const answer = typeof row?.selected_answer === 'string' && row.selected_answer
        ? ` (your answer: ${row.selected_answer})` : '';
    return `Not scored${reason ? ` — ${reason}` : ''}${answer}`;
}

/** The results-screen note for the questions an attempt does not score ('' when there are none). */
export function notScoredNote(count: unknown): string {
    const n = Number(count);
    if (!Number.isFinite(n) || n <= 0) return '';
    const one = n === 1;
    return `${n} question${one ? '' : 's'} ${one ? 'is' : 'are'} not part of the score `
        + '(dropped by UPSC from evaluation, or no answer key yet).';
}
