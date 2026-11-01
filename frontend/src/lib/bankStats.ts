/**
 * bankStats.ts — the question-bank figures quoted on public pages.
 *
 * One source, so every page, meta description and JSON-LD block states the
 * same size for the same bank. Figures are rounded DOWN from the production
 * bank (Nov 2026 backup):
 *   - UPSC CMS: 1,880 active PYQs dated 2018–2025 (eight papers of 240
 *     questions cap that range at 1,920; undated rows are not counted).
 *   - NEET PG:  about 4,200 active questions (mostly exam recalls).
 *   - INI-CET:  about 100 active recall questions.
 * FMGE and USMLE have no question bank of their own yet — do not quote a
 * size for them. Raise a figure here only after the active, dated count in
 * the database has actually passed it.
 *
 * Keep this file free of imports (it is unit-tested directly with Node).
 */

/** UPSC CMS previous-year questions in the bank (1,880 active, 2018–2025). */
export const CMS_PYQ_COUNT = '1,800+';

/** Exam years the UPSC CMS bank covers. */
export const CMS_PYQ_YEARS = '2018–2025';

/** Number of UPSC CMS exam years covered (2018–2025 inclusive). */
export const CMS_PYQ_YEAR_COUNT = 8;

/** "1,800+ UPSC CMS PYQs (2018–2025)" — the standard phrase for copy. */
export const CMS_PYQ_PHRASE = `${CMS_PYQ_COUNT} UPSC CMS PYQs (${CMS_PYQ_YEARS})`;

/** NEET PG questions in the bank (about 4,200 active). */
export const NEET_PG_QUESTION_COUNT = '4,000+';

/** INI-CET recall questions in the bank (about 100 active). */
export const INI_CET_QUESTION_COUNT = 'about 100';

/** Where the INI-CET bank lives in the app (same route as the sidebar). */
export const INI_CET_BANK_HREF = '/questions/inicet/practice';
