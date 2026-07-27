import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import rehypeRaw from 'rehype-raw';
import { decodeMojiB } from '@/lib/textCleanup';

interface FormattedTextProps {
    text: string;
    className?: string;
}

/**
 * Renders medical question text with proper formatting.
 * Uses remark-breaks to honor line breaks exactly as typed in the admin panel.
 *
 * Also decodes UTF-8 mojibake so text originally stored with double-encoded
 * punctuation ("ΓÇÿ", "ΓÇÖ", etc.) renders correctly.
 *
 * Custom admin tokens resolved before markdown:
 *   `[[red]]foo[[/red]]`  → `<span style="color:#dc2626">foo</span>`
 *   `[[u]]foo[[/u]]`      → `<span style="text-decoration:underline">foo</span>`
 * `rehype-raw` lets the inline `<span style="…">` survive into the DOM so
 * the colour / underline actually renders (react-markdown v10 strips raw
 * HTML by default).
 */
export function FormattedText({ text, className = '' }: FormattedTextProps) {
    if (!text) return null;

    const clean = decodeMojiB(applyColorTokens(text));

    return (
        <div className={`formatted-text ${className}`}>
            <ReactMarkdown remarkPlugins={[remarkBreaks]} rehypePlugins={[rehypeRaw]}>
                {clean}
            </ReactMarkdown>
        </div>
    );
}

/**
 * Rewrites the admin's `[[red]]…[[/red]]` and `[[u]]…[[/u]]` tokens into
 * inline `<span style="…">…</span>` so `react-markdown` + `rehype-raw`
 * render them as styled DOM elements.
 *
 * Note: we emit *inline* HTML inside a string that flows into markdown.
 * `[[red]]` is paired with the matching `[[/red]]` on the same line / block;
 * nesting is not supported (would need a parser, not a regex) but admin
 * usage is flat.
 */
export function applyColorTokens(text: string): string {
    if (!text) return '';
    return text
        // Red highlight. Style matches Tailwind's text-red-600 so it survives
        // both the markdown preview and the student-side render.
        .replace(/\[\[red\]\]([\s\S]*?)\[\[\/red\]\]/g, (_m, inner: string) => {
            const safe = String(inner).replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return `<span style="color:#dc2626;font-weight:600">${safe}</span>`;
        })
        // Underline.
        .replace(/\[\[u\]\]([\s\S]*?)\[\[\/u\]\]/g, (_m, inner: string) => {
            const safe = String(inner).replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return `<span style="text-decoration:underline">${safe}</span>`;
        });
}

/**
 * Renders `text` where `[[img:N]]` tokens resolve to markdown image syntax
 * (`![alt](src)`) so `react-markdown` picks them up. Use this for any text
 * field that is run through `FormattedText` (explanations, mnemonics, etc.)
 * so admin-uploaded images render inline.
 *
 * Two token shapes are accepted:
 *   - `[[img:42]]` — looks up QuestionImage id=42 in `images`
 *   - `[[img:https://…/foo.png]]` — legacy/supabase-url form (older mocktest
 *     imports stored the full URL as the token value). Falls through to
 *     `![alt](url)` so the image still renders even when no QuestionImage row
 *     was joined. Defence-in-depth: the proper fix is the
 *     `rewrite_url_image_tokens.py` one-shot cleanup that converts these to
 *     integer IDs.
 */
export function resolveImageTokensForMarkdown(
    text: string,
    images?: Array<{ id: number; url?: string | null; file?: string | null; caption?: string | null }>,
): string {
    if (!text) return '';
    // Apply color tokens first so they flow through to react-markdown.
    // Order matters: if we ran image resolution first, the inner-text of an
    // `![alt](src)` could swallow a stray `[[red]]` and confuse the regex.
    const withColors = applyColorTokens(text);
    const byId = new Map((images ?? []).map((i) => [i.id, i]));
    // Match either an integer ID or a URL inside the brackets. Order: try ID
    // first (most common) — the regex alternation handles both in one pass.
    return withColors.replace(/\[\[img:([^\]]+)\]\]/g, (match, payload: string) => {
        // Integer ID — canonical form, looks up QuestionImage row.
        if (/^\d+$/.test(payload)) {
            const id = parseInt(payload, 10);
            const img = byId.get(id);
            if (!img) return `*[missing image #${id}]*`;
            const src = (img.url || img.file || '').replace(/"/g, '%22');
            const alt = (img.caption || `image #${id}`).replace(/\]/g, '');
            return `![${alt}](${src})`;
        }
        // URL payload — render directly. Re-encode embedded quotes so the
        // markdown parser doesn't choke on URLs containing spaces / quotes.
        if (/^https?:\/\//i.test(payload)) {
            const src = payload.replace(/"/g, '%22');
            return `![image](${src})`;
        }
        // Alphanumeric / arbitrary token — defence-in-depth fallback: render
        // as a broken-link placeholder so the user sees an icon instead of
        // raw `[[img:foo]]` text. This handles older cms_exclusive_material
        // imports where the docx used short IDs (e.g. "r1d35") that never
        // matched QuestionImage rows.
        return `*[image: ${payload} unavailable]*`;
    });
}

/**
 * Renders option / short text where markdown is overkill: just preserves
 * line breaks and resolves `[[img:N]]` tokens to inline images. Used by the
 * question options and any other field where markdown would be more
 * confusing than helpful.
 *
 * `images` is the list of `QuestionImage` rows loaded with the question.
 */
export function FormattedOptionText({
    text,
    images,
    className = '',
}: {
    text: string;
    images?: Array<{ id: number; url?: string | null; file?: string | null; caption?: string | null }>;
    className?: string;
}) {
    if (!text) return null;
    const clean = decodeMojiB(text);
    const byId = new Map((images ?? []).map((i) => [i.id, i]));
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    // Match integer ID OR URL payload — same shape as resolveImageTokensForMarkdown.
    const tokenRe = /\[\[img:(\d+|https?:\/\/[^\]]+)\]\]/g;
    let match: RegExpExecArray | null;
    let key = 0;
    while ((match = tokenRe.exec(clean)) !== null) {
        if (match.index > lastIndex) {
            parts.push(
                <span key={key++} className="whitespace-pre-wrap">{clean.slice(lastIndex, match.index)}</span>
            );
        }
        const payload = match[1];
        if (/^\d+$/.test(payload)) {
            const id = parseInt(payload, 10);
            const img = byId.get(id);
            if (img) {
                const src = img.url || img.file || '';
                parts.push(
                    <img
                        key={key++}
                        src={src}
                        alt={img.caption || `image #${id}`}
                        loading="lazy"
                        className="question-inline-image inline-block max-w-full h-auto my-1 rounded border"
                    />
                );
            } else {
                parts.push(
                    <span key={key++} className="missing-image-placeholder italic text-amber-700">
                        [missing image #{id}]
                    </span>
                );
            }
        } else if (/^https?:\/\//i.test(payload)) {
            // URL payload — render directly so legacy [[img:https://…]] tokens
            // still produce an <img> instead of leaking raw text.
            parts.push(
                <img
                    key={key++}
                    src={payload}
                    alt="Question image"
                    loading="lazy"
                    className="question-inline-image inline-block max-w-full h-auto my-1 rounded border"
                />
            );
        } else {
            // Alphanumeric / arbitrary token — render as a placeholder so the
            // user sees an explanatory marker instead of raw `[[img:foo]]`.
            parts.push(
                <span key={key++} className="missing-image-placeholder italic text-amber-700">
                    [image: {payload} unavailable]
                </span>
            );
        }
        lastIndex = match.index + match[0].length;
    }
    if (lastIndex < clean.length) {
        parts.push(
            <span key={key++} className="whitespace-pre-wrap">{clean.slice(lastIndex)}</span>
        );
    }
    return <span className={`formatted-option-text ${className}`}>{parts}</span>;
}

/**
 * Strips markdown symbols for plain-text previews (list cards, etc.).
 * Also decodes mojibake so the preview shows real punctuation.
 */
export function stripMarkdown(text: string): string {
    if (!text) return '';
    return decodeMojiB(text)
        .replace(/\*\*(.+?)\*\*/g, '$1')
        .replace(/\*(.+?)\*/g, '$1')
        .replace(/`(.+?)`/g, '$1')
        .replace(/!\[.*?\]\(.*?\)/g, '')
        .replace(/\[(.+?)\]\(.*?\)/g, '$1')
        .replace(/#/g, '')
        .trim();
}
