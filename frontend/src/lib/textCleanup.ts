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
 * Decode double-encoded UTF-8 mojibake so the user sees real
 * punctuation characters (`'`, `'`, `"`, `"`, `—`, `…`) instead of
 * the "ΓÇÿ" garbled sequences. Idempotent — safe to call multiple times.
 */
export function decodeMojiB(text: string): string {
    if (!text) return text;
    let out = text;
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
// ---------------------------------------------------------------------------

const TRAILER_PATTERNS: Array<[RegExp, string]> = [
    // Multi-line patterns — match the full line, possibly after a newline.
    [/(?im)^\s*PDF\s+Compiled\s+by[^\n]*$/g, ''],
    [/(?im)^\s*To\s+Know\s+about\s+our\s+products[^\n]*$/g, ''],
    [/(?im)^\s*https?:\/\/medicoapps\.org[^\n]*$/g, ''],
    [/(?im)^\s*MEDICAL[\s\-]*JUNCTION(?:\.COM)?\s*$/g, ''],
    [/(?im)^\s*MEDICAL\s+JUNCTION\s+TEAM\s*$/g, ''],
    [/(?im)^\s*www\.medical[\-_]?junction\.com[^\n]*$/g, ''],
    [/(?im)^\s*Medicoapps\.org[^\n]*$/g, ''],
    [/(?im)^\s*Medicoapps[^\n]*$/g, ''],
    [/(?im)^\s*Compiled\s+by[^\n]*$/g, ''],
    [/(?im)^\s*For\s+more\s+visit[^\n]*$/g, ''],
    [/(?im)^\s*Also\s+follow\s+us[^\n]*$/g, ''],
    [/(?im)^\s*Follow\s+us\s+on[^\n]*$/g, ''],
    [/(?im)^\s*Join\s+our\s+telegram[^\n]*$/g, ''],
    [/(?im)^\s*Telegram[^\n]*$/g, ''],
    [/(?im)^\s*Disclaimer[^\n]*$/g, ''],
    [/(?im)^\s*Note\s*:[^\n]*$/g, ''],
    [/(?im)^\s*Source\s*:[^\n]*$/g, ''],
    [/(?im)^\s*Image\s+courtesy[^\n]*$/g, ''],
];

// Single-line option marker: "A. xxx" / "A) xxx" / "(A) xxx"
const OPTION_LINE = /^\s*\(?([A-Da-d])\)?[\.\)]\s+(.+?)\s*$/;

// Leaked "Answer: X" / "Answer-X" / "Answer <A: …" line.
const ANSWER_LINE = /^\s*Answer\s*[\-<:>]\s*<?\s*[A-Da-d][^\n]*$/i;
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
    let t = decodeMojiB(String(text));

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
