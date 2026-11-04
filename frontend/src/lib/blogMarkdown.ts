/**
 * blogMarkdown — how a blog post body (markdown, as stored in blog_engine)
 * becomes the article: the one pipeline behind the public post page
 * (components/blog/BlogArticle), the editor's Preview tab, the post's table
 * of contents and the editor's markdown reader (app/admin/blog/editor).
 *
 * Markdown dialect
 *   CommonMark + GFM (tables, task items, ~~strike~~, autolinks; one tilde
 *   stays text: "pH ~7.4"). A single newline inside a paragraph is a line
 *   break (remark-breaks): 38 of the 129 seeded posts write "**Term:** text"
 *   lines that way, and the site has always shown them as separate lines.
 *   The editor writes line breaks as a backslash + newline, which means the
 *   same with or without remark-breaks.
 *
 * Callouts (GitHub alert syntax): a blockquote whose first line is
 *   [!NOTE], [!TIP], [!IMPORTANT], [!WARNING] or [!CAUTION]:
 *       > [!TIP]
 *       > Revise the PYQs of the last five years first.
 *
 * Figures: an image alone in its paragraph is a figure; its title is the
 *   caption: ![Alt text for screen readers](/api/blog/images/2026/11/x.png "Caption").
 *   Uploaded images are stored as /api/... paths and point at the API origin
 *   here (imageOrigin), so a change of API host never breaks them.
 *
 * Safety: raw HTML is parsed (rehype-raw) and then cut down by the shared
 * allow-list (lib/markdownSanitize); everything rehypeBlogArticle adds after it
 * (callout boxes, figures, table wrappers, heading ids and anchors) is
 * generated here, never taken from the post.
 */
import type { Element, ElementContent, Properties, Root, RootContent, Text } from 'hast';
import type { ListItem, Paragraph, Root as MdastRoot, RootContent as MdastContent } from 'mdast';
import { unified, type PluggableList } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import remarkRehype from 'remark-rehype';
import rehypeRaw from 'rehype-raw';
import { rehypeAllowlist } from '@/lib/markdownSanitize';
import { assignHeadingIds, type TocItem } from '@/components/blogToc';
import { CALLOUT_LABELS, slugifyHeading, type CalloutKind } from '@/lib/blogText';

export type { TocItem };
export { CALLOUT_KINDS, CALLOUT_LABELS, type CalloutKind } from '@/lib/blogText';

/** `[!NOTE]` … `[!CAUTION]` at the start of a blockquote's first line (any case). */
export const CALLOUT_MARKER = /^[ \t]*\[!(note|tip|important|warning|caution)\]/i;

/** Ids the post page itself uses; a heading never takes them. */
export const RESERVED_PAGE_IDS: readonly string[] = ['start-reading', 'post-body', 'main-content'];
const ANCHOR_ID = /^[a-z0-9][a-z0-9_-]*$/;

/** How markdown is read: shared by the renderer and the editor's markdown reader. */
export const BLOG_PARSE_PLUGINS: PluggableList = [[remarkGfm, { singleTilde: false }], remarkBreaks];

/**
 * Task items ("- [ ] Admit card") render as ☐ / ☑ items: the sanitizer drops
 * <input> elements, so GFM's checkboxes never reached the page.
 */
export function remarkTaskGlyphs() {
    return (tree: MdastRoot) => {
        const visit = (nodes: MdastContent[]) => {
            for (const node of nodes) {
                if (node.type === 'listItem') taskGlyph(node);
                if ('children' in node && Array.isArray(node.children)) visit(node.children as MdastContent[]);
            }
        };
        visit(tree.children);
    };
}

function taskGlyph(item: ListItem) {
    if (item.checked === null || item.checked === undefined) return;
    const glyph = { type: 'text' as const, value: item.checked ? '☑ ' : '☐ ' };
    const first = item.children[0];
    if (first && first.type === 'paragraph') first.children.unshift(glyph);
    else item.children.unshift({ type: 'paragraph', children: [glyph] } as Paragraph);
    item.checked = null;
}

/** remark plugins of the rendered article. */
export const BLOG_RENDER_REMARK_PLUGINS: PluggableList = [...BLOG_PARSE_PLUGINS, remarkTaskGlyphs];

export interface BlogArticleOptions {
    /**
     * Anchor ids to keep: the post's stored table of contents. A `##` heading
     * whose text matches an entry gets that entry's id (so existing #links
     * keep working); other headings get an id from their text.
     */
    preferredIds?: readonly TocItem[];
    /** Origin that /api/... image paths resolve against (the API origin); unset keeps them as they are. */
    imageOrigin?: string;
}

/** rehype plugins of the rendered article: raw HTML, the allow-list, then the article structure. */
export function blogRehypePlugins(options: BlogArticleOptions = {}): PluggableList {
    return [rehypeTableWhitespace, rehypeRaw, rehypeAllowlist, [rehypeBlogArticle, options]];
}

const TABLE_PARTS = new Set(['table', 'thead', 'tbody', 'tfoot', 'tr']);

/**
 * Drops the newlines between table rows and cells. rehype-raw's HTML parser
 * would move ("foster-parent") them in front of the table, where they pile up
 * as stray text.
 */
export function rehypeTableWhitespace() {
    const clean = (node: Root | Element) => {
        if (node.type === 'element' && TABLE_PARTS.has(node.tagName)) {
            node.children = node.children.filter((c) => !isBlank(c));
        }
        for (const child of node.children) if (child.type === 'element') clean(child);
    };
    return (tree: Root) => clean(tree);
}

/** The article's HTML tree (what BlogArticle renders): for the table of contents and tests. */
export function blogArticleTree(markdown: string, options: BlogArticleOptions = {}): Root {
    const processor = unified()
        .use(remarkParse)
        .use(BLOG_RENDER_REMARK_PLUGINS)
        // react-markdown passes the same option to remark-rehype.
        .use(remarkRehype, { allowDangerousHtml: true })
        .use(blogRehypePlugins(options));
    return processor.runSync(processor.parse(markdown)) as Root;
}

/**
 * The post's "On this page" entries: its `##` headings, in order, with the
 * ids the rendered article gives them.
 */
export function blogToc(markdown: string, preferredIds: readonly TocItem[] = []): TocItem[] {
    if (!markdown.trim()) return [];
    const toc: TocItem[] = [];
    walkElements(blogArticleTree(markdown, { preferredIds }), (el) => {
        if (el.tagName === 'h2' && typeof el.properties.id === 'string') {
            toc.push({ id: el.properties.id, label: textOf(el) });
        }
    });
    return toc;
}

/** The article structure (runs after the sanitizer; see the header of this file). */
export function rehypeBlogArticle(options: BlogArticleOptions = {}) {
    return (tree: Root) => {
        structure(tree, options);
        assignIds(tree, options.preferredIds ?? []);
    };
}

// ── tree helpers ───────────────────────────────────────────────────────────

function el(tagName: string, properties: Properties, children: ElementContent[]): Element {
    return { type: 'element', tagName, properties, children };
}

function txt(value: string): Text {
    return { type: 'text', value };
}

function isBlank(node: RootContent | ElementContent): boolean {
    return node.type === 'text' && node.value.trim() === '';
}

function hasClass(node: Element, name: string): boolean {
    const value = node.properties.className;
    return Array.isArray(value) ? value.includes(name) : value === name;
}

/** The text of a node, without heading anchors. */
export function textOf(node: Root | RootContent | ElementContent): string {
    if (node.type === 'text') return node.value;
    if (node.type === 'element' && hasClass(node, 'heading-anchor')) return '';
    if ('children' in node) return (node.children as ElementContent[]).map(textOf).join('');
    return '';
}

function walkElements(node: Root | Element, visit: (el: Element) => void) {
    for (const child of node.children) {
        if (child.type !== 'element') continue;
        visit(child);
        walkElements(child, visit);
    }
}

// ── structure: callouts, figures, tables, links, images ────────────────────

function structure(parent: Root | Element, options: BlogArticleOptions) {
    const children = parent.children as Array<RootContent | ElementContent>;
    for (let i = 0; i < children.length; i++) {
        const node = children[i];
        if (node.type !== 'element') continue;
        if (node.tagName === 'h1') node.tagName = 'h2'; // the page title is the only h1
        if (node.tagName === 'table') {
            children[i] = el('div', { className: ['blog-table-wrap'], role: 'region', ariaLabel: 'Table (scrolls sideways)', tabIndex: 0 }, [node]);
            structure(node, options);
            continue;
        }
        const replacement = node.tagName === 'blockquote' ? asCallout(node) : node.tagName === 'p' ? asFigure(node) : null;
        if (replacement) {
            children[i] = replacement;
            structure(replacement, options);
            continue;
        }
        if (node.tagName === 'a') {
            const href = node.properties.href;
            if (typeof href === 'string' && /^https?:\/\//i.test(href)) node.properties.target = '_blank';
        } else if (node.tagName === 'img') {
            fixImage(node, options);
        }
        structure(node, options);
    }
}

function fixImage(img: Element, options: BlogArticleOptions) {
    const src = img.properties.src;
    if (typeof src === 'string' && src.startsWith('/api/') && options.imageOrigin) {
        img.properties.src = `${options.imageOrigin.replace(/\/+$/, '')}${src}`;
    }
    img.properties.loading = 'lazy';
    img.properties.decoding = 'async';
}

/** A blockquote opened by [!NOTE] / [!TIP] / ... as a callout box, else null. */
function asCallout(quote: Element): Element | null {
    const index = quote.children.findIndex((c) => !isBlank(c));
    const first = quote.children[index];
    if (!first || first.type !== 'element' || first.tagName !== 'p') return null;
    const lead = first.children[0];
    if (!lead || lead.type !== 'text') return null;
    const match = CALLOUT_MARKER.exec(lead.value);
    if (!match) return null;
    const kind = match[1].toLowerCase() as CalloutKind;

    const rest = first.children.slice(1);
    const after = lead.value.slice(match[0].length).replace(/^[ \t]+/, '');
    if (after.replace(/^\n+/, '')) {
        rest.unshift(txt(after.replace(/^\n+/, '')));
    } else {
        // The marker line ended with a line break: drop it (and the newline after a <br>).
        if (rest[0]?.type === 'element' && rest[0].tagName === 'br') rest.shift();
        if (rest[0]?.type === 'text') {
            const trimmed = rest[0].value.replace(/^\s+/, '');
            if (trimmed) rest[0] = txt(trimmed);
            else rest.shift();
        }
    }
    const body = quote.children.slice();
    if (rest.some((c) => !isBlank(c))) body[index] = { ...first, children: rest };
    else body.splice(index, 1);

    const title = el('p', { className: ['callout-title'] }, [
        el('span', { className: ['callout-icon'], ariaHidden: 'true' }, []),
        txt(CALLOUT_LABELS[kind]),
    ]);
    // One newline between blocks, whatever the source's blank lines were
    // ("> [!TIP]\n> text" and "> [!TIP]\n>\n> text" render the same).
    const children: ElementContent[] = [txt('\n'), title];
    for (const block of body) if (!isBlank(block)) children.push(txt('\n'), block as ElementContent);
    children.push(txt('\n'));
    return el('div', { className: ['callout', `callout-${kind}`], dataCallout: kind, role: 'note' }, children);
}

/** A paragraph holding only an image (or a linked image) as a figure; the title is its caption. */
function asFigure(paragraph: Element): Element | null {
    const content = paragraph.children.filter((c) => !isBlank(c));
    if (content.length !== 1 || content[0].type !== 'element') return null;
    const only = content[0];
    let img: Element | null = null;
    if (only.tagName === 'img') img = only;
    else if (only.tagName === 'a') {
        const inner = only.children.filter((c) => !isBlank(c));
        if (inner.length === 1 && inner[0].type === 'element' && inner[0].tagName === 'img') img = inner[0];
    }
    if (!img) return null;
    const caption = typeof img.properties.title === 'string' ? img.properties.title.trim() : '';
    const children: ElementContent[] = [only];
    if (caption) {
        delete img.properties.title; // shown below the image instead of as a tooltip
        children.push(el('figcaption', {}, [txt(caption)]));
    }
    return el('figure', { className: ['blog-figure'] }, children);
}

// ── heading ids ────────────────────────────────────────────────────────────

function assignIds(tree: Root, preferred: readonly TocItem[]) {
    const headings: Element[] = [];
    walkElements(tree, (node) => {
        if (node.tagName === 'h2' || node.tagName === 'h3') headings.push(node);
    });
    if (!headings.length) return;

    const used = new Set<string>(RESERVED_PAGE_IDS);
    const h2s = headings.filter((h) => h.tagName === 'h2');
    const wanted = preferred.filter((item) => ANCHOR_ID.test(item.id) && !used.has(item.id));
    const kept = assignHeadingIds(h2s.map((h) => ({ text: textOf(h) })), wanted);
    const ids = new Map<Element, string>();
    h2s.forEach((h, i) => {
        const id = kept[i];
        if (id && !used.has(id)) {
            ids.set(h, id);
            used.add(id);
        }
    });
    headings.forEach((heading, n) => {
        let id = ids.get(heading);
        if (!id) {
            const base = slugifyHeading(textOf(heading)) || `section-${n + 1}`;
            id = base;
            for (let k = 2; used.has(id); k++) id = `${base}-${k}`;
            used.add(id);
        }
        const label = textOf(heading).trim();
        heading.properties.id = id;
        heading.children.push(el('a', { className: ['heading-anchor'], href: `#${id}`, ariaLabel: `Link to this section: ${label}` }, [txt('#')]));
    });
}
