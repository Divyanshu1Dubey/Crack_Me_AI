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
 * Build the reveal from the POST /questions/<id>/attempt/ response
 * (`{is_correct, correct_answer, ...}`; entitled users may also get
 * `explanation` / `mnemonic`).
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
        explanation: typeof d.explanation === 'string' ? d.explanation : undefined,
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
    const detailExplanation =
        (typeof d.explanation === 'string' && d.explanation.trim() ? d.explanation : '') ||
        (typeof d.effective_explanation === 'string' ? d.effective_explanation : '');
    return {
        correctAnswer: correct,
        isCorrect: reveal.isCorrect ?? (correct && pick ? correct === pick : null),
        explanation: reveal.explanation ?? detailExplanation,
        mnemonic: reveal.mnemonic ?? (typeof d.mnemonic === 'string' ? d.mnemonic : ''),
        images: Array.isArray(d.images) ? d.images : reveal.images,
    };
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
