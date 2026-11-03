/**
 * Pure helpers for the /neet-pg landing (NeetPgLanding.tsx), kept free of
 * JSX and imports so they can be unit-tested directly with Node.
 *
 * Both work on GET /api/questions/stats/?exam_source=NEET PG, whose
 * by_subject rows ({id, name, code, count, solved}) and by_year rows
 * ({year, count, solved}) are already scoped to NEET PG questions.
 */

export interface SubjectStat { id: number; name: string; code: string; count: number; solved: number }
export interface YearStat { year: number; count: number; solved: number }

/** A year tile promises "the paper"; years with only a handful of recalls are not one. */
export const MIN_QUESTIONS_PER_YEAR_TILE = 50;

/** Loader / placeholder buckets that are not PG subjects. */
const PLACEHOLDER_SUBJECT_CODES = new Set(['IMPORTED']);
const PLACEHOLDER_SUBJECT_NAMES = new Set(['Expert Curated', 'Imported']);

/** NEET PG subjects that have questions, biggest first. */
export function pgSubjectsFromStats(bySubject: SubjectStat[] | null | undefined): SubjectStat[] {
    return (bySubject ?? [])
        .filter((s) => s.count > 0 && !PLACEHOLDER_SUBJECT_CODES.has(s.code) && !PLACEHOLDER_SUBJECT_NAMES.has(s.name))
        .sort((a, b) => b.count - a.count);
}

/** Year tiles worth offering as a paper (real years with enough questions), newest first. */
export function yearTilesFromStats(byYear: YearStat[] | null | undefined): YearStat[] {
    return (byYear ?? [])
        .filter((y) => y.year > 0 && y.count >= MIN_QUESTIONS_PER_YEAR_TILE)
        .sort((a, b) => b.year - a.year);
}

/** "2018–2025", "2025", or "" — the span the year tiles actually cover. */
export function yearSpanLabel(tiles: YearStat[]): string {
    if (tiles.length === 0) return '';
    const years = tiles.map((t) => t.year);
    const min = Math.min(...years);
    const max = Math.max(...years);
    return min === max ? String(max) : `${min}–${max}`;
}

/** "1 Q" / "12 Qs". */
export function questionCountLabel(n: number): string {
    return `${n.toLocaleString('en-IN')} ${n === 1 ? 'Q' : 'Qs'}`;
}
