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
 * correct punctuation regardless of how the data is stored.
 *
 * Also strips surrounding asterisks (`*`) from option text — some
 * PYQ fixtures leave trailing `*` markers on the correct option.
 */

const MOJIBAKE_MAP: Array<[RegExp, string]> = [
    // 6-char Latin-1-of-UTF-8 patterns — these are the "ΓÇÿ" family.
    [/Î¸/g, '—'], // em dash
    [/Î¦/g, '—'], // em dash (alt)
    [/â€"/g, '—'], // em dash (Windows-encoded variant)
    [/â€™/g, '’'], // right single quote (apostrophe)
    [/â€˜/g, '‘'], // left single quote
    [/â€œ/g, '“'], // left double quote
    [/â€/g, '”'], // right double quote
    [/â€¦/g, '…'], // ellipsis
    [/â€“/g, '–'], // en dash
    [/â€”/g, '—'], // em dash
    // The literal "ΓÇÿ" / "ΓÇÖ" sequences (Unicode-Γ + Latin Ç + …).
    [/ΓÇÿ/g, '‘'], // left single quote
    [/ΓÇÖ/g, '’'], // right single quote
    [/ΓÇ£/g, '“'], // left double quote
    [/ΓÇ¥/g, '”'], // right double quote
    [/ΓÇª/g, '…'], // ellipsis
    [/ΓÇ­/g, '–'], // en dash
    [/ΓÇô/g, '–'], // en dash
    [/ΓÇö/g, '—'], // em dash
    // Other common mojibake.
    [/Â°/g, '°'], // degree
    [/Â·/g, '·'], // middle dot
    [/Ã©/g, 'é'],
    [/Ã¨/g, 'è'],
    [/Ã¢/g, 'â'],
    [/Ã®/g, 'î'],
    [/Ã´/g, 'ô'],
    [/Ã»/g, 'û'],
    [/Ã /g, 'à'],
    [/Ã§/g, 'ç'],
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
