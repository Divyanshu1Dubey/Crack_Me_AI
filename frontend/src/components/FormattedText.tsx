import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
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
 */
export function FormattedText({ text, className = '' }: FormattedTextProps) {
    if (!text) return null;

    const clean = decodeMojiB(text);

    return (
        <div className={`formatted-text ${className}`}>
            <ReactMarkdown remarkPlugins={[remarkBreaks]}>{clean}</ReactMarkdown>
        </div>
    );
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
    const byId = new Map((images ?? []).map((i) => [i.id, i]));
    // Match either an integer ID or a URL inside the brackets. Order: try ID
    // first (most common) — the regex alternation handles both in one pass.
    return text.replace(/\[\[img:(\d+|https?:\/\/[^\]]+)\]\]/g, (match, payload: string) => {
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
        const src = payload.replace(/"/g, '%22');
        return `![image](${src})`;
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
        } else {
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
