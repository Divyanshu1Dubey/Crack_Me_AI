/**
 * The address a browser loads for a question figure, and where a figure is shown (2026-11-04).
 *
 * The backend hands out its image endpoint (`/api/questions/images/<id>/serve/`), which serves a
 * figure from wherever this server keeps it. Until 2026-11-04 the question view handed out the
 * stored address of admin uploads instead: a Supabase Storage URL, dead since that host was shut
 * down on 2026-11-03, so those figures showed as broken images and "[image unavailable]".
 * `figureSrc` swaps any such address (an older cached payload, a path that was missed) for the
 * image endpoint, which serves the restored copy.
 *
 * `sidePaneFigures`: a figure the stem already shows inline (`[[img:N]]` where the author put it) is
 * not repeated in the side pane of the question bank.
 *
 * Pure (no React, no DOM): tests/unit/figure-src.test.ts.
 */
import { apiUrl } from './apiBase';

const RETIRED_STORAGE = /^https?:\/\/[^/?#]+\.supabase\.co\/storage\//i;
// `/media/...` (relative or on the API host) is served only by a development server.
const MEDIA_PATH = /^(?:https?:\/\/[^/?#]+)?\/media\//i;
const INLINE_TOKEN = /\[\[img:(\d+)\]\]/g;

export interface FigureLike {
    id?: number | string | null;
    serve_url?: string | null;
    url?: string | null;
    file?: string | null;
    file_url?: string | null;
}

/** True for an address on retired Supabase Storage (never loaded by the browser). */
export function isRetiredStorageUrl(url: unknown): boolean {
    return typeof url === 'string' && RETIRED_STORAGE.test(url.trim());
}

/** The image endpoint of the figure with this id. */
export function figureServeUrl(id: number | string): string {
    return apiUrl(`/questions/images/${id}/serve/`);
}

/** The address to load: the one the API gave (`serve_url` first: admin image rows), unless it is
 *  empty, on retired storage or a `/media/` path and the figure has an id, then the image endpoint. */
export function figureSrc(img: FigureLike | null | undefined): string {
    if (!img) return '';
    const given = String(img.serve_url || img.url || img.file_url || img.file || '').trim();
    const id = Number(img.id);
    if (Number.isInteger(id) && id > 0 && (!given || isRetiredStorageUrl(given) || MEDIA_PATH.test(given))) {
        return figureServeUrl(id);
    }
    // The backend's relative fallback (`/api/...`) belongs to the API host, not this site.
    if (given.startsWith('/api/')) return apiUrl(given.slice('/api'.length));
    return given;
}

/** The address FigureImage retries a failed figure with: the same figure, past a failed response
 *  the browser may have kept. */
export function figureRetryUrl(src: string): string {
    if (!src || src.startsWith('data:') || src.startsWith('blob:')) return src;
    return `${src}${src.includes('?') ? '&' : '?'}retry=1`;
}

/** Ids of the figures `text` shows inline (`[[img:N]]`). */
export function inlineFigureIds(text: string | null | undefined): Set<number> {
    const ids = new Set<number>();
    for (const match of String(text || '').matchAll(INLINE_TOKEN)) ids.add(Number(match[1]));
    return ids;
}

/** The figures for the side pane: those the stem does not already show inline. */
export function sidePaneFigures<T extends { id?: number | string | null }>(
    figures: readonly T[] | null | undefined,
    stemText: string | null | undefined,
): T[] {
    const inline = inlineFigureIds(stemText);
    return (figures || []).filter((figure) => !inline.has(Number(figure.id)));
}
