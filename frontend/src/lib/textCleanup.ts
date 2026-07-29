/**
 * textCleanup.ts — Restore text that has been double-encoded.
 *
 * Some PYQ entries in the database (and in `questions_fixture.json`) were
 * stored as the Latin-1 interpretation of UTF-8 bytes — classic mojibake.
 * The visible symptom is sequences like `ΓÇÿ`, `ΓÇÖ`, `ΓÇ£`, `ΓÇ¥`,
 * `ΓÇª` and `ΓÇô` appearing where the user expects `'`, `'`, `"`, `"`,
 * `…` and `–`.
 *
 * The bug: the source text contains Unicode codepoints like U+2018
 * (LEFT SINGLE QUOTATION MARK). When those bytes are mistakenly
 * interpreted as Latin-1, each codepoint becomes two Latin-1 chars
 * (e.g. U+2018 → bytes CE 92 → "Î" + "'" — wait, more precisely the
 * UTF-8 bytes E2 80 98 become three Latin-1 characters rendered as
 * "ΓÇÿ"). Storing those Latin-1 chars back as UTF-8 yields the
 * "ΓÇÿ" sequence users actually see.
 *
 * We reverse the damage at render time so the user sees the
 * correct punctuation characters (`'`, `'`, `"`, `"`, `—`, `…`) instead of
 * the "ΓÇÿ" garbled sequences. Idempotent — safe to call multiple times.
 *
 * Also strips surrounding asterisks (`*`) from option text — some
 * PYQ fixtures leave trailing `*` markers on the correct option.
 */

const MOJIBAKE_MAP: Array<[RegExp, string]> = [
    // 6-char Latin-1-of-UTF-8 patterns — these are the "ΓÇÿ" family.
    [/Î¸/g, '—'], // em dash
    [/Î¦/g, '—'], // em dash (alt)
    [/â€"/g, '—'], // em dash (Windows-encoded variant)
    [/â€™/g, '\u2019'], // right single quote (apostrophe)
    [/â€˜/g, '\u2018'], // left single quote
    [/â€œ/g, '\u201C'], // left double quote
    [/â€/g, '\u201D'], // right double quote
    [/â€¦/g, '…'], // ellipsis
    [/â€"/g, '–'], // en dash
    [/â€"/g, '—'], // em dash
    // The literal "ΓÇÿ" / "ΓÇÖ" sequences (Unicode-Γ + Latin Ç + …).
    [/ΓÇÿ/g, '\u2018'], // left single quote
    [/ΓÇÖ/g, '\u2019'], // right single quote
    [/ΓÇ£/g, '\u201C'], // left double quote
    [/ΓÇ¥/g, '\u201D'], // right double quote
    [/ΓÇª/g, '…'], // ellipsis
    [/ΓÇ­/g, '–'], // en dash
    [/ΓÇô/g, '–'], // en dash
    [/ΓÇö/g, '—'], // em dash
    // Windows-1252 mojibake patterns (common in Indian medical databases).
    [/Ã¢â‚¬â„¢/g, '\u2019'], // right single quote (triple-encoded)
    [/Ã¢â‚¬Å"/g, '\u201C'], // left double quote (triple-encoded)
    [/Ã¢â‚¬\u009D/g, '\u201D'], // right double quote (triple-encoded)
    [/Ã¢â‚¬â€œ/g, '–'], // en dash (triple-encoded)
    [/Ã¢â‚¬â€/g, '—'], // em dash (triple-encoded)
    [/Ã¢â‚¬¦/g, '…'], // ellipsis (triple-encoded)
    // Other common mojibake.
    [/Â°/g, '°'], // degree
    [/Â·/g, '·'], // middle dot
    [/Âµ/g, 'µ'], // micro sign
    [/Â±/g, '±'], // plus-minus
    [/Â½/g, '½'], // one-half
    [/Â¼/g, '¼'], // one-quarter
    [/Â¾/g, '¾'], // three-quarters
    [/Â²/g, '²'], // superscript 2
    [/Â³/g, '³'], // superscript 3
    [/Ã©/g, 'é'],
    [/Ã¨/g, 'è'],
    [/Ã¢/g, 'â'],
    [/Ã®/g, 'î'],
    [/Ã´/g, 'ô'],
    [/Ã»/g, 'û'],
    [/Ã /g, 'à'],
    [/Ã§/g, 'ç'],
    [/Ã¶/g, 'ö'],
    [/Ã¤/g, 'ä'],
    [/Ã¼/g, 'ü'],
    [/Ã±/g, 'ñ'],
    // Stray BOM / zero-width chars that render as garbled.
    [/\uFEFF/g, ''],
    [/\uFFFD/g, ''], // replacement char
];

/**
 * Coerce any value into a plain string for display. Defensive against
 * objects (e.g. a stray citation array stored as message content)
 * that would otherwise render as `[object Object]` and crash callers
 * like `.replace()` / `.split()` downstream.
 */
export function coerceToText(value: unknown): string {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
        return String(value);
    }
    if (Array.isArray(value)) {
        // Common shape: an array of citations. Render a readable summary
        // instead of crashing the chat thread.
        return value
            .map((item) => {
                if (item === null || item === undefined) return '';
                if (typeof item === 'string') return item;
                if (typeof item === 'object') {
                    const obj = item as Record<string, unknown>;
                    const book = obj.book ?? obj.name ?? obj.title ?? '';
                    const page = obj.page ?? obj.page_number;
                    const excerpt = obj.excerpt ?? obj.text ?? obj.snippet ?? '';
                    if (book && page) return `${book} p.${page}: ${excerpt}`;
                    if (book && excerpt) return `${book}: ${excerpt}`;
                    if (excerpt) return String(excerpt);
                    if (book) return String(book);
                }
                return String(item);
            })
            .filter(Boolean)
            .join('\n');
    }
    if (typeof value === 'object') {
        // Last resort: stringify objects (mostly citations/dict payloads
        // that were saved into a text column by mistake).
        try {
            return JSON.stringify(value);
        } catch {
            return '[unrenderable content]';
        }
    }
    return String(value);
}

/**
 * Decode double-encoded UTF-8 mojibake so the user sees real
 * punctuation characters (`'`, `'`, `"`, `"`, `—`, `…`) instead of
 * the "ΓÇÿ" garbled sequences. Idempotent — safe to call multiple times.
 *
 * Accepts any value: non-string inputs are coerced so a stray object
 * never crashes the chat thread via `.replace()`.
 */
export function decodeMojiB(text: unknown): string {
    const safe = coerceToText(text);
    if (!safe) return '';
    let out = safe;
    for (const [pattern, replacement] of MOJIBAKE_MAP) {
        out = out.replace(pattern, replacement);
    }
    return out;
}

/**
 * Detect whether text is likely garbled / unreadable mojibake.
 *
 * Returns true when a large fraction of the text consists of
 * characters from the Devanagari-range or Latin-Extended Unicode blocks
 * that typically indicate multi-byte corruption (e.g. the "ÏÀÖÏÀÖ"
 * patterns visible in corrupted question_text fields).
 *
 * Heuristic: if more than 40% of non-whitespace characters fall in
 * the U+00C0–U+024F or U+0900–U+097F ranges AND the text contains
 * no recognisable English/medical words, it's probably garbled.
 */
export function isLikelyGarbled(text: string): boolean {
    if (!text || text.length < 10) return false;
    const nonWs = text.replace(/\s/g, '');
    if (nonWs.length === 0) return false;
    // Count chars in corruption-prone ranges.
    let suspectChars = 0;
    for (let i = 0; i < nonWs.length; i++) {
        const c = nonWs.charCodeAt(i);
        // Latin Extended-A/B garble range + Devanagari
        if ((c >= 0x00C0 && c <= 0x024F) || (c >= 0x0900 && c <= 0x097F)) {
            suspectChars++;
        }
    }
    const ratio = suspectChars / nonWs.length;
    // Only flag as garbled if ratio is very high — real medical text
    // may contain some accented characters but not 40%+.
    return ratio > 0.4;
}

/**
 * Returns readable text or a fallback placeholder when the text is
 * likely garbled beyond repair.
 */
export function safeDisplayText(text: string, fallback: string): string {
    if (!text) return fallback;
    const cleaned = decodeMojiB(text);
    if (isLikelyGarbled(cleaned)) return fallback;
    return cleaned;
}

/**
 * Strip trailing asterisks/stars that the PYQ fixture leaves on the
 * correct option. Some entries end in `***` or `*` which would otherwise
 * render literally in the option card.
 */
export function cleanOptionText(text: string): string {
    if (!text) return '';
    return decodeMojiB(text).replace(/\s*\*+\s*$/, '').trim();
}

/**
 * Combine mojibake cleanup with a generic markdown-stripping preview
 * used by list cards and tooltips.
 */
export function cleanPreview(text: string): string {
    return decodeMojiB(text || '');
}

// ---------------------------------------------------------------------------
// Defence-in-depth: Sanitize question/option text at render time.
//
// The NEET PG (recall) importer (5,080 rows) persisted the entire PDF block
// — stem, options, answer key, explanation, and a "MEDICAL JUNCTION TEAM"
// footer — into `question_text`. Some rows have the footer alone stuffed
// into `option_a`. The backend cleanup script (`cleanup_question_text_
// contamination.py`) fixes the DB, but until a deploy rolls out, the
// frontend must render clean text for the user.
//
// `sanitizeQuestionText()` strips trailers, splits a leaked-options block
// (where the stem ends and `A. … B. … C. … D. …` begins), and removes any
// leaked "Answer: X" / "Explanation:" stuffer so the user only sees the
// actual question stem. The split-off options are dropped on the floor in
// the frontend (the backend already has them in dedicated columns).
//
// `stripRawHtml()` handles the related "docx → HTML serialization leaked
// into a text column" case — `<p>`, `&nbsp;`, `<ul><li>`, `<span style=…>`
// etc. were stored verbatim by an older mocktest parser; ReactMarkdown
// expects markdown, so those tags would otherwise leak into the UI as
// literal characters. Backend `strip_html_from_text.py` cleans existing
// rows; this helper covers any future import until it lands.

// Tag-only check — fast guard so we don't pay the regex cost on clean text.
const RAW_HTML_RE = /<[a-zA-Z][^>]*>|&(?:nbsp|amp|lt|gt|quot|#\d+);/i;
const LIST_ITEM_RE = /<li[^>]*>/gi;
const LIST_END_RE = /<\/li>/gi;
const BLOCK_TAG_RE = /<\/?(?:p|div|h[1-6]|ul|ol|li|br)[^>]*>/gi;
const ANY_TAG_RE = /<[^>]+>/g;
const ENTITY_MAP: Record<string, string> = {
    '&nbsp;': ' ',
    '&amp;': '&',
    '&lt;': '<',
    '&gt;': '>',
    '&quot;': '"',
    '&apos;': "'",
    '&hellip;': '…',
    '&mdash;': '—',
    '&ndash;': '–',
    '&rsquo;': "'",
    '&lsquo;': "'",
    '&rdquo;': '"',
    '&ldquo;': '"',
};

/**
 * Strip raw HTML tags from a text field so it can be safely passed to
 * ReactMarkdown. Also converts `<li>` to markdown bullets, `<p>/<br>/<div>`
 * closers to newlines, and decodes common HTML entities. Used as a
 * defence-in-depth against any docx parser that ever serializes rich text
 * into a text column.
 */
export function stripRawHtml(text: string): string {
    if (!text || !RAW_HTML_RE.test(text)) return text || '';
    let s = text;
    s = s.replace(LIST_ITEM_RE, '\n- ');
    s = s.replace(LIST_END_RE, '\n');
    s = s.replace(BLOCK_TAG_RE, '\n');
    s = s.replace(ANY_TAG_RE, '');
    s = s.replace(/&[a-z]+;|&#\d+;/gi, (m) => ENTITY_MAP[m.toLowerCase()] ?? ' ');
    s = s.replace(/[ \t]+/g, ' ');
    s = s.replace(/\n[ \t]+/g, '\n');
    s = s.replace(/\n{3,}/g, '\n\n');
    return s.trim();
}
// ---------------------------------------------------------------------------

// NOTE: TS 5.9's parser misreads `(?im)` regex flag-groups as a ternary
// expression and emits TS1005 (':' expected). We build these via the
// `RegExp` constructor so the literal never reaches the parser as a
// regex with a leading `(?...)` group.
const TRAILER_PATTERNS: Array<[RegExp, string]> = [
    // Multi-line patterns — match the full line, possibly after a newline.
    [new RegExp('^\\s*PDF\\s+Compiled\\s+by[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*To\\s+Know\\s+about\\s+our\\s+products[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*https?:\\/\\/medicoapps\\.org[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*MEDICAL[\\s\\-]*JUNCTION(\\.COM)?\\s*$', 'gim'), ''],
    [new RegExp('^\\s*MEDICAL\\s+JUNCTION\\s+TEAM\\s*$', 'gim'), ''],
    [new RegExp('^\\s*www\\.medical[\\-_]?junction\\.com[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Medicoapps\\.org[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Medicoapps[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Compiled\\s+by[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*For\\s+more\\s+visit[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Also\\s+follow\\s+us[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Follow\\s+us\\s+on[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Join\\s+our\\s+telegram[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Telegram[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Disclaimer[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Note\\s*:[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Source\\s*:[^\\n]*$', 'gim'), ''],
    [new RegExp('^\\s*Image\\s+courtesy[^\\n]*$', 'gim'), ''],
];

// Single-line option marker: "A. xxx" / "A) xxx" / "(A) xxx"
const OPTION_LINE = /^\s*\(?([A-Da-d])\)?[\.\)]\s+(.+?)\s*$/;

// Leaked "Answer: X" / "Answer-X" / "Answer <A: …" line.
const ANSWER_LINE = /^\s*Answer\s*[\-<:>]\s*<?\s*([A-Da-d])[^\n]*$/i;
const ANSWER_INLINE = /\bAnswer\s*[\-<:>]\s*<?\s*([A-Da-d])\b/i;
// Leaked "Explanation:" line — the body's explanation should already be in
// the `explanation` field, so we drop everything from here onward.
const EXPL_START_LINE = /^\s*Explan?ation\s*[\-:]?\s*$/i;
// "Explanation: blah" on the same line.
const EXPL_INLINE_LINE = /^\s*Explan?ation\s*[\-:]?\s*.+$/i;

/**
 * Truncate a question string at the first leaked `A. …` block, drop the
 * embedded options/explanation, and return the stem only. Idempotent.
 */
export function sanitizeQuestionText(text: string | null | undefined): string {
    if (!text) return '';
    let t = stripRawHtml(decodeMojiB(String(text)));

    // Strip trailer / promo lines.
    for (const [pattern, replacement] of TRAILER_PATTERNS) {
        t = t.replace(pattern, replacement);
    }

    // Drop everything from the first "Answer: X" line onward (the answer
    // key + any explanation that snuck in).
    const answerIdx = t.search(ANSWER_LINE);
    if (answerIdx >= 0) {
        t = t.slice(0, answerIdx);
    }

    // Drop everything from the first standalone "Explanation:" line onward.
    const explIdx = t.search(EXPL_START_LINE);
    if (explIdx >= 0) {
        t = t.slice(0, explIdx);
    }

    // Drop a same-line "Explanation: blah" tail.
    t = t.replace(EXPL_INLINE_LINE, '');

    // Drop embedded options A./B./C./D. — find the first A. line, and
    // truncate there. The backend has these in dedicated columns.
    const lines = t.split('\n');
    let aIdx = -1;
    for (let i = 0; i < lines.length; i++) {
        const m = lines[i].match(OPTION_LINE);
        if (m && m[1].toUpperCase() === 'A') {
            aIdx = i;
            break;
        }
    }
    if (aIdx >= 0) {
        // Keep the stem, drop the options block.
        lines.length = aIdx;
    }
    t = lines.join('\n');

    // Collapse 3+ blank lines.
    t = t.replace(/\n{3,}/g, '\n\n');
    return t.trim();
}

/**
 * Sanitize an option column value. Strips trailers; if the entire value is
 * just a trailer/footer line, returns an empty string so the option row
 * is hidden by the renderer's `if (!optionText) return null` guard.
 */
export function sanitizeOptionText(text: string | null | undefined): string {
    if (!text) return '';
    let t = decodeMojiB(String(text));
    for (const [pattern, replacement] of TRAILER_PATTERNS) {
        t = t.replace(pattern, replacement);
    }
    t = stripRawHtml(t);
    return t.trim();
}

/**
 * If a string looks like it contains a JSON-encoded AI explanation,
 * try to extract the readable "analysis" markdown from it.
 * Returns the original string if it's not JSON or has no analysis key.
 */
export function extractAnalysisFromJson(text: any): string {
    if (!text) return "";
    
    // If it's already an object (e.g., parsed by Axios or Next.js)
    if (typeof text === 'object') {
        if (text.analysis && typeof text.analysis === 'string') {
            return text.analysis;
        }
        // Try structured format fallback
        const parts: string[] = [];
        if (text.core_concept) parts.push(`**Core concept:** ${text.core_concept}`);
        if (text.why_correct) parts.push(`**Why correct:** ${text.why_correct}`);
        if (text.why_wrong) parts.push(`**Why wrong:** ${text.why_wrong}`);
        if (text.clinical_pearl) parts.push(`**Clinical pearl:** ${text.clinical_pearl}`);
        if (text.mnemonic) parts.push(`**Mnemonic:** ${text.mnemonic}`);
        if (parts.length > 0) return parts.join('\n\n');
        
        // Final fallback: just stringify it so it isn't [object Object]
        try { return JSON.stringify(text, null, 2); } catch { return ""; }
    }

    if (typeof text !== 'string') text = String(text);
    const trimmed = text.trim();
    if (!trimmed.startsWith('{')) return text;
    try {
        const parsed = JSON.parse(trimmed);
        // ExplainQuestionView format: {"analysis": "<markdown>", "context": {...}}
        if (parsed.analysis && typeof parsed.analysis === 'string') {
            return parsed.analysis;
        }
        // Structured format: stitch known fields
        const parts: string[] = [];
        if (parsed.core_concept) parts.push(`**Core concept:** ${parsed.core_concept}`);
        if (parsed.why_correct) parts.push(`**Why correct:** ${parsed.why_correct}`);
        if (parsed.why_wrong) parts.push(`**Why wrong:** ${parsed.why_wrong}`);
        if (parsed.clinical_pearl) parts.push(`**Clinical pearl:** ${parsed.clinical_pearl}`);
        if (parsed.mnemonic) parts.push(`**Mnemonic:** ${parsed.mnemonic}`);
        if (parts.length > 0) return parts.join('\n\n');
    } catch {
        // Not JSON — return as-is
    }
    return text;
}

// Recognised admin-side placeholder strings stored in `ai_explanation`,
// `ai_answer`, and `ai_mnemonic` by the `force-regenerate` admin endpoint
// when those fields weren't already populated. Mirrors the list in
// `backend/questions/serializers.py::_parse_ai_explanation_to_markdown`.
const ADMIN_AI_PLACEHOLDER_PATTERNS: RegExp[] = [
    /regenerated ai explanation placeholder/i,
    /regenerated mnemonic for question/i,
    /regenerated answer for question/i,
];

/**
 * Returns the trimmed string when it contains real AI content, or an empty
 * string when the input is empty / only whitespace / matches one of the
 * admin-side placeholder strings (e.g. "Regenerated AI explanation
 * placeholder."). Used by the NEET-PG / INI-CET players to fall back to
 * their "tap the AI Tutor button" hint instead of rendering a placeholder
 * as if it were a real explanation.
 */
export function nonPlaceholderExplanation(text: string | null | undefined): string {
    if (!text || typeof text !== "string") return "";
    const trimmed = text.trim();
    if (!trimmed) return "";
    for (const re of ADMIN_AI_PLACEHOLDER_PATTERNS) {
        if (re.test(trimmed)) return "";
    }
    return trimmed;
}

// ---------------------------------------------------------------------------
// Defence-in-depth: extract leaked options from a recall question whose
// `option_a..d` columns are empty but whose `question_text` still contains
// the embedded options block. Some Medical-Junction / NEET PG recall PDFs
// were imported with the full PDF block stuffed into `question_text` and
// the dedicated columns left blank. Until the cleanup script runs against
// the entire corpus, the frontend must still render a solvable question.
//
// `extractLeakedOptions(text)` returns:
//   - `stem`: the cleaned question stem (without the leaked options/answer)
//   - `options`: { A, B, C, D } if a complete 4-option block was found, else null
//   - `correctAnswer`: leaked single letter (A/B/C/D) if found, else null
//   - `optionLabels`: the labels to render on the buttons (e.g. ["1", "2", "3", "4"])
//                     — empty string when the leak uses bare letters A-D.
//
// Recognised shapes (whitespace/separator-flexible):
//   "A. foo  B. bar  C. baz  D. qux"
//   "1. foo  2. bar  3. baz  4. qux"
//   "1 and 2 only" / "2 and 3 only" / "1, 2 and 3" (free-text style)
//
// Also recognises "Answer: X" / "Answer-X" / "Answer <X: …" answer leaks.
// ---------------------------------------------------------------------------

export interface LeakedOptions {
    stem: string;
    options: { A: string; B: string; C: string; D: string } | null;
    correctAnswer: string | null;
    optionLabels: string[];
}

// Matches a single option line at the start of a (trimmed) line. Accepts:
//   "A. foo" / "A) foo" / "(A) foo" / "A - foo" / "A: foo"
const LETTER_OPT = /^\s*\(?([A-Da-d])\)?\s*[\.\)\:\-]\s+(.+?)\s*$/;
// Matches a numbered option line: "1. foo" / "1) foo" / "(1) foo"
const NUMBER_OPT = /^\s*\(?([1-4])\)?\s*[\.\)\:\-]\s+(.+?)\s*$/;

/**
 * Walk every non-empty line of the input and bucket them into A/B/C/D
 * depending on which kind of label the line starts with. Returns null when
 * fewer than 4 lines match (gives up — the embedded text isn't a clean
 * leaked-options block).
 */
function bucketByLabels(lines: string[]): { A: string; B: string; C: string; D: string } | null {
    const out: Partial<Record<'A' | 'B' | 'C' | 'D', string>> = {};
    let labelKind: 'letter' | 'number' | null = null;
    for (const raw of lines) {
        const line = raw.trim();
        if (!line) continue;
        const lm = line.match(LETTER_OPT);
        if (lm) {
            if (labelKind && labelKind !== 'letter') return null;
            labelKind = 'letter';
            const L = lm[1].toUpperCase() as 'A' | 'B' | 'C' | 'D';
            // First-write wins — protects against duplicate label lines.
            if (!out[L]) out[L] = lm[2].trim();
            continue;
        }
        const nm = line.match(NUMBER_OPT);
        if (nm) {
            if (labelKind && labelKind !== 'number') return null;
            labelKind = 'number';
            const n = parseInt(nm[1], 10) - 1;
            const L = (['A', 'B', 'C', 'D'] as const)[n];
            if (!out[L]) out[L] = nm[2].trim();
            continue;
        }
        // A line without a label, while we still have unmatched options, is
        // treated as a continuation of the previous option (multi-line
        // options happen — e.g. "1.  \n  Emphysema  \n  2. ...").
        if (labelKind && (out.A || out.B || out.C || out.D)) {
            const last = (['A', 'B', 'C', 'D'] as const).slice().reverse().find(k => out[k]);
            if (last) out[last] = `${out[last]} ${line}`.trim();
        }
    }
    if (!out.A || !out.B || !out.C || !out.D) return null;
    return out as { A: string; B: string; C: string; D: string };
}

/**
 * Some recall rows put the options on a single line: "1 and 2 only  2 and
 * 3 only  1 and 3 only  1, 2 and 3". We detect this by counting "1"/"2"/"3"/"4"
 * tokens separated by 2+ spaces or newlines.
 */
function parseFreeTextOptions(text: string): { A: string; B: string; C: string; D: string } | null {
    // Split on lines OR 2+ spaces. The recall blocks render options on
    // separate lines, but PDFs sometimes collapse them.
    const parts = text.split(/\n|\s{2,}(?=[1234]\s)/).map(p => p.trim()).filter(Boolean);
    if (parts.length < 4) return null;
    // Heuristic: first 4 distinct short parts (<80 chars) are the options.
    const candidates = parts.slice(0, 4);
    if (candidates.some(p => p.length > 80)) return null;
    // Each candidate must reference at least one of 1/2/3/4 — pulls junk
    // (e.g. "Select the correct answer using the code given below:") out.
    if (!candidates.every(p => /\b[1234]\b/.test(p))) return null;
    return {
        A: decodeMojiB(candidates[0]),
        B: decodeMojiB(candidates[1]),
        C: decodeMojiB(candidates[2]),
        D: decodeMojiB(candidates[3]),
    };
}

export function extractLeakedOptions(text: string | null | undefined): LeakedOptions {
    const empty: LeakedOptions = { stem: '', options: null, correctAnswer: null, optionLabels: [] };
    if (!text) return empty;

    let t = decodeMojiB(String(text));

    // Pull a leaked answer first — works whether the answer is on its own
    // line ("Answer: D") or inline mid-paragraph ("Answer <A: ...").
    let correctAnswer: string | null = null;
    const lineMatch = t.match(ANSWER_LINE);
    if (lineMatch) correctAnswer = lineMatch[1].toUpperCase();
    if (!correctAnswer) {
        const inlineMatch = t.match(ANSWER_INLINE);
        if (inlineMatch) correctAnswer = inlineMatch[1].toUpperCase();
    }
    // Drop everything from any "Answer:" leak onward so the parser below
    // doesn't see the answer letter as a stray option label.
    if (correctAnswer) {
        const li = t.search(ANSWER_LINE);
        if (li >= 0) t = t.slice(0, li);
        t = t.replace(ANSWER_INLINE, '').trim();
    }

    // Drop trailers as well — they're noise to the parser.
    for (const [pattern] of TRAILER_PATTERNS) {
        t = t.replace(pattern, '');
    }
    // Drop the "Select the correct answer using the code given below:" hint
    // that always precedes free-text options blocks.
    // NOTE: TS 5.9's parser misreads both `(?im)` flag-groups and `(?:` /
    // `(?:)` non-capturing groups as ternary expressions and emits TS1005
    // (':' expected). We therefore construct this via `new RegExp(...)`
    // and use a capturing group instead of `(?:...)`. The captured group
    // is destructured for nothing.
    const SELECT_HINT_RE = new RegExp(
        '^\\s*(Select\\s+the\\s+correct\\s+answer[^\\n]*|Code\\s*:[^\\n]*|List\\s+of\\s+options[^\\n]*)$',
        'im',
    );
    const selectMatch = t.match(SELECT_HINT_RE);
    let stemFromDelimiter: string | null = null;
    let tailAfterDelimiter: string | null = null;
    if (selectMatch && typeof selectMatch.index === 'number') {
        const splitAt = selectMatch.index;
        stemFromDelimiter = t.slice(0, splitAt).trim();
        tailAfterDelimiter = t.slice(splitAt + selectMatch[0].length).trim();
    }

    // ── Strategy 1: clean lettered/numbered blocks (A. foo / 1. foo). ──
    // Apply to the tail if we have a delimiter; otherwise to the whole text.
    const forLabelParse = tailAfterDelimiter ?? t;
    const lineBucketed = bucketByLabels(forLabelParse.split('\n'));
    if (lineBucketed) {
        const stemSource = stemFromDelimiter ?? t.split('\n').filter(raw => {
            const line = raw.trim();
            if (!line) return true;
            return !line.match(LETTER_OPT) && !line.match(NUMBER_OPT);
        }).join('\n');
        const stem = stemSource.replace(/\n{3,}/g, '\n\n').trim();
        const labels = lineBucketed.A.match(LETTER_OPT) ? ['A', 'B', 'C', 'D'] : ['1', '2', '3', '4'];
        return { stem, options: lineBucketed, correctAnswer, optionLabels: labels };
    }

    // ── Strategy 2: free-text options ("1 and 2 only" / "2 and 3 only" …).
    // Apply to the tail (post-Select-the-correct-answer block) when a
    // delimiter exists — this is the common recall shape where the stem
    // contains its own numbered indicators (1./2./3.) and the options
    // block is the 4 trailing short lines.
    if (tailAfterDelimiter !== null) {
        const ft = parseFreeTextOptions(tailAfterDelimiter);
        if (ft) {
            const stem = (stemFromDelimiter ?? '').replace(/\n{3,}/g, '\n\n').trim();
            return { stem, options: ft, correctAnswer, optionLabels: ['1', '2', '3', '4'] };
        }
    }

    // ── Strategy 2b: 4 trailing unlabelled lines after a delimiter. The
    // Medical-Junction recall dump often renders options as plain text
    // (no A./1. prefix), one per line, immediately after the question
    // stem. We grab the *last* 4 non-empty lines of the post-delimiter
    // tail as A/B/C/D in order.
    if (tailAfterDelimiter !== null) {
        const tailLines = tailAfterDelimiter.split('\n').map(l => l.trim()).filter(Boolean);
        if (tailLines.length >= 4) {
            const last4 = tailLines.slice(-4);
            if (last4.every(l => l.length > 1 && l.length < 120)) {
                const ft = {
                    A: decodeMojiB(last4[0]),
                    B: decodeMojiB(last4[1]),
                    C: decodeMojiB(last4[2]),
                    D: decodeMojiB(last4[3]),
                };
                // Pull those 4 lines out of the tail to keep the stem clean.
                const stemLines = tailAfterDelimiter.split('\n').filter(l => !last4.includes(l.trim()));
                const stem = ((stemFromDelimiter ?? '') + '\n' + stemLines.join('\n')).replace(/\n{3,}/g, '\n\n').trim();
                return { stem, options: ft, correctAnswer, optionLabels: ['A', 'B', 'C', 'D'] };
            }
        }
    }

    // ── Strategy 3: free-text options embedded in the whole text (no delimiter).
    const freeText = parseFreeTextOptions(t);
    if (freeText) {
        const stem = t.split(/\n/).filter(l => {
            const trimmed = l.trim();
            if (!trimmed) return true;
            return !(/\b[1234]\b/.test(trimmed) && trimmed.length < 80);
        }).join('\n').replace(/\n{3,}/g, '\n\n').trim();
        return { stem, options: freeText, correctAnswer, optionLabels: ['1', '2', '3', '4'] };
    }

    // ── Strategy 3b: 4 unlabelled trailing lines, no delimiter. The
    // Medical-Junction recall dump often renders options as plain text
    // (no A./1. prefix), one per line, immediately after the question
    // stem. We grab the last 4 non-empty lines as A/B/C/D in order.
    {
        const allLines = t.split('\n').map(l => l.trim()).filter(Boolean);
        if (allLines.length >= 4) {
            const last4 = allLines.slice(-4);
            if (last4.every(l => l.length > 1 && l.length < 120)) {
                const ft = {
                    A: decodeMojiB(last4[0]),
                    B: decodeMojiB(last4[1]),
                    C: decodeMojiB(last4[2]),
                    D: decodeMojiB(last4[3]),
                };
                const stem = allLines.slice(0, -4).join('\n').replace(/\n{3,}/g, '\n\n').trim();
                return { stem, options: ft, correctAnswer, optionLabels: ['A', 'B', 'C', 'D'] };
            }
        }
    }

    return { stem: t.trim(), options: null, correctAnswer, optionLabels: [] };
}
