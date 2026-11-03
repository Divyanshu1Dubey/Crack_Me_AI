/**
 * Allow-list sanitizer for markdown rendered with `rehype-raw`.
 *
 * FormattedText renders question stems, explanations (including AI-generated
 * and admin-imported ones), topic notes, blog posts and tutor answers with
 * `rehype-raw`, so raw HTML stored in that content reached the DOM. React
 * already drops string event handlers and react-markdown filters
 * `javascript:` URLs, but iframes, forms, <style>, overlays built with inline
 * CSS and similar markup still rendered for every student who opened the
 * question.
 *
 * This plugin runs after `rehype-raw` and keeps only formatting markup:
 *  - allowed tags keep an explicit per-tag attribute list; everything else
 *    (event handlers, data-*, id, class, style except below) is removed;
 *  - script / style / iframe / form / svg / media and similar elements are
 *    dropped together with their content; unknown tags are unwrapped;
 *  - href / src keep only http(s), mailto, tel, relative URLs and, for
 *    images, raster data: URLs (control characters are ignored when the
 *    scheme is checked, as browsers do);
 *  - <span style> keeps colour / decoration declarations only, which is what
 *    the admin [[red]] / [[u]] tokens produce.
 */
import type { Element, ElementContent, Properties, Root, RootContent } from 'hast';

const ALLOWED_TAGS = new Set([
    'p', 'br', 'hr', 'span', 'div', 'strong', 'b', 'em', 'i', 'u', 's', 'del', 'ins', 'mark', 'small', 'sub', 'sup',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'blockquote', 'code', 'pre', 'kbd', 'abbr',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'caption',
    'a', 'img', 'figure', 'figcaption', 'details', 'summary',
]);

// Removed with everything inside them (their text is not content).
const DROP_WITH_CONTENT = new Set([
    'script', 'style', 'iframe', 'frame', 'frameset', 'object', 'embed', 'applet', 'form', 'input', 'button',
    'textarea', 'select', 'option', 'noscript', 'template', 'svg', 'math', 'link', 'meta', 'base', 'title',
    'video', 'audio', 'source', 'track', 'canvas', 'dialog', 'portal',
]);

const TAG_PROPS: Record<string, readonly string[]> = {
    a: ['href', 'title'],
    img: ['src', 'alt', 'title', 'width', 'height'],
    td: ['colSpan', 'rowSpan', 'align'],
    th: ['colSpan', 'rowSpan', 'align', 'scope'],
    ol: ['start'],
    abbr: ['title'],
    span: ['style'],
    code: ['className'],
    pre: ['className'],
};

const STYLE_PROPS = new Set(['color', 'background-color', 'text-decoration', 'text-decoration-line', 'font-weight', 'font-style']);
const STYLE_VALUE = /^[#a-z0-9\s(),.%-]+$/i;
const LINK_SCHEMES = new Set(['http', 'https', 'mailto', 'tel']);
const IMG_DATA_URL = /^data:image\/(?:png|jpe?g|gif|webp);base64,[a-z0-9+/=\s]+$/i;

/** Browsers ignore ASCII whitespace and control characters inside a URL scheme. */
const schemeOf = (url: string): string | null => {
    const compact = url.replace(/[\u0000- \u007f]+/g, '');
    const m = /^([a-z][a-z0-9+.-]*):/i.exec(compact);
    return m ? m[1].toLowerCase() : null;
};

export function safeUrl(value: unknown, kind: 'link' | 'image'): string | null {
    if (typeof value !== 'string') return null;
    const url = value.trim();
    if (!url) return null;
    const scheme = schemeOf(url);
    if (scheme === null) return url; // relative URL, fragment or path
    if (kind === 'image' && scheme === 'data') return IMG_DATA_URL.test(url) ? url : null;
    if (kind === 'image' && scheme === 'blob') return url;
    if (kind === 'image') return scheme === 'http' || scheme === 'https' ? url : null;
    return LINK_SCHEMES.has(scheme) ? url : null;
}

export function safeStyle(value: unknown): string | null {
    if (typeof value !== 'string') return null;
    const kept: string[] = [];
    for (const declaration of value.split(';')) {
        const colon = declaration.indexOf(':');
        if (colon < 0) continue;
        const prop = declaration.slice(0, colon).trim().toLowerCase();
        const val = declaration.slice(colon + 1).trim();
        if (!STYLE_PROPS.has(prop) || !val || !STYLE_VALUE.test(val) || /url\s*\(|expression|var\s*\(/i.test(val)) continue;
        kept.push(`${prop}:${val}`);
    }
    return kept.length ? kept.join(';') : null;
}

function cleanProperties(tag: string, props: Properties): Properties {
    const out: Properties = {};
    for (const name of TAG_PROPS[tag] ?? []) {
        const value = props[name];
        if (value === undefined || value === null) continue;
        if (name === 'href') {
            const href = safeUrl(value, 'link');
            if (href) {
                out.href = href;
                if (/^https?:/i.test(href)) out.rel = ['nofollow', 'noopener', 'noreferrer'];
            }
        } else if (name === 'src') {
            const src = safeUrl(value, 'image');
            if (src) out.src = src;
        } else if (name === 'style') {
            const style = safeStyle(value);
            if (style) out.style = style;
        } else if (name === 'className') {
            const classes = (Array.isArray(value) ? value : [value]).map(String).filter(c => /^language-[\w-]+$/.test(c));
            if (classes.length) out.className = classes;
        } else if (name === 'colSpan' || name === 'rowSpan' || name === 'start' || name === 'width' || name === 'height') {
            const n = Number(value);
            if (Number.isFinite(n) && n >= 0 && n <= 10000) out[name] = n;
        } else if (typeof value === 'string' || typeof value === 'number') {
            out[name] = String(value).slice(0, 500);
        }
    }
    return out;
}

function sanitizeNodes(nodes: Array<RootContent | ElementContent>): ElementContent[] {
    const out: ElementContent[] = [];
    for (const node of nodes) {
        if (node.type === 'text') {
            out.push(node);
            continue;
        }
        if (node.type !== 'element') continue; // comments, doctypes, leftover raw nodes
        const element = node as Element;
        const tag = element.tagName.toLowerCase();
        if (DROP_WITH_CONTENT.has(tag)) continue;
        const children = sanitizeNodes(element.children);
        if (!ALLOWED_TAGS.has(tag)) {
            out.push(...children); // unknown wrapper: keep its content only
            continue;
        }
        const properties = cleanProperties(tag, element.properties ?? {});
        if (tag === 'img' && !properties.src) continue;
        out.push({ ...element, tagName: tag, properties, children });
    }
    return out;
}

/** unified/rehype plugin: use as `rehypePlugins={[rehypeRaw, rehypeAllowlist]}`. */
export function rehypeAllowlist() {
    return (tree: Root) => {
        tree.children = sanitizeNodes(tree.children) as Root['children'];
    };
}
