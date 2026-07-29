"use client";
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import rehypeRaw from 'rehype-raw';
import { decodeMojiB } from '@/lib/textCleanup';

interface FormattedTextProps {
    text: string;
    className?: string;
}

/**
 * `<img>` component used by `<FormattedText>` that swaps a broken image
 * for an explanatory placeholder the moment the load fails. Replaces
 * the browser's silent broken-icon behaviour with a meaningful
 * "image unavailable: <alt>" message so the student immediately sees
 * what went wrong (vs. an unexplained blank rectangle or icon).
 *
 * The fallback is rendered via React state — not by mutating the DOM
 * imperatively from inside `onError` — so React's reconciler stays in
 * the loop and re-renders cleanly without undoing our swap.
 */
function ImgWithFallback({ src, alt, ...rest }: any) {
    const [failed, setFailed] = useState(false);
    if (failed) {
        const base = (alt && typeof alt === 'string') ? alt : 'image';
        return (
            <span className="missing-image-placeholder italic text-amber-700">
                [image unavailable: {base}]
            </span>
        );
    }
    return (
        <img
            src={src}
            alt={alt ?? ''}
            loading="lazy"
            className="question-inline-image"
            onError={() => setFailed(true)}
            {...rest}
        />
    );
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

    // Collapse horizontal whitespace (tabs, runs of spaces) to a single space
    // so CommonMark inline-emphasis rules (`**Foo\tbar**` is invalid, since
    // the `**` must abut non-whitespace) actually parse. The recall importer
    // and docx copy-pastes leave literal `\t` characters in the DB which
    // silently disable bold/italic/links. We do NOT touch newlines — those
    // carry paragraph + list semantics that `react-markdown` + remark-breaks
    // need.
    const normalized = text.replace(/[ \t\f\v]+/g, ' ');
    const clean = decodeMojiB(applyColorTokens(normalized));

    return (
        <div className={`formatted-text ${className}`}>
            <ReactMarkdown
                remarkPlugins={[remarkBreaks]}
                rehypePlugins={[rehypeRaw]}
                components={{
                    // Bug 2026-07-28: wire an `onError` on every `<img>`
                    // emitted by react-markdown so a missing/broken
                    // image renders an explanatory placeholder span
                    // instead of the browser's silent broken-image
                    // icon. Recurring image-not-rendering audit bug —
                    // closed at the UI layer even when the backend
                    // relink pass can't find the file on disk.
                    img: ImgWithFallback,
                }}
            >
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
 * Three token shapes are accepted:
 *   - `[[img:42]]` — looks up QuestionImage id=42 in `images`
 *   - `[[img:https://…/foo.png]]` — legacy/supabase-url form (older mocktest
 *     imports stored the full URL as the token value). Falls through to
 *     `![alt](url)` so the image still renders even when no QuestionImage row
 *     was joined. Defence-in-depth: the proper fix is the
 *     `rewrite_url_image_tokens.py` one-shot cleanup that converts these to
 *     integer IDs.
 *
 * Also recognises a *bare* `/media/fixtures/images/<exam>/<file>.png` URL
 * that the legacy `load_exam_fixture` loader rewrote into question_text.
 * This is the canonical mojibake-adjacent bug: the URL renders as plain
 * text instead of an `<img>`. We convert it to a markdown image so the
 * student sees the figure, preferring the canonical `serve_url` when we
 * can match the file basename to a QuestionImage row. The proper fix is
 * a one-shot backend migration (`rewrite_url_image_tokens.py` /
 * `relink_fixture_images.py`) that converts these to integer IDs.
 */
export function resolveImageTokensForMarkdown(
    text: string,
    images?: Array<{ id: number; url?: string | null; file?: string | null; caption?: string | null }>,
): string {
    if (!text) return '';
    // Normalise horizontal whitespace so `**Foo<TAB>bar**` parses as bold.
    // Same reason as in `<FormattedText>` — CommonMark requires non-whitespace
    // immediately after the opening `**` and before the closing `**`.
    const normalized = text.replace(/[ \t\f\v]+/g, ' ');
    // Apply color tokens first so they flow through to react-markdown.
    // Order matters: if we ran image resolution first, the inner-text of an
    // `![alt](src)` could swallow a stray `[[red]]` and confuse the regex.
    const withColors = applyColorTokens(normalized);
    const byId = new Map((images ?? []).map((i) => [i.id, i]));
    // Build a basename → image lookup so we can resolve a bare
    // `/media/fixtures/images/<exam>/<file>.png` URL to a QuestionImage
    // row when one exists.
    const byBasename = new Map<string, { id: number; url?: string | null; file?: string | null; caption?: string | null }>();
    for (const img of images ?? []) {
        const ref = (img.file || img.url || '').toString();
        if (!ref) continue;
        const base = ref.split('?')[0].split('#')[0].split('/').pop() || '';
        if (base) byBasename.set(base.toLowerCase(), img);
    }

    // First pass: token-form `[[img:…]]`.
    let resolved = withColors.replace(/\[\[img:([^\]]+)\]\]/g, (match, payload: string) => {
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

    // Second pass: bare `/media/fixtures/images/...` URLs (legacy
    // load_exam_fixture output). We still match the alternation above so
    // tokens inside attribute strings get handled — but bare URLs sit
    // outside any bracket syntax, so we do a separate pass.
    //
    // When no matching QuestionImage row exists for the basename, we
    // still emit a markdown image so the `<FormattedText>` `onerror`
    // handler (registered via `components.img` above) fires and shows
    // a visible "image unavailable" placeholder instead of the raw
    // URL leaking through. This is the recurrence-mode fix for the
    // screenshot bug — even when the auto-heal hasn't run, or when
    // the file is genuinely missing from disk, the student sees a
    // meaningful message instead of a broken image icon.
    resolved = resolved.replace(
        /(\/media\/fixtures\/images\/[^\s)\]]+|https?:\/\/[^\s)\]]*\/fixtures\/images\/[^\s)\]]+)/g,
        (rawUrl) => {
            const stripped = rawUrl.split('?')[0].split('#')[0];
            const base = stripped.split('/').pop() || '';
            const found = byBasename.get(base.toLowerCase());
            const served = found
                ? ((found.url && found.url.length > 0 ? found.url : null) ||
                   `/api/questions/images/${found.id}/serve/`)
                : rawUrl;
            const alt = (found?.caption || `Question image ${base}`).replace(/[\[\]"]/g, '');
            return `![${alt}](${served.replace(/"/g, '%22')})`;
        },
    );

    // Third pass: `[image unavailable: <basename>]` markers written by the
    // backend's `relink_fixture_images` command when no on-disk file was
    // found for a bare URL. We rewrite these into styled HTML spans so
    // they read as an amber-tinted chip (matching `.missing-image-placeholder`
    // in globals.css) instead of plain text leaking through.
    //
    // Bug 2026-07-28 (recurrence): the first round of this fix left these
    // markers as raw text — `react-markdown` doesn't interpret the square
    // brackets as markdown link syntax (needs `[]()`), so the placeholder
    // rendered as a literal string in the question stem. Converting to a
    // styled `<span>` here closes that loop.
    resolved = resolved.replace(
        /\[image unavailable:\s*([^\]]+)\]/g,
        (_m, basename: string) => {
            const safe = String(basename).trim().replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            return `<span class="missing-image-placeholder" data-image-basename="${safe}">[image unavailable: ${safe}]</span>`;
        },
    );

    return resolved;
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
    const byBasename = new Map<string, { id: number; url?: string | null; file?: string | null; caption?: string | null }>();
    for (const img of images ?? []) {
        const ref = (img.file || img.url || '').toString();
        if (!ref) continue;
        const base = ref.split('?')[0].split('#')[0].split('/').pop() || '';
        if (base) byBasename.set(base.toLowerCase(), img);
    }
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    // Match: 1) integer-ID / URL inside `[[img:…]]` brackets, or 2) a
    // bare `/media/fixtures/images/<exam>/<file>` URL left behind by the
    // legacy loader.
    //
    // We also handle the backend's `[image unavailable: <basename>]`
    // marker here so the placeholder renders as a styled amber chip
    // (matching `.missing-image-placeholder` in globals.css) rather than
    // as literal text in the option card. Bug 2026-07-28 (recurrence):
    // the first round of this fix left these markers as plain text,
    // which is what the screenshot showed.
    const tokenRe = /\[\[img:(\d+|https?:\/\/[^\]]+)\]\]|(\/media\/fixtures\/images\/[^\s)\]]+|https?:\/\/[^\s)\]]*\/fixtures\/images\/[^\s)\]]+)|(\[image unavailable:\s*[^\]]+\])/g;
    let match: RegExpExecArray | null;
    let key = 0;
    const pushImg = (src: string, alt: string, missing?: string) => {
        if (missing) {
            parts.push(
                <span key={key++} className="missing-image-placeholder italic text-amber-700" data-image-basename={alt}>
                    {missing}
                </span>,
            );
        } else {
            parts.push(
                <OptionImgWithFallback
                    key={key++}
                    src={src}
                    alt={alt}
                />,
            );
        }
    };
    const pushMissingMarker = (marker: string) => {
        // Extract basename from `[image unavailable: <basename>]`.
        const m = marker.match(/\[image unavailable:\s*([^\]]+)\]/);
        const base = m ? m[1].trim() : 'image';
        parts.push(
            <span key={key++} className="missing-image-placeholder italic text-amber-700" data-image-basename={base}>
                [image unavailable: {base}]
            </span>,
        );
    };
    while ((match = tokenRe.exec(clean)) !== null) {
        if (match.index > lastIndex) {
            parts.push(
                <span key={key++} className="whitespace-pre-wrap">{clean.slice(lastIndex, match.index)}</span>
            );
        }
        // Branch 1: `[[img:…]]` token.
        if (match[1] !== undefined) {
            const payload = match[1];
            if (/^\d+$/.test(payload)) {
                const id = parseInt(payload, 10);
                const img = byId.get(id);
                if (img) {
                    pushImg(img.url || img.file || '', img.caption || `image #${id}`);
                } else {
                    pushImg('', '', `[missing image #${id}]`);
                }
            } else if (/^https?:\/\//i.test(payload)) {
                pushImg(payload, 'Question image');
            } else {
                pushImg('', '', `[image: ${payload} unavailable]`);
            }
        } else if (match[3] !== undefined) {
            // Branch 3: `[image unavailable: <basename>]` marker left by
            // the backend's relink pass. Render as a styled placeholder
            // (matches `.missing-image-placeholder` in globals.css).
            pushMissingMarker(match[3]);
        } else {
            // Branch 2: bare `/media/fixtures/images/...` URL. Resolve via
            // basename → QuestionImage lookup when possible; otherwise
            // render the raw URL with an onerror fallback so the user
            // sees a placeholder instead of a broken image icon.
            const rawUrl = match[2];
            const base = (rawUrl.split('?')[0].split('#')[0].split('/').pop() || '').toLowerCase();
            const found = byBasename.get(base);
            if (found) {
                const served = (found.url && found.url.length > 0 ? found.url : null) ||
                               `/api/questions/images/${found.id}/serve/`;
                pushImg(served, found.caption || `Question image ${base}`);
            } else {
                pushImg(
                    rawUrl,
                    `Question image ${base}`,
                );
            }
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
 * `<img>` component used by `<FormattedOptionText>` — same fallback
 * shape as `ImgWithFallback` but inlined here so the option-card
 * styling (rounded border, `inline-block`) survives intact.
 */
function OptionImgWithFallback({ src, alt }: { src: string; alt: string }) {
    const [failed, setFailed] = useState(false);
    if (failed) {
        return (
            <span className="missing-image-placeholder italic text-amber-700">
                [image unavailable: {alt || 'image'}]
            </span>
        );
    }
    return (
        <img
            src={src}
            alt={alt || ''}
            loading="lazy"
            className="question-inline-image inline-block max-w-full h-auto my-1 rounded border"
            onError={() => setFailed(true)}
        />
    );
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
        .replace(/\[image unavailable:[^\]]+\]/g, '[image]')
        .replace(/#/g, '')
        .trim();
}
