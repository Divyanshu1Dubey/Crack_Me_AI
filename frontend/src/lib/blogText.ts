/**
 * blogText — small, dependency-free blog helpers that client bundles may
 * import (unlike lib/blog.ts, which bundles every static post).
 *
 * countBlogWords is backend/blog_engine/text_stats.py count_words, step for
 * step: the API reports that count for every post (word_count, and the
 * reading_time derived from it) and the site shows it; this port serves the
 * static fallback posts and the editor's live count. The vectors in
 * tests/unit/blog-article.test.ts and backend tests_blog_editor_api.py keep
 * the two in step: change both together.
 */

/** Callout types (GitHub alert syntax, `> [!NOTE]`), in toolbar order, with their titles. */
export const CALLOUT_KINDS = ['note', 'tip', 'important', 'warning', 'caution'] as const;
export type CalloutKind = (typeof CALLOUT_KINDS)[number];
export const CALLOUT_LABELS: Record<CalloutKind, string> = {
    note: 'Note',
    tip: 'Tip',
    important: 'Important',
    warning: 'Warning',
    caution: 'Caution',
};

export function calloutKind(value: unknown): CalloutKind {
    const kind = String(value ?? '').toLowerCase();
    return (CALLOUT_KINDS as readonly string[]).includes(kind) ? (kind as CalloutKind) : 'note';
}

/** Reading speed behind readingMinutes (text_stats.WORDS_PER_MINUTE). */
export const WORDS_PER_MINUTE = 200;
/** Posts with fewer words are "thin" in /admin/blog (text_stats.THIN_POST_WORDS). */
export const THIN_POST_WORDS = 400;

const COUNT_STEPS: ReadonlyArray<[RegExp, string]> = [
    [/\r\n?/g, '\n'],
    [/<!--[\s\S]*?-->/g, ' '], // HTML comments
    [/!\[[^\]]*\]\([^)]*\)/g, ' '], // images (alt text is not read)
    [/\[([^\]]*)\]\([^)]*\)/g, '$1'], // links: keep the text
    [/<[^>\n]*>/g, ' '], // HTML tags, <autolinks>
    [/https?:\/\/\S+/gi, ' '], // bare URLs
    [/\[!(?:note|tip|important|warning|caution)\]/gi, ' '], // callout markers
    [/^[ \t]*\d{1,9}[.)](?=[ \t])/gm, ' '], // ordered-list numbers
    [/[#>*_`~|[\]\\]/g, ' '], // markdown punctuation
];

const HAS_WORD_CHAR = /[\p{L}\p{N}]/u;

/** Words a reader sees in a markdown body: whitespace-separated tokens with a letter or a digit. */
export function countBlogWords(markdown: string | null | undefined): number {
    let text = markdown ?? '';
    for (const [pattern, replacement] of COUNT_STEPS) text = text.replace(pattern, replacement);
    return text.split(/\s+/).filter((token) => HAS_WORD_CHAR.test(token)).length;
}

/** Minutes at WORDS_PER_MINUTE, rounded half up, at least 1. */
export function readingMinutes(words: number): number {
    return Math.max(1, Math.floor(Math.max(0, words) / WORDS_PER_MINUTE + 0.5));
}

/** "N min", what the cards and the post header show. */
export function readingTimeLabel(words: number): string {
    return `${readingMinutes(words)} min`;
}

export function isThinPost(words: number): boolean {
    return words < THIN_POST_WORDS;
}

/** Human-readable date in long form, e.g. "28 July 2026" (the input when it does not parse). */
export function formatPostDate(iso: string): string {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' });
}

/**
 * Anchor id for a heading's text: the rule the post page always used for its
 * "On this page" links (lowercase words joined by hyphens, at most 80
 * characters), without a leading hyphen or underscore. '' when nothing is left
 * (e.g. a heading in another script); callers number those.
 */
export function slugifyHeading(text: string): string {
    return text
        .replace(/[`*_]/g, '')
        .toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-')
        .slice(0, 80)
        .replace(/^[-_]+/, '');
}
