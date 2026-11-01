/**
 * practiceData — small, framework-free helpers shared by the practice
 * surfaces (/questions/practice, the question bank's exam mode, /practice
 * and its side panels).
 *
 * Kept free of React / axios imports so the logic can be unit-tested in
 * plain Node (see tests/e2e/practice-data.spec.ts).
 */

// ── Paginated list responses ──────────────────────────────────────────

/** One page of a DRF list response, normalised. */
export interface ListPage<T> {
    items: T[];
    /** True when the API returned a `next` link (more rows exist). */
    hasNext: boolean;
    /** Total row count reported by the API, when it sent one. */
    count: number | null;
}

/** Normalise a DRF list response: a paginated object or a bare array. */
export function readPage<T>(data: unknown): ListPage<T> {
    if (Array.isArray(data)) {
        return { items: data as T[], hasNext: false, count: data.length };
    }
    const d = (data && typeof data === 'object' ? data : {}) as {
        results?: unknown;
        next?: unknown;
        count?: unknown;
    };
    const items = Array.isArray(d.results) ? (d.results as T[]) : [];
    return {
        items,
        // An empty page with a `next` link would loop forever; treat it as the end.
        hasNext: Boolean(d.next) && items.length > 0,
        count: typeof d.count === 'number' ? d.count : null,
    };
}

/** Append `incoming` to `existing`, skipping rows whose `id` is already present. */
export function appendUniqueById<T extends { id?: unknown }>(existing: T[], incoming: T[]): T[] {
    const seen = new Set(existing.map((row) => row?.id));
    const out = existing.slice();
    for (const row of incoming) {
        const id = row?.id;
        if (id !== undefined && id !== null && seen.has(id)) continue;
        seen.add(id);
        out.push(row);
    }
    return out;
}

/**
 * Fetch pages 1, 2, 3 … until the API stops sending a `next` link, `maxItems`
 * rows were collected or `maxPages` requests were made.
 *
 * The loop never assumes how many rows a page holds, so it works whether or
 * not the backend honours `page_size` (it used to ignore it and always send
 * 20 rows, which ended the old `items.length < 100` loop after one page).
 *
 * A failure on the first page rejects; a failure on a later page resolves
 * with the rows collected so far (`complete: false`).
 */
export async function collectPages<T extends { id?: unknown }>(
    fetchPage: (page: number) => Promise<unknown>,
    opts: { maxItems?: number; maxPages?: number; isCancelled?: () => boolean } = {},
): Promise<{ items: T[]; count: number | null; complete: boolean }> {
    const maxItems = opts.maxItems ?? Number.POSITIVE_INFINITY;
    const maxPages = opts.maxPages ?? 50;
    let items: T[] = [];
    let count: number | null = null;
    for (let page = 1; page <= maxPages; page += 1) {
        if (opts.isCancelled?.()) return { items, count, complete: false };
        let data: unknown;
        try {
            data = await fetchPage(page);
        } catch (err) {
            if (page === 1) throw err;
            return { items, count, complete: false };
        }
        const parsed = readPage<T>(data);
        if (count === null) count = parsed.count;
        items = appendUniqueById(items, parsed.items);
        if (!parsed.hasNext) return { items, count, complete: true };
        if (items.length >= maxItems) return { items: items.slice(0, maxItems), count, complete: false };
    }
    return { items, count, complete: false };
}

// ── Answer reveal (after the student picks an option) ─────────────────

/** What the UI needs to show once an option has been picked. */
export interface AnswerReveal {
    /** Correct option letter, '' when the server did not disclose it. */
    correctAnswer: string;
    /** Whether the pick was right; null when unknown. */
    isCorrect: boolean | null;
    /** undefined = the source did not include the field (fetch the detail). */
    explanation?: string;
    mnemonic?: string;
    /** Full image list (incl. explanation figures) from the detail payload. */
    images?: unknown[];
}

/** Upper-case option letter A-E, or '' for anything else. */
export function answerLetter(value: unknown): string {
    const s = typeof value === 'string' ? value.trim().toUpperCase().slice(0, 1) : '';
    return /^[A-E]$/.test(s) ? s : '';
}

/**
 * The explanation to show from an attempt response or a question detail
 * payload: the curated `explanation`, else the backend's
 * `effective_explanation`. A blank string counts as missing — the attempt
 * endpoint sends `explanation: ''` for rows that only have an AI
 * explanation.
 *
 * `effective_explanation` (questions.serializers.effective_explanation_for:
 * an admin lock / override, else the stored AI analysis, else the curated
 * text) goes first only when the payload flags an admin correction
 * (`explanation_overridden: true`). Without that flag it is usually the AI
 * analysis, which the AI panels already show, so the curated text stays
 * first, as in the test review (tests_engine.serializers). The answer
 * responses already send an admin override as `explanation`
 * (questions.views._question_explanation_payload).
 *
 * Returns '' when the payload has the fields but no text, and undefined
 * when it carries neither field (e.g. a redacted detail payload).
 */
export function pickExplanation(data: unknown): string | undefined {
    const d = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const order = d.explanation_overridden === true
        ? ['effective_explanation', 'explanation']
        : ['explanation', 'effective_explanation'];
    let sawField = false;
    for (const key of order) {
        const value = d[key];
        if (typeof value !== 'string') continue;
        sawField = true;
        if (value.trim()) return value;
    }
    return sawField ? '' : undefined;
}

/**
 * Build the reveal from the POST /questions/<id>/attempt/ response
 * (`{is_correct, correct_answer, explanation, effective_explanation, ...}`;
 * entitled users may also get `mnemonic`).
 */
export function revealFromAttempt(picked: string, data: unknown): AnswerReveal {
    const d = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    const pick = answerLetter(picked);
    const serverVerdict = typeof d.is_correct === 'boolean' ? d.is_correct : null;
    let correct = answerLetter(d.correct_answer);
    // A right answer reveals the key even when the server withheld it.
    if (!correct && serverVerdict === true) correct = pick;
    return {
        correctAnswer: correct,
        isCorrect: serverVerdict ?? (correct && pick ? correct === pick : null),
        explanation: pickExplanation(d),
        mnemonic: typeof d.mnemonic === 'string' ? d.mnemonic : undefined,
    };
}

/** True when the question detail endpoint is needed to complete the reveal. */
export function revealNeedsDetail(reveal: AnswerReveal): boolean {
    return !reveal.correctAnswer || reveal.explanation === undefined || reveal.mnemonic === undefined;
}

/** Fill the gaps of a reveal from the GET /questions/<id>/ detail payload. */
export function mergeRevealWithDetail(picked: string, reveal: AnswerReveal, detail: unknown): AnswerReveal {
    const d = (detail && typeof detail === 'object' ? detail : {}) as Record<string, unknown>;
    const pick = answerLetter(picked);
    const correct = reveal.correctAnswer || answerLetter(d.correct_answer);
    // A blank explanation from the attempt response is a gap the detail can fill.
    const explanation = reveal.explanation?.trim()
        ? reveal.explanation
        : (pickExplanation(d) ?? reveal.explanation ?? '');
    return {
        correctAnswer: correct,
        isCorrect: reveal.isCorrect ?? (correct && pick ? correct === pick : null),
        explanation,
        mnemonic: reveal.mnemonic ?? (typeof d.mnemonic === 'string' ? d.mnemonic : ''),
        images: Array.isArray(d.images) ? d.images : reveal.images,
    };
}

/**
 * What the practice player shows once the requests behind a pick settled:
 *  - 'ready':  the key is known — grade the pick and show the explanation.
 *  - 'locked': the server would not disclose the answer (free plan).
 *  - 'no-key': the server answered but has no answer key for the question.
 *              Retrying cannot help, and re-posting the attempt would record
 *              another mistake and more study time, so there is no Retry.
 *  - 'error':  the requests failed — Retry is worthwhile.
 */
export type RevealOutcome = 'ready' | 'locked' | 'no-key' | 'error';

export function classifyReveal(input: {
    reveal: AnswerReveal;
    /** The attempt POST returned 2xx. */
    attemptOk: boolean;
    /** A 2xx attempt / unredacted detail response carried an empty answer key. */
    serverHasNoKey: boolean;
    /** The detail refused the answer (answer_locked, 402/403/404 or upgrade_required). */
    gated: boolean;
}): RevealOutcome {
    if (input.reveal.correctAnswer) return 'ready';
    if (input.gated && input.attemptOk) return 'locked';
    if (input.serverHasNoKey) return 'no-key';
    return 'error';
}

/**
 * True when a response states the question's answer key and it is empty
 * (`correct_answer: ''`): the key does not exist, as opposed to a payload
 * that simply does not include the field.
 */
export function hasBlankAnswerKey(data: unknown): boolean {
    const d = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    return typeof d.correct_answer === 'string' && !answerLetter(d.correct_answer);
}

/**
 * Right / wrong for a pick from the POST /questions/<id>/attempt/
 * response: the server's `is_correct` when it is a boolean, else the pick
 * graded against the response's `correct_answer`; null when the question
 * has no answer key (`is_correct: null, correct_answer: ''` — the server
 * then records no attempt or mistake, so the pick is ungraded).
 */
export function attemptVerdict(picked: string, data: unknown): boolean | null {
    const d = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
    if (typeof d.is_correct === 'boolean') return d.is_correct;
    const key = answerLetter(d.correct_answer);
    const pick = answerLetter(picked);
    return key && pick ? key === pick : null;
}

/**
 * Seconds to send again when the student retries a failed attempt POST.
 * Without an HTTP response the outcome is unknown (the server may already
 * have recorded the attempt), so the retry sends 0 instead of counting the
 * study time twice.
 */
export function retryTimeSpent(err: unknown, timeSpent: number): number {
    return errorStatus(err) === null ? 0 : Math.max(0, timeSpent);
}

/**
 * Freemium gate payload: the backend answers free users with
 * `{code: 'upgrade_required', feature}` (HTTP 402/403). Returns the feature
 * label to show in the paywall, or null for any other error.
 */
export function upgradeRequiredFeature(err: unknown): string | null {
    const data = (err as { response?: { data?: { code?: unknown; feature?: unknown } } })?.response?.data;
    if (!data || data.code !== 'upgrade_required') return null;
    return typeof data.feature === 'string' && data.feature ? data.feature : 'PYQ answers';
}

/** HTTP status of an axios-style error, if any. */
export function errorStatus(err: unknown): number | null {
    const status = (err as { response?: { status?: unknown } })?.response?.status;
    return typeof status === 'number' ? status : null;
}

/**
 * Seconds to wait before retrying a rate-limited (429) request: the
 * `Retry-After` header when the browser can read it (cross-origin it is
 * only visible when the API exposes it), else the wait DRF states in the
 * body (`Request was throttled. Expected available in 42 seconds.`), else
 * 5; capped at 30.
 */
export function retryAfterSeconds(err: unknown): number {
    const response = (err as { response?: { headers?: Record<string, unknown>; data?: unknown } })?.response;
    let seconds = Number(response?.headers?.['retry-after']);
    if (!(Number.isFinite(seconds) && seconds > 0)) {
        const detail = (response?.data as { detail?: unknown } | null | undefined)?.detail;
        const match = typeof detail === 'string' ? detail.match(/available in (\d+(?:\.\d+)?) second/i) : null;
        seconds = match ? Number(match[1]) : NaN;
    }
    return Number.isFinite(seconds) && seconds > 0 ? Math.min(30, Math.ceil(seconds)) : 5;
}

// ── AI request failures (explain-answer, textbook lookup) ─────────────

/**
 * Why an AI request failed:
 *  - 'upgrade':     402 `{code: 'upgrade_required'}` — a premium question on
 *                   the free plan (the api.ts interceptor opens the paywall).
 *  - 'tokens':      429 `{error: 'insufficient_tokens'}` — the AI wallet is empty.
 *  - 'throttled':   any other 429 (the per-minute AI rate limit).
 *  - 'unavailable': 503 `{code: 'ai_unavailable'}` — no AI / grounded offline
 *                   answer right now; the backend never charges for it.
 *  - 'error':       anything else (network, 5xx).
 */
export type AiFailure = 'upgrade' | 'tokens' | 'throttled' | 'unavailable' | 'error';

function errorBody(err: unknown): Record<string, unknown> {
    const data = (err as { response?: { data?: unknown } })?.response?.data;
    return data && typeof data === 'object' ? (data as Record<string, unknown>) : {};
}

export function classifyAiFailure(err: unknown): AiFailure {
    if (upgradeRequiredFeature(err)) return 'upgrade';
    const status = errorStatus(err);
    const body = errorBody(err);
    if (body.code === 'ai_unavailable' || status === 503) return 'unavailable';
    if (status === 429) return body.error === 'insufficient_tokens' ? 'tokens' : 'throttled';
    return 'error';
}

/**
 * Short notice for a failed AI request. Never the server's own error text
 * (it can carry provider details); "not charged" only when the backend
 * said so (`charged: false`).
 */
export function aiFailureNotice(kind: AiFailure, err?: unknown): { title: string; message: string } {
    switch (kind) {
        case 'unavailable':
            return {
                title: 'AI is unavailable right now',
                message: errorBody(err).charged === false
                    ? 'You were not charged. Please try again in a few minutes.'
                    : 'Please try again in a few minutes.',
            };
        case 'throttled':
            return {
                title: 'Too many AI requests',
                message: "You're sending AI requests too quickly. Wait a few seconds and try again.",
            };
        case 'tokens':
            return {
                title: 'AI Tokens Exhausted',
                message: 'Your daily/weekly free tokens have been used up. Purchase more tokens to continue using AI features.',
            };
        case 'upgrade':
            return { title: 'Premium question', message: 'Upgrade to see its answer and explanation.' };
        default:
            return { title: 'AI Temporarily Unavailable', message: 'AI service unavailable. Please try again.' };
    }
}

/**
 * True when one of the per-question AI responses (`ai/why_correct/`, …)
 * says the hourly generation budget is spent (`rate_limited: true`).
 */
export function aiRateLimited(bodies: unknown[]): boolean {
    return bodies.some((b) => !!b && typeof b === 'object' && (b as { rate_limited?: unknown }).rate_limited === true);
}

/**
 * What a failed question-detail request means for the bank's detail pane:
 *  - 'locked':  premium question on the free plan (402 / 403, or a 404 for
 *               a non-premium user — the detail endpoint only serves the
 *               free showcase to free accounts);
 *  - 'missing': the question no longer exists (404 for a premium user);
 *  - 'error':   network / server error — Retry is worthwhile.
 */
export function detailFailureKind(err: unknown, premium: boolean): 'locked' | 'missing' | 'error' {
    const status = errorStatus(err);
    if (upgradeRequiredFeature(err) || status === 402 || status === 403) return 'locked';
    if (status === 404) return premium ? 'missing' : 'locked';
    return 'error';
}

// ── Question bank stats strip / year list ─────────────────────────────

export interface BankStatsSummary {
    /** Questions with a real year (year 0 is the Expert Curated sentinel). */
    pyqTotal: number;
    /** How many of those the student has answered. */
    pyqSolved: number;
    /** Undated (year 0) questions in the same stats scope. */
    undatedTotal: number;
    /** False when the stats cover no question at all (nothing to show). */
    hasRows: boolean;
}

/**
 * One PYQ definition for the bank's headline and its progress bar: sums of
 * the `/questions/stats/` `by_year` rows with year > 0 (`total` /
 * `total_solved` also count the undated rows, which made the strip read
 * "1,892 PYQs" above "Overall Progress 0 / 2,277"). Falls back to
 * `total` / `total_solved` when `by_year` is missing.
 */
export function summariseBankStats(stats: unknown): BankStatsSummary {
    const s = (stats && typeof stats === 'object' ? stats : {}) as {
        by_year?: unknown;
        total?: unknown;
        total_solved?: unknown;
    };
    const num = (v: unknown): number => {
        const n = Number(v);
        return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
    };
    if (Array.isArray(s.by_year)) {
        let pyqTotal = 0;
        let pyqSolved = 0;
        let undatedTotal = 0;
        for (const row of s.by_year) {
            const r = (row && typeof row === 'object' ? row : {}) as { year?: unknown; count?: unknown; solved?: unknown };
            const count = num(r.count);
            if (Number(r.year) > 0) {
                pyqTotal += count;
                // Attempts on since-archived rows can exceed the active count.
                pyqSolved += Math.min(count, num(r.solved));
            } else {
                undatedTotal += count;
            }
        }
        return { pyqTotal, pyqSolved, undatedTotal, hasRows: pyqTotal + undatedTotal > 0 };
    }
    const total = num(s.total);
    return { pyqTotal: total, pyqSolved: Math.min(total, num(s.total_solved)), undatedTotal: 0, hasRows: total > 0 };
}

/** The `/questions/years/` payload (a bare array, or `{results}`) as positive years. */
export function normaliseYears(data: unknown): number[] {
    const rows = Array.isArray(data)
        ? data
        : (data && typeof data === 'object' && Array.isArray((data as { results?: unknown }).results)
            ? (data as { results: unknown[] }).results
            : []);
    const out: number[] = [];
    for (const row of rows) {
        const year = Number(row);
        if (Number.isInteger(year) && year > 0 && !out.includes(year)) out.push(year);
    }
    return out;
}

/** Mirrors backend `is_premium`: active plan, or admin/staff. */
export function isPremiumUser(user: unknown): boolean {
    const u = (user || {}) as {
        is_premium?: boolean;
        is_admin?: boolean;
        role?: string;
        subscription_info?: { is_active?: boolean } | null;
    };
    return u.is_premium === true || u.subscription_info?.is_active === true || u.is_admin === true || u.role === 'admin';
}

// ── Per-question AI panels (/questions/<id>/ai/<feature>/) ────────────

/**
 * Canned strings `questions/ai_per_question.py` returns when no AI output
 * exists (anonymous caller, AI offline, provider failure). They are generic
 * study tips, not analysis of the question, so the reveal panel hides them
 * instead of presenting them as AI content.
 */
const AI_TEMPLATE_TEXTS = new Set([
    "Core concept: review the textbook chapter covering the stem's keywords.",
    'The correct option matches the canonical guideline / definition referenced by the question stem.',
    'Clinically relevant: appears in viva voce and INI-CET short cases.',
    'Mnemonic: look for the first-letter pattern across the four options.',
    'Medium-high yield; appears in ≥2 PYQs over the last 5 years.',
    'Each wrong distractor fails because it does not satisfy the canonical definition referenced by the stem.',
    'Distractors: each fails the canonical definition; cross-check with the textbook.',
]);

/** `why_incorrect` is always built from a template line per distractor. */
const WHY_INCORRECT_TEMPLATE = /— not the canonical answer because the stem requires /;

/** True when `text` is one of the backend's template fallbacks. */
export function isAiTemplateText(text: unknown): boolean {
    if (typeof text !== 'string') return false;
    const t = text.trim();
    return AI_TEMPLATE_TEXTS.has(t) || WHY_INCORRECT_TEMPLATE.test(t);
}

/**
 * Read one per-question AI field, returning '' for missing values, template
 * fallbacks, or responses the backend explicitly marks as fallbacks.
 */
export function readAiField(data: unknown, field: string): string {
    if (!data || typeof data !== 'object') return '';
    const d = data as Record<string, unknown>;
    if (d.is_fallback === true || d.fallback === true || d.source === 'template') return '';
    const value = d[field];
    if (typeof value !== 'string') return '';
    const text = value.trim();
    return text && !isAiTemplateText(text) ? text : '';
}

// ── Related topics / textbook references ──────────────────────────────

export interface RelatedTopic {
    id: number;
    name: string;
    count: number | null;
}

/**
 * `ai/related_topics/` returns `values('topic_id', 'topic__name')` rows
 * annotated with a count `c`. Rows without a topic are dropped.
 */
export function normaliseRelatedTopics(rows: unknown): RelatedTopic[] {
    if (!Array.isArray(rows)) return [];
    const out: RelatedTopic[] = [];
    for (const row of rows) {
        if (!row || typeof row !== 'object') continue;
        const r = row as Record<string, unknown>;
        const id = Number(r.topic_id ?? r.id);
        const rawName = r.topic__name ?? r.topic_name ?? r.topic ?? r.name;
        const name = typeof rawName === 'string' ? rawName.trim() : '';
        if (!Number.isFinite(id) || id <= 0 || !name) continue;
        out.push({ id, name, count: typeof r.c === 'number' ? r.c : null });
    }
    return out;
}

export interface TextbookReference {
    book: string;
    chapter: string;
    page: string;
    excerpt: string;
}

/**
 * `/ai/textbook-reference/` returns `{references: [{book, page, excerpt,
 * relevance_score}]}`. Also accepts a bare list or a legacy single object
 * (`book_name` / `page_range` / `reference`).
 */
export function normaliseTextbookReferences(data: unknown): TextbookReference[] {
    const d = data as { references?: unknown } | unknown[] | null | undefined;
    let rows: unknown[] = [];
    if (Array.isArray(d)) rows = d;
    else if (d && typeof d === 'object' && Array.isArray((d as { references?: unknown }).references)) {
        rows = (d as { references: unknown[] }).references;
    } else if (d && typeof d === 'object') rows = [d];

    const text = (v: unknown): string =>
        typeof v === 'string' ? v.trim() : typeof v === 'number' && Number.isFinite(v) ? String(v) : '';
    const out: TextbookReference[] = [];
    for (const row of rows) {
        if (!row || typeof row !== 'object') continue;
        const r = row as Record<string, unknown>;
        const ref: TextbookReference = {
            book: text(r.book) || text(r.book_name),
            chapter: text(r.chapter),
            page: text(r.page) || text(r.page_range) || text(r.page_number),
            excerpt: text(r.excerpt) || text(r.reference),
        };
        if (ref.book || ref.excerpt) out.push(ref);
    }
    return out;
}

/**
 * `screenshot_url` of a `GET /ai/screenshot/{id}/` body, or '' when it
 * carries none (`{status: 'rendering'}`, an error body). Only a URL is
 * accepted, never a server filesystem path (the old `screenshot_path`).
 */
export function screenshotUrlFrom(data: unknown): string {
    const raw = data && typeof data === 'object' ? (data as { screenshot_url?: unknown }).screenshot_url : '';
    const url = typeof raw === 'string' ? raw.trim() : '';
    if (!url || url.includes('\\')) return '';
    // Absolute http(s), protocol- or root-relative.
    return /^(https?:\/\/|\/)/i.test(url) ? url : '';
}

/** Default pause before the one retry of a 202 `{status: 'rendering'}`. */
export const SCREENSHOT_RETRY_MS = 3000;

/**
 * The textbook page image for "Find in Textbook" from `GET
 * /ai/screenshot/{id}/`: its URL on 200; on 202 (another request is
 * rendering the page) asked once more after `retryDelayMs`; null for a
 * 404 (no page for this question), a 402 (the api.ts interceptor opens the
 * paywall), any other failure, or a second 202. `isCurrent` is checked
 * before the retry so a question the student has left is not asked again.
 */
export async function fetchPageScreenshot(
    getScreenshot: (questionId: number) => Promise<{ status?: number; data?: unknown }>,
    questionId: number,
    opts: {
        retryDelayMs?: number;
        isCurrent?: () => boolean;
        wait?: (ms: number) => Promise<void>;
    } = {},
): Promise<string | null> {
    const retryDelayMs = opts.retryDelayMs ?? SCREENSHOT_RETRY_MS;
    const isCurrent = opts.isCurrent ?? (() => true);
    const wait = opts.wait ?? ((ms: number) => new Promise<void>(resolve => { setTimeout(resolve, ms); }));
    for (let round = 0; round < 2; round += 1) {
        let res: { status?: number; data?: unknown } | undefined;
        try {
            res = await getScreenshot(questionId);
        } catch {
            return null;
        }
        const url = screenshotUrlFrom(res?.data);
        if (url) return url;
        if (res?.status !== 202 || round > 0) return null;
        await wait(retryDelayMs);
        if (!isCurrent()) return null;
    }
    return null;
}

// ── Exam / subject URL parameters ─────────────────────────────────────

/** Normalised URL value (`NEET_PG`, `neet pg`, `Neet-PG` → `neet-pg`) → `Question.exam_type`. */
const EXAM_PARAM_TO_TYPE: Record<string, string> = {
    'cms': 'cms',
    'upsc-cms': 'cms',
    'upsc': 'cms',
    'neet-pg': 'neet_pg',
    'neetpg': 'neet_pg',
    'ini-cet': 'ini_cet',
    'inicet': 'ini_cet',
    'ini-cet-pg': 'ini_cet',
    'fmge': 'fmge',
    'usmle': 'usmle',
    // No Medical Officer rows yet: the CMS bank stands in.
    'medical-officer': 'cms',
};

const EXAM_TYPE_LABEL: Record<string, string> = {
    cms: 'UPSC CMS',
    neet_pg: 'NEET PG',
    ini_cet: 'INI-CET',
    fmge: 'FMGE',
    usmle: 'USMLE',
};

function normaliseExamParam(raw: string | null | undefined): string {
    return typeof raw === 'string' ? raw.trim().toLowerCase().replace(/[\s_+]+/g, '-') : '';
}

/**
 * `?exam=` / `?exam_type=` value → backend `exam_type`, matched
 * case-insensitively and accepting slugs (`neet-pg`), enum values
 * (`neet_pg`, `NEET_PG`) and labels (`NEET PG`, `UPSC CMS`). Unknown → null.
 */
export function examTypeFromParam(raw: string | null | undefined): string | null {
    return EXAM_PARAM_TO_TYPE[normaliseExamParam(raw)] ?? null;
}

/** Display label (`Question.exam_source` prefix) for a URL exam value; null when unknown. */
export function examLabelFromParam(raw: string | null | undefined): string | null {
    if (normaliseExamParam(raw) === 'medical-officer') return 'Medical Officer';
    const type = examTypeFromParam(raw);
    return type ? EXAM_TYPE_LABEL[type] : null;
}

/** Display label for an `exam_type` enum value (falls back to the value itself). */
export function examTypeLabel(examType: string): string {
    return EXAM_TYPE_LABEL[examType] || examType;
}

/**
 * Chip text for a question's exam + year, from `exam_source`
 * ("NEET PG (recall)" → "NEET PG 2025"). Without a source: "PYQ 2025".
 */
export function examYearChip(examSource: unknown, year: unknown): string {
    const label = typeof examSource === 'string' ? examSource.replace(/\s*\(.*\)\s*$/, '').trim() : '';
    const y = typeof year === 'number' && year > 0 ? String(year) : '';
    if (!y) return label;
    return `${label || 'PYQ'} ${y}`;
}

/** A subject row as the question bank's subject filter shows it. */
export interface SubjectOption {
    id: number;
    name: string;
    code?: string;
    count: number;
}

/**
 * Names public pages / blog posts use in `?subject=` that differ from the
 * Subject rows (compared after `subjectKey`).
 */
const SUBJECT_ALIASES: Record<string, string> = {
    medicine: 'generalmedicine',
    internalmedicine: 'generalmedicine',
    surgery: 'generalsurgery',
    obg: 'obstetricsgynaecology',
    obgyn: 'obstetricsgynaecology',
    obstetricsandgynaecology: 'obstetricsgynaecology',
    gynaecology: 'obstetricsgynaecology',
    psm: 'communitymedicine',
    preventivesocialmedicine: 'communitymedicine',
    preventiveandsocialmedicine: 'communitymedicine',
    communitymedicinepsm: 'communitymedicine',
    pediatrics: 'paediatrics',
    anesthesia: 'anaesthesia',
    anesthesiology: 'anaesthesia',
    anaesthesiology: 'anaesthesia',
    orthopedics: 'orthopaedics',
    radiology: 'radiodiagnosis',
    biochemistrygenetics: 'biochemistry',
    microbiologyimmunology: 'microbiology',
    forensic: 'forensicmedicine',
    fmt: 'forensicmedicine',
    eye: 'ophthalmology',
    skin: 'dermatology',
};

/** Lower-case letters and digits only; '&' and 'and' are dropped. */
function subjectKey(value: string): string {
    return value.toLowerCase().replace(/&/g, ' ').replace(/\band\b/g, ' ').replace(/[^a-z0-9]+/g, '');
}

/**
 * Resolve a `?subject=` value — a subject id, name, code or public-page
 * slug such as `medicine`, `obg`, `psm` or `General%20Medicine` — to the id
 * of one of `options`. Returns null when nothing matches (the filter is
 * then left empty instead of sending an id the API would reject).
 */
export function resolveSubjectParam(raw: string | null | undefined, options: SubjectOption[]): number | null {
    const value = typeof raw === 'string' ? raw.trim() : '';
    if (!value || options.length === 0) return null;
    if (/^\d+$/.test(value)) {
        const id = Number(value);
        return options.some((o) => o.id === id) ? id : null;
    }
    const key = subjectKey(value);
    if (!key) return null;
    const wanted = SUBJECT_ALIASES[key] ?? key;
    const byName = options.find((o) => subjectKey(o.name) === wanted);
    if (byName) return byName.id;
    const byCode = options.find((o) => o.code && subjectKey(o.code) === key);
    return byCode ? byCode.id : null;
}

// ── /practice queue deep links ────────────────────────────────────────

/**
 * Position a deep-linked question (`/practice?id=N`) in a freshly built
 * queue. Mode queues are random, so the requested id is usually absent:
 * `prependIfMissing` puts it first instead of silently opening another
 * question.
 */
export function placeInQueue(
    ids: number[],
    wanted: number | null,
    prependIfMissing: boolean,
): { ids: number[]; index: number } {
    if (!wanted) return { ids, index: 0 };
    const at = ids.indexOf(wanted);
    if (at >= 0) return { ids, index: at };
    if (!prependIfMissing) return { ids, index: 0 };
    return { ids: [wanted, ...ids], index: 0 };
}

/**
 * Open `wanted` from the current position: jump to it when it is already
 * queued, otherwise insert it right after the current question.
 */
export function openInQueue(ids: number[], currentIndex: number, wanted: number): { ids: number[]; index: number } {
    const at = ids.indexOf(wanted);
    if (at >= 0) return { ids, index: at };
    const insertAt = ids.length === 0 ? 0 : Math.min(ids.length, Math.max(0, currentIndex) + 1);
    const next = ids.slice();
    next.splice(insertAt, 0, wanted);
    return { ids: next, index: insertAt };
}
