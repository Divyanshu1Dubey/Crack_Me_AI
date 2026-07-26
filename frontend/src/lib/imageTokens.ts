/**
 * Resolves `[[img:N]]` tokens inside question text into `<img>` tags.
 *
 * Used by the public practice pages and the admin editor preview. The
 * resolver is cached per `(questionId, imagesHash)` so re-renders are
 * cheap. Missing ids render an inline placeholder so the admin can
 * spot and re-upload them.
 */

export interface QuestionImageLike {
  id: number;
  url?: string | null;
  file?: string | null;
  mime?: string;
  width?: number;
  height?: number;
  caption?: string | null;
}

const TOKEN_RE = /\[\[img:(\d+)\]\]/g;
const cache = new Map<string, string>();

export function imagesHash(images: QuestionImageLike[]): string {
  return images.map((i) => `${i.id}:${i.url ?? i.file ?? ''}`).join('|');
}

export function resolveImageTokens(
  html: string,
  images: QuestionImageLike[],
  cacheKey?: string,
): string {
  const key = cacheKey ?? `__anon__:${imagesHash(images)}`;
  const cached = cache.get(key);
  if (cached !== undefined) return cached;

  const byId = new Map(images.map((i) => [i.id, i]));

  const resolved = html.replace(TOKEN_RE, (_match, idStr: string) => {
    const id = parseInt(idStr, 10);
    const img = byId.get(id);
    if (!img) {
      if (typeof console !== 'undefined') {
        console.warn(`[imageTokens] missing image #${id}`);
      }
      return `<span class="missing-image-placeholder" data-missing-image-id="${id}">[missing image #${id}]</span>`;
    }
    const src = (img.url || img.file) ?? '';
    const alt = (img.caption || `Question image ${id}`).replace(/"/g, '&quot;');
    const widthAttr = img.width ? ` width="${img.width}"` : '';
    const heightAttr = img.height ? ` height="${img.height}"` : '';
    return `<img src="${src}" alt="${alt}"${widthAttr}${heightAttr} loading="lazy" class="question-inline-image" />`;
  });

  cache.set(key, resolved);
  return resolved;
}

export function clearImageTokenCache(): void {
  cache.clear();
}
