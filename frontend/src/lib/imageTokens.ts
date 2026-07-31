/**
 * Resolves `[[img:N]]` tokens inside question text into `<img>` tags.
 *
 * Used by the public practice pages and the admin editor preview. The
 * resolver is cached per `(questionId, imagesHash)` so re-renders are
 * cheap. Missing ids render an inline placeholder so the admin can
 * spot and re-upload them.
 *
 * Also resolves *bare* `/media/fixtures/images/<exam>/<file>` URLs left
 * behind by older fixture loaders. The canonical form is `[[img:N]]`
 * (resolved via the question's QuestionImage list) but legacy fixtures
 * stored the raw URL path. In production Django, `/media/...` 404s
 * unless DEBUG=True — so the URL must be re-routed through the
 * `/api/questions/images/<id>/serve/` proxy that reads from whichever
 * storage backend is configured. When the question's `images` list
 * includes a matching file, we substitute the proxy URL; otherwise we
 * emit a fallback `<img>` whose `src` points at the (still broken)
 * `/media/...` path so the admin can spot it.
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
// Match `/media/fixtures/images/<anything>/<file>` as a bare URL.
// We accept either `/media/fixtures/...` or an absolute URL whose path
// contains `/fixtures/images/` so QA can spot broken CDNs in tests.
const BARE_MEDIA_RE = /(\/media\/fixtures\/images\/[^"\s)]+|https?:\/\/[^\s")]*\/fixtures\/images\/[^"\s)]+)/g;
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
  // Build a basename → image lookup for the bare-URL fallback path.
  // `file` may be a relative path or a basename, so we match on the
  // final segment.
  const byBasename = new Map<string, QuestionImageLike>();
  for (const img of images) {
    const f = (img.file || img.url || '').toString();
    if (!f) continue;
    const base = f.split('?')[0].split('#')[0].split('/').pop() || '';
    if (base) byBasename.set(base.toLowerCase(), img);
  }

  // First, resolve `[[img:N]]` tokens.
  let resolved = html.replace(TOKEN_RE, (_match, idStr: string) => {
    const id = parseInt(idStr, 10);
    const img = byId.get(id);
    if (!img) {
      if (typeof console !== 'undefined') {
        console.warn(`[imageTokens] missing image #${id}`);
      }
      return `<span class="missing-image-placeholder" data-missing-image-id="${id}">[missing image #${id}]</span>`;
    }
    return _imgTag(img, `Question image ${id}`);
  });

  // Then, resolve any bare `/media/fixtures/images/...` URL left behind
  // by the legacy fixture loader. The right fix is a one-shot backend
  // cleanup that rewrites these to `[[img:N]]`; until that lands, this
  // pass converts the URL into a real `<img>` so the student sees the
  // figure instead of a raw path.
  resolved = resolved.replace(BARE_MEDIA_RE, (rawUrl) => {
    const stripped = rawUrl.split('?')[0].split('#')[0];
    const base = stripped.split('/').pop() || '';
    const found = byBasename.get(base.toLowerCase());
    if (found) {
      // Prefer the canonical QuestionImage — `serve_url` is what the
      // auth-gated proxy will return. Inline `img.url || img.file` as
      // a fallback for environments where the proxy isn't wired up.
      const served =
        (found.url && found.url.length > 0 ? found.url : null) ||
        `/api/questions/images/${found.id}/serve/`;
      const alt = (found.caption || `Question image ${base}`).replace(/"/g, '&quot;');
      return `<img src="${escapeAttr(served)}" alt="${alt}" loading="lazy" class="question-inline-image" />`;
    }
    // No matching QuestionImage row — fall back to the legacy path so
    // the admin can still see something is broken (matches the debug
    // banner in the recall page for unresolved images).
    const alt = `Question image ${base}`.replace(/"/g, '&quot;');
    return `<img src="${escapeAttr(rawUrl)}" alt="${alt}" loading="lazy" class="question-inline-image" data-legacy-media-url="1" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'missing-image-placeholder',textContent:'[image missing: ${escapeAttr(base)}]'}))" />`;
  });

  cache.set(key, resolved);
  return resolved;
}

/**
 * Escape a value for safe inclusion inside an HTML attribute (double-quoted).
 *
 * The text-resolver path emits `<img src="…">` via `dangerouslySetInnerHTML`,
 * and the `src`/`onerror` payload ultimately comes from admin-controlled
 * fields (`QuestionImage.url`, `QuestionImage.file`, or the bare media
 * URL in the question text). Without escaping, a crafted string like
 *     x" onerror="alert(1)"
 * breaks out of the attribute. This helper encodes `"`, `&`, `<`, `>`
 * so the attribute always terminates at its own closing quote.
 */
function escapeAttr(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function _imgTag(img: QuestionImageLike, fallbackAlt: string): string {
  const src = escapeAttr((img.url || img.file) ?? '');
  const alt = (img.caption || fallbackAlt).replace(/"/g, '&quot;');
  const widthAttr = img.width ? ` width="${img.width}"` : '';
  const heightAttr = img.height ? ` height="${img.height}"` : '';
  return `<img src="${src}" alt="${alt}"${widthAttr}${heightAttr} loading="lazy" class="question-inline-image" />`;
}

export function clearImageTokenCache(): void {
  cache.clear();
}
