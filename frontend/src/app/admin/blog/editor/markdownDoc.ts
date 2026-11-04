/**
 * markdownDoc — a blog body (markdown, as blog_engine stores it) ⇄ the visual
 * editor's document (ProseMirror JSON in the schema of ./schema.ts).
 *
 * markdownToDoc reads markdown with the site's own parser (lib/blogMarkdown
 * BLOG_PARSE_PLUGINS: CommonMark + GFM, a newline is a line break), so the
 * editor holds what the post page renders. docToMarkdown writes it back:
 *  - line breaks as backslash + newline (the same with or without
 *    remark-breaks), <br> where markdown cannot hold one (headings, table
 *    cells) or where the post wrote <br>;
 *  - text escaped where markdown would read it as syntax (*, _, [, |, a line
 *    starting with "#", "1." or "- ", autolink-looking URLs, ...);
 *  - every paragraph, heading and table cell is read back; if the markdown
 *    would not give the same text and formatting (e.g. emphasis next to
 *    punctuation), that one is written with HTML tags instead (<strong>,
 *    <em>, <del>, <a href>, <code>), which the site's sanitizer keeps.
 * tests/unit/blog-editor-roundtrip.test.ts runs every seeded post through
 * markdown -> document -> markdown and compares the rendered article HTML.
 *
 * What the visual editor cannot hold is reported in `unsupported` (e.g.
 * footnotes); the editor then keeps that post in the Markdown tab.
 */
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import type {
    Blockquote,
    Definition,
    List,
    ListItem,
    PhrasingContent,
    Root,
    RootContent,
    Table,
} from 'mdast';
import { BLOG_PARSE_PLUGINS, CALLOUT_MARKER } from '@/lib/blogMarkdown';
import { calloutKind } from '@/lib/blogText';

export interface PMMark {
    type: string;
    attrs?: Record<string, unknown>;
}

export interface PMNode {
    type: string;
    attrs?: Record<string, unknown>;
    content?: PMNode[];
    text?: string;
    marks?: PMMark[];
}

export interface MarkdownDoc {
    doc: PMNode;
    /** Constructs the visual editor cannot hold (empty: the visual editor may edit this body). */
    unsupported: string[];
}

// ── markdown -> document ───────────────────────────────────────────────────

const parser = unified().use(remarkParse).use(BLOG_PARSE_PLUGINS);

/** The markdown tree of a body, as the site reads it. */
export function parseBlogMarkdown(markdown: string): Root {
    return parser.runSync(parser.parse(markdown)) as Root;
}

interface ReadContext {
    definitions: Map<string, Definition>;
    unsupported: Set<string>;
}

export function markdownToDoc(markdown: string): MarkdownDoc {
    const tree = parseBlogMarkdown(markdown);
    const ctx: ReadContext = { definitions: new Map(), unsupported: new Set() };
    collectDefinitions(tree.children, ctx);
    const content = readBlocks(tree.children, ctx);
    return {
        doc: { type: 'doc', content: content.length ? content : [{ type: 'paragraph' }] },
        unsupported: [...ctx.unsupported],
    };
}

function collectDefinitions(nodes: RootContent[], ctx: ReadContext) {
    for (const node of nodes) {
        if (node.type === 'definition') {
            if (!ctx.definitions.has(node.identifier)) ctx.definitions.set(node.identifier, node);
        } else if ('children' in node && Array.isArray(node.children)) {
            collectDefinitions(node.children as RootContent[], ctx);
        }
    }
}

function readBlocks(nodes: RootContent[], ctx: ReadContext): PMNode[] {
    const out: PMNode[] = [];
    for (const node of nodes) out.push(...readBlock(node, ctx));
    return out;
}

function paragraph(content: PMNode[]): PMNode {
    return content.length ? { type: 'paragraph', content } : { type: 'paragraph' };
}

function readBlock(node: RootContent, ctx: ReadContext): PMNode[] {
    switch (node.type) {
        case 'paragraph':
            return [paragraph(readInline(node.children, ctx))];
        case 'heading': {
            const content = readInline(node.children, ctx);
            // The page title is the only h1: the site renders "# x" as a ## heading.
            const level = node.depth === 1 ? 2 : node.depth;
            return [{ type: 'heading', attrs: { level }, ...(content.length ? { content } : {}) }];
        }
        case 'thematicBreak':
            return [{ type: 'horizontalRule' }];
        case 'blockquote':
            return [readQuote(node, ctx)];
        case 'list':
            return [readList(node, ctx)];
        case 'code':
            return [{
                type: 'codeBlock',
                attrs: { language: node.lang || null },
                ...(node.value ? { content: [{ type: 'text', text: node.value }] } : {}),
            }];
        case 'html':
            return [{ type: 'htmlBlock', attrs: { html: node.value } }];
        case 'table':
            return [readTable(node, ctx)];
        case 'definition':
            return []; // read into the links that use it
        case 'footnoteDefinition':
            ctx.unsupported.add('footnotes');
            return [];
        default:
            ctx.unsupported.add(node.type);
            return [];
    }
}

/** A blockquote, or a callout when its first line is [!NOTE] ... [!CAUTION] (see lib/blogMarkdown). */
function readQuote(node: Blockquote, ctx: ReadContext): PMNode {
    const first = node.children[0];
    const lead = first?.type === 'paragraph' ? first.children[0] : undefined;
    const match = lead?.type === 'text' ? CALLOUT_MARKER.exec(lead.value) : null;
    if (first?.type === 'paragraph' && lead?.type === 'text' && match) {
        let rest: PhrasingContent[] = first.children.slice(1);
        const after = lead.value.slice(match[0].length).replace(/^[ \t]+/, '');
        if (after.replace(/^\n+/, '')) {
            rest = [{ ...lead, value: after.replace(/^\n+/, '') }, ...rest];
        } else {
            if (rest[0]?.type === 'break') rest = rest.slice(1);
            if (rest[0]?.type === 'text') {
                const trimmed = rest[0].value.replace(/^\s+/, '');
                rest = trimmed ? [{ ...rest[0], value: trimmed }, ...rest.slice(1)] : rest.slice(1);
            }
        }
        const body: RootContent[] = [...(rest.length ? [{ ...first, children: rest }] : []), ...node.children.slice(1)];
        const content = readBlocks(body, ctx);
        return { type: 'callout', attrs: { kind: calloutKind(match[1]) }, content: content.length ? content : [paragraph([])] };
    }
    const content = readBlocks(node.children, ctx);
    return { type: 'blockquote', content: content.length ? content : [paragraph([])] };
}

/** As mdast-util-to-hast decides whether list items render as paragraphs. */
function listIsLoose(node: List): boolean {
    if (node.spread) return true;
    return node.children.some((item) => (item.spread === null || item.spread === undefined ? item.children.length > 1 : item.spread));
}

function readList(node: List, ctx: ReadContext): PMNode {
    const tight = !listIsLoose(node);
    const content = node.children.map((item) => readListItem(item, ctx));
    return node.ordered
        ? { type: 'orderedList', attrs: { start: node.start ?? 1, tight }, content }
        : { type: 'bulletList', attrs: { tight }, content };
}

function readListItem(item: ListItem, ctx: ReadContext): PMNode {
    const content = readBlocks(item.children, ctx);
    // A list item starts with a paragraph in the editor's schema.
    if (content[0]?.type !== 'paragraph') content.unshift(paragraph([]));
    return { type: 'listItem', attrs: { checked: typeof item.checked === 'boolean' ? item.checked : null }, content };
}

function readTable(node: Table, ctx: ReadContext): PMNode {
    const align = node.align ?? [];
    // mdast-util-to-hast renders every row with as many cells as the alignment row.
    const width = align.length || Math.max(1, ...node.children.map((row) => row.children.length));
    return {
        type: 'table',
        content: node.children.map((row, r) => ({
            type: 'tableRow',
            content: Array.from({ length: width }, (_, c) => {
                const cell = row.children[c];
                return {
                    type: r === 0 ? 'tableHeader' : 'tableCell',
                    attrs: { align: align[c] ?? null },
                    content: [paragraph(cell ? readInline(cell.children, ctx) : [])],
                };
            }),
        })),
    };
}

// Raw inline HTML the editor shows as formatting (the same element markdown
// would produce); anything else stays a verbatim htmlInline node.
const RAW_MARKS: Record<string, string> = { strong: 'bold', em: 'italic', del: 'strike', u: 'underline', code: 'code' };
const RAW_OPEN = /^<([a-z][a-z0-9]*)(\s[^<>]*)?>$/i;
const RAW_CLOSE = /^<\/([a-z][a-z0-9]*)\s*>$/i;
const RAW_BR = /^<br\s*\/?>$/i;

function decodeAttr(value: string): string | null {
    const known: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", '#39': "'", '#x27': "'" };
    let ok = true;
    const out = value.replace(/&(#?[a-z0-9]+);/gi, (m, name: string) => {
        const hit = known[name.toLowerCase()];
        if (hit === undefined) ok = false;
        return hit ?? m;
    });
    return ok ? out : null;
}

/** href / title of a raw <a ...> open tag, or null when it has other or unreadable attributes. */
function anchorAttrs(attrs: string): { href: string; title: string | null } | null {
    const found: Record<string, string> = {};
    const rest = attrs.replace(/\s([a-z-]+)\s*=\s*("([^"]*)"|'([^']*)')/gi, (_m, name: string, _q, dq?: string, sq?: string) => {
        found[name.toLowerCase()] = dq ?? sq ?? '';
        return '';
    });
    if (rest.trim() || !('href' in found) || Object.keys(found).some((k) => k !== 'href' && k !== 'title')) return null;
    const href = decodeAttr(found.href);
    const title = found.title === undefined ? null : decodeAttr(found.title);
    if (href === null || (found.title !== undefined && title === null)) return null;
    return { href, title };
}

function textNode(text: string, marks: PMMark[]): PMNode {
    return marks.length ? { type: 'text', text, marks: dedupeMarks(marks) } : { type: 'text', text };
}

function withMarks(node: PMNode, marks: PMMark[]): PMNode {
    return marks.length ? { ...node, marks: dedupeMarks(marks) } : node;
}

function dedupeMarks(marks: PMMark[]): PMMark[] {
    const byType = new Map<string, PMMark>();
    for (const mark of marks) byType.set(mark.type, mark); // the innermost wins
    return [...byType.values()];
}

function linkMark(href: string, title: string | null | undefined): PMMark {
    return { type: 'link', attrs: { href, title: title || null } };
}

function readInline(nodes: PhrasingContent[], ctx: ReadContext, marks: PMMark[] = []): PMNode[] {
    const out: PMNode[] = [];
    const raw: { tag: string; mark: PMMark }[] = [];
    const current = () => [...marks, ...raw.map((r) => r.mark)];
    for (const node of nodes) {
        switch (node.type) {
            case 'text':
                if (node.value) out.push(textNode(node.value, current()));
                break;
            case 'strong':
                out.push(...readInline(node.children, ctx, [...current(), { type: 'bold' }]));
                break;
            case 'emphasis':
                out.push(...readInline(node.children, ctx, [...current(), { type: 'italic' }]));
                break;
            case 'delete':
                out.push(...readInline(node.children, ctx, [...current(), { type: 'strike' }]));
                break;
            case 'inlineCode':
                if (node.value) out.push(textNode(node.value, [...current(), { type: 'code' }]));
                break;
            case 'link':
                out.push(...readInline(node.children, ctx, [...current(), linkMark(node.url, node.title)]));
                break;
            case 'linkReference': {
                const def = ctx.definitions.get(node.identifier);
                if (def) out.push(...readInline(node.children, ctx, [...current(), linkMark(def.url, def.title)]));
                else {
                    // No definition: rendered as the text it was written as.
                    out.push(textNode('[', current()), ...readInline(node.children, ctx, current()),
                        textNode(node.referenceType === 'full' ? `][${node.label ?? node.identifier}]`
                            : node.referenceType === 'collapsed' ? '][]' : ']', current()));
                }
                break;
            }
            case 'image':
                out.push(withMarks({ type: 'image', attrs: { src: node.url, alt: node.alt ?? null, title: node.title ?? null } }, current()));
                break;
            case 'imageReference': {
                const def = ctx.definitions.get(node.identifier);
                if (def) out.push(withMarks({ type: 'image', attrs: { src: def.url, alt: node.alt ?? null, title: def.title ?? null } }, current()));
                else out.push(textNode(`![${node.alt ?? ''}]`, current()));
                break;
            }
            case 'break':
                out.push(withMarks({ type: 'hardBreak' }, current()));
                break;
            case 'html': {
                const value = node.value;
                const open = RAW_OPEN.exec(value);
                const close = RAW_CLOSE.exec(value);
                if (RAW_BR.test(value)) {
                    out.push(withMarks({ type: 'hardBreak', attrs: { source: 'html' } }, current()));
                } else if (open && RAW_MARKS[open[1].toLowerCase()] && !open[2]?.trim()) {
                    raw.push({ tag: open[1].toLowerCase(), mark: { type: RAW_MARKS[open[1].toLowerCase()] } });
                } else if (open && open[1].toLowerCase() === 'a' && anchorAttrs(open[2] ?? '')) {
                    const { href, title } = anchorAttrs(open[2] ?? '')!;
                    raw.push({ tag: 'a', mark: linkMark(href, title) });
                } else if (close && raw.some((r) => r.tag === close[1].toLowerCase())) {
                    // Close up to the matching tag (the HTML parser does the same).
                    while (raw.length && raw[raw.length - 1].tag !== close[1].toLowerCase()) raw.pop();
                    raw.pop();
                } else {
                    out.push(withMarks({ type: 'htmlInline', attrs: { html: value } }, current()));
                }
                break;
            }
            case 'footnoteReference':
                ctx.unsupported.add('footnotes');
                break;
            default: // a node type a later mdast version adds
                ctx.unsupported.add((node as { type: string }).type);
        }
    }
    return out;
}

// ── document -> markdown ───────────────────────────────────────────────────

export function docToMarkdown(doc: PMNode): string {
    return writeBlocks(doc.content ?? []).replace(/\n{3,}/g, '\n\n').trim();
}

function writeBlocks(nodes: PMNode[]): string {
    const parts: string[] = [];
    let previous: { type: string; marker: string } | null = null;
    for (const node of nodes) {
        let marker = '';
        if (node.type === 'bulletList') {
            // Two lists in a row with the same marker would read back as one list.
            marker = previous?.type === 'bulletList' && previous.marker === '-' ? '*' : '-';
        } else if (node.type === 'orderedList') {
            marker = previous?.type === 'orderedList' && previous.marker === '.' ? ')' : '.';
        }
        const text = writeBlock(node, marker);
        if (!text) continue; // an empty paragraph
        parts.push(text);
        previous = { type: node.type, marker };
    }
    return parts.join('\n\n');
}

function prefixLines(text: string, prefix: string): string {
    return text.split('\n').map((line) => (line ? prefix + line : prefix.trimEnd())).join('\n');
}

function plainText(node: PMNode): string {
    if (node.type === 'text') return node.text ?? '';
    return (node.content ?? []).map(plainText).join('');
}

function writeBlock(node: PMNode, marker: string): string {
    switch (node.type) {
        case 'paragraph':
            return writeInline(node.content ?? [], 'paragraph');
        case 'heading': {
            const level = Math.min(6, Math.max(1, Number(node.attrs?.level) || 2));
            const text = writeInline(node.content ?? [], 'heading', level);
            return text ? `${'#'.repeat(level)} ${text}` : '#'.repeat(level);
        }
        case 'horizontalRule':
            return '---';
        case 'blockquote':
            return prefixLines(writeBlocks(node.content ?? []) || '', '> ') || '>';
        case 'callout': {
            const kind = calloutKind(node.attrs?.kind).toUpperCase();
            const content = node.content ?? [];
            const body = writeBlocks(content);
            if (!body) return `> [!${kind}]`;
            // A paragraph may follow the marker line directly; other blocks after a blank quote line.
            const joiner = content.find((c) => writeBlock(c, '') !== '')?.type === 'paragraph' ? '\n' : '\n>\n';
            return `> [!${kind}]${joiner}${prefixLines(body, '> ')}`;
        }
        case 'bulletList':
        case 'orderedList':
            return writeList(node, marker || (node.type === 'bulletList' ? '-' : '.'));
        case 'codeBlock': {
            const text = plainText(node);
            const lang = typeof node.attrs?.language === 'string' ? node.attrs.language.replace(/[`\s]/g, '') : '';
            let fence = '```';
            while (text.includes(fence)) fence += '`';
            return `${fence}${lang}\n${text}${text ? '\n' : ''}${fence}`;
        }
        case 'htmlBlock':
            return String(node.attrs?.html ?? '');
        case 'table':
            return writeTable(node);
        default:
            return '';
    }
}

function writeList(node: PMNode, marker: string): string {
    const ordered = node.type === 'orderedList';
    const tight = node.attrs?.tight !== false;
    const start = Number(node.attrs?.start ?? 1) || 1;
    const items = (node.content ?? []).map((item, i) => {
        const bullet = ordered ? `${start + i}${marker}` : marker;
        const checked = item.attrs?.checked;
        const task = checked === true ? '[x] ' : checked === false ? '[ ] ' : '';
        const indent = ' '.repeat(bullet.length + 1);
        let children = item.content ?? [];
        // An item that starts with another block than text: that block goes on the marker line.
        if (children.length > 1 && children[0].type === 'paragraph' && !(children[0].content ?? []).length) children = children.slice(1);
        const parts: string[] = [];
        children.forEach((child, j) => {
            const text = writeBlock(child, child.type === 'bulletList' ? '-' : child.type === 'orderedList' ? '.' : '');
            if (!text && j > 0) return;
            if (j > 0) parts.push(tight && (child.type === 'bulletList' || child.type === 'orderedList') ? '\n' : '\n\n');
            parts.push(text);
        });
        const body = parts.join('');
        if (!body) return `${bullet}${task ? ` ${task.trimEnd()}` : ''}`;
        const [first, ...more] = body.split('\n');
        return `${bullet} ${task}${first}${more.length ? `\n${more.map((line) => (line ? indent + line : '')).join('\n')}` : ''}`;
    });
    return items.join(tight ? '\n' : '\n\n');
}

function writeTable(node: PMNode): string {
    const rows = node.content ?? [];
    if (!rows.length) return '';
    const width = Math.max(1, ...rows.map((row) => (row.content ?? []).length));
    const line = (row: PMNode) => {
        const cells = row.content ?? [];
        return `| ${Array.from({ length: width }, (_, c) => writeCell(cells[c])).join(' | ')} |`;
    };
    const header = rows[0].content ?? [];
    const delimiter = `| ${Array.from({ length: width }, (_, c) => {
        const align = header[c]?.attrs?.align;
        return align === 'left' ? ':---' : align === 'center' ? ':---:' : align === 'right' ? '---:' : '---';
    }).join(' | ')} |`;
    return [line(rows[0]), delimiter, ...rows.slice(1).map(line)].join('\n');
}

function writeCell(cell: PMNode | undefined): string {
    if (!cell) return '';
    const inline: PMNode[] = [];
    (cell.content ?? []).forEach((block, i) => {
        if (i > 0) inline.push({ type: 'hardBreak', attrs: { source: 'html' } });
        inline.push(...(block.content ?? []));
    });
    return writeInline(inline, 'cell');
}

// ── inline content ─────────────────────────────────────────────────────────

type InlineKind = 'paragraph' | 'heading' | 'cell';

type Token =
    | { k: 'text'; text: string; marks: PMMark[] }
    | { k: 'break'; html: boolean; marks: PMMark[] }
    | { k: 'image'; src: string; alt: string; title: string; marks: PMMark[] }
    | { k: 'html'; html: string; marks: PMMark[] };

const KNOWN_MARKS = new Set(['bold', 'italic', 'strike', 'underline', 'link', 'code']);
/** Outer to inner, for marks over the same text: **[a link](/x)**, emphasis outside, code innermost. */
const MARK_ORDER = ['bold', 'italic', 'strike', 'underline', 'link'];

function markKey(mark: PMMark): string {
    if (mark.type !== 'link') return mark.type;
    return `link\u0000${String(mark.attrs?.href ?? '')}\u0000${String(mark.attrs?.title ?? '')}`;
}

function tokensOf(nodes: PMNode[]): Token[] {
    const tokens: Token[] = [];
    for (const node of nodes) {
        const marks = (node.marks ?? []).filter((m) => KNOWN_MARKS.has(m.type) && (m.type !== 'link' || m.attrs?.href));
        if (node.type === 'text' && node.text) {
            // A newline cannot be inside markdown text: it is a line break.
            node.text.split('\n').forEach((part, i) => {
                if (i > 0) tokens.push({ k: 'break', html: false, marks });
                if (part) tokens.push({ k: 'text', text: part, marks });
            });
        } else if (node.type === 'hardBreak') {
            tokens.push({ k: 'break', html: node.attrs?.source === 'html', marks });
        } else if (node.type === 'image') {
            tokens.push({
                k: 'image',
                src: String(node.attrs?.src ?? ''),
                alt: String(node.attrs?.alt ?? ''),
                title: String(node.attrs?.title ?? ''),
                marks,
            });
        } else if (node.type === 'htmlInline') {
            tokens.push({ k: 'html', html: String(node.attrs?.html ?? ''), marks });
        }
    }
    // Merge neighbouring text with the same formatting.
    const merged: Token[] = [];
    for (const token of tokens) {
        const last = merged[merged.length - 1];
        if (token.k === 'text' && last?.k === 'text' && sameMarks(last.marks, token.marks)) last.text += token.text;
        else merged.push(token.k === 'text' ? { ...token } : token);
    }
    return merged;
}

function marksSignature(marks: PMMark[]): string {
    return marks.map(markKey).sort().join('\u0001');
}

function sameMarks(a: PMMark[], b: PMMark[]): boolean {
    return marksSignature(a) === marksSignature(b);
}

/**
 * The inline content as markdown, verified: when the markdown would not read
 * back as the same text and formatting, the same content with HTML tags.
 */
function writeInline(nodes: PMNode[], kind: InlineKind, level = 2): string {
    const tokens = tokensOf(nodes);
    // A line break cannot end a paragraph in markdown: keep it as <br> (rare; the HTML version).
    if (!tokens.length) return '';
    const markdown = renderTokens(tokens, 'markdown', kind);
    if (sameTokens(tokens, reread(markdown, kind, level))) return markdown;
    return renderTokens(tokens, 'html', kind);
}

function reread(markdown: string, kind: InlineKind, level: number): Token[] | null {
    const source = kind === 'heading' ? `${'#'.repeat(level)} ${markdown}` : kind === 'cell' ? `| ${markdown} |\n| --- |` : markdown;
    const tree = parseBlogMarkdown(source);
    if (tree.children.length !== 1) return null;
    const block = tree.children[0];
    let phrasing: PhrasingContent[] | null = null;
    if (kind === 'paragraph' && block.type === 'paragraph') phrasing = block.children;
    else if (kind === 'heading' && block.type === 'heading') phrasing = block.children;
    else if (kind === 'cell' && block.type === 'table') phrasing = block.children[0]?.children[0]?.children ?? [];
    if (!phrasing) return null;
    return tokensOf(readInline(phrasing, { definitions: new Map(), unsupported: new Set() }));
}

/** Text compared as the page shows it: runs of spaces are one space, none around line breaks or at the ends. */
function normalizedTokens(tokens: Token[]): Token[] {
    const out = tokens.map((t) => (t.k === 'text' ? { ...t, text: t.text.replace(/[ \t]+/g, ' ') } : t));
    for (let i = 0; i < out.length; i++) {
        const t = out[i];
        if (t.k !== 'text') continue;
        const prev = out[i - 1];
        const next = out[i + 1];
        let text = t.text;
        if (!prev || prev.k === 'break') text = text.replace(/^ +/, '');
        if (!next || next.k === 'break') text = text.replace(/ +$/, '');
        out[i] = { ...t, text };
    }
    return out.filter((t) => t.k !== 'text' || t.text !== '');
}

function sameTokens(a: Token[], b: Token[] | null): boolean {
    if (!b) return false;
    const x = normalizedTokens(a);
    const y = normalizedTokens(b);
    if (x.length !== y.length) return false;
    return x.every((t, i) => {
        const u = y[i];
        if (t.k !== u.k || !sameMarks(t.marks, u.marks)) return false;
        if (t.k === 'text' && u.k === 'text') return t.text === u.text;
        if (t.k === 'image' && u.k === 'image') return t.src === u.src && t.alt === u.alt && t.title === u.title;
        if (t.k === 'html' && u.k === 'html') return t.html === u.html;
        return t.k === 'break';
    });
}

interface OpenMark {
    key: string;
    mark: PMMark;
}

function renderTokens(tokens: Token[], mode: 'markdown' | 'html', kind: InlineKind): string {
    let out = '';
    const stack: OpenMark[] = [];
    // Trailing line breaks do not survive in markdown; the HTML version keeps them as <br>.
    let end = tokens.length;
    if (mode === 'markdown') while (end > 0 && tokens[end - 1].k === 'break') end--;

    const span = (from: number, key: string) => {
        let n = 0;
        for (let i = from; i < end; i++) {
            const t = tokens[i];
            if (!t.marks.some((m) => markKey(m) === key)) break;
            n++;
        }
        return n;
    };
    const close = (count: number) => {
        for (let n = 0; n < count; n++) {
            const open = stack.pop();
            if (!open) return;
            const closer = closingDelimiter(open.mark, mode);
            if (mode === 'markdown' && open.mark.type !== 'link' && open.mark.type !== 'underline') {
                // Emphasis cannot end with a space: move the space after the delimiter.
                const space = /[ \t]+$/.exec(out)?.[0] ?? '';
                out = out.slice(0, out.length - space.length) + closer + space;
            } else {
                out += closer;
            }
        }
    };

    for (let i = 0; i < end; i++) {
        const token = tokens[i];
        const keys = new Set(token.marks.filter((m) => m.type !== 'code').map(markKey));
        // Close every open mark this token does not have (and those opened inside it).
        const keep = stack.findIndex((open) => !keys.has(open.key));
        if (keep >= 0) close(stack.length - keep);
        const toOpen = token.marks
            .filter((m) => m.type !== 'code' && !stack.some((open) => open.key === markKey(m)))
            .sort((a, b) => span(i, markKey(b)) - span(i, markKey(a))
                || MARK_ORDER.indexOf(a.type) - MARK_ORDER.indexOf(b.type));
        let text = token.k === 'text' ? token.text : '';
        if (token.k === 'text' && toOpen.length && mode === 'markdown') {
            // Emphasis cannot start with a space: emit it before the delimiters.
            const space = /^[ \t]+/.exec(text)?.[0] ?? '';
            out += atLineStart(out) ? '' : space;
            text = text.slice(space.length);
        }
        for (const mark of toOpen) {
            out += openingDelimiter(mark, mode);
            stack.push({ key: markKey(mark), mark });
        }
        const code = token.marks.some((m) => m.type === 'code');
        if (token.k === 'text') {
            if (code) out += mode === 'markdown' ? codeSpan(text, kind) : `<code>${escapeText(text, false, kind)}</code>`;
            else out += escapeText(atLineStart(out) ? text.replace(/^[ \t]+/, '') : text, atLineStart(out), kind);
        } else if (token.k === 'break') {
            out = out.replace(/[ \t]+$/, '');
            out += token.html || kind !== 'paragraph' || mode === 'html' ? '<br>' : '\\\n';
        } else if (token.k === 'image') {
            out += mode === 'markdown'
                ? `![${escapeText(token.alt, false, kind)}](${destination(token.src)}${titlePart(token.title)})`
                : `<img src="${escapeAttribute(token.src)}" alt="${escapeAttribute(token.alt)}"${token.title ? ` title="${escapeAttribute(token.title)}"` : ''}>`;
        } else {
            out += token.html;
        }
    }
    close(stack.length);
    return out.replace(/[ \t]+$/, '');
}

function atLineStart(out: string): boolean {
    return out === '' || out.endsWith('\n');
}

function openingDelimiter(mark: PMMark, mode: 'markdown' | 'html'): string {
    switch (mark.type) {
        case 'bold':
            return mode === 'markdown' ? '**' : '<strong>';
        case 'italic':
            return mode === 'markdown' ? '*' : '<em>';
        case 'strike':
            return mode === 'markdown' ? '~~' : '<del>';
        case 'underline':
            return '<u>';
        case 'link': {
            if (mode === 'markdown') return '[';
            const title = mark.attrs?.title ? ` title="${escapeAttribute(String(mark.attrs.title))}"` : '';
            return `<a href="${escapeAttribute(String(mark.attrs?.href ?? ''))}"${title}>`;
        }
        default:
            return '';
    }
}

function closingDelimiter(mark: PMMark, mode: 'markdown' | 'html'): string {
    switch (mark.type) {
        case 'bold':
            return mode === 'markdown' ? '**' : '</strong>';
        case 'italic':
            return mode === 'markdown' ? '*' : '</em>';
        case 'strike':
            return mode === 'markdown' ? '~~' : '</del>';
        case 'underline':
            return '</u>';
        case 'link':
            return mode === 'markdown'
                ? `](${destination(String(mark.attrs?.href ?? ''))}${titlePart(String(mark.attrs?.title ?? ''))})`
                : '</a>';
        default:
            return '';
    }
}

const isWordChar = (ch: string | undefined) => !!ch && /[\p{L}\p{N}]/u.test(ch);

/** Text as markdown that reads back as exactly this text. */
function escapeText(text: string, lineStart: boolean, kind: InlineKind): string {
    let s = text
        .replace(/[\\`*[\]|]/g, '\\$&')
        .replace(/~(?=~)|(?<=~)~/g, '\\~')
        .replace(/</g, (m, offset: number, str: string) => (/[A-Za-z/!?]/.test(str[offset + 1] ?? '') ? '\\<' : m))
        .replace(/&(?=#?[A-Za-z0-9]+;)/g, '\\&')
        .replace(/\b(https?|ftp):\/\//gi, '$1\\://')
        .replace(/\bwww\./gi, (m) => `${m.slice(0, 3)}\\.`)
        .replace(/([A-Za-z0-9._%+-])@(?=[A-Za-z0-9-]+\.[A-Za-z])/g, '$1\\@');
    s = s.replace(/_/g, (m, offset: number, str: string) => (isWordChar(str[offset - 1]) && isWordChar(str[offset + 1]) ? m : '\\_'));
    if (kind === 'heading') s = s.replace(/#(?=\s*$)/, '\\#');
    if (lineStart) {
        s = s
            .replace(/^(#{1,6})(?=[ \t]|$)/, '\\$1')
            .replace(/^>/, '\\>')
            .replace(/^([-+])(?=[ \t]|$)/, '\\$1')
            .replace(/^(\d{1,9})([.)])(?=[ \t]|$)/, '$1\\$2')
            .replace(/^(=+|-+)([ \t]*)$/, '\\$1$2');
    }
    return s;
}

function codeSpan(text: string, kind: InlineKind): string {
    let value = text.replace(/\n/g, ' ');
    // In a table cell a pipe ends the cell even inside code; \| keeps it.
    if (kind === 'cell') value = value.replace(/\|/g, '\\|');
    const longest = Math.max(0, ...(value.match(/`+/g) ?? []).map((run) => run.length));
    const fence = '`'.repeat(longest + 1);
    const pad = value.startsWith('`') || value.endsWith('`') || (/^ .*[^ ].* $/.test(value)) ? ' ' : '';
    return `${fence}${pad}${value}${pad}${fence}`;
}

const ENTITY_LIKE = /&(?=#?[A-Za-z0-9]+;)/g;

/** A link / image destination that reads back as exactly `url` (entities are decoded in markdown: escape &). */
function destination(url: string): string {
    let depth = 0;
    let balanced = true;
    for (const ch of url) {
        if (ch === '(') depth++;
        if (ch === ')' && --depth < 0) balanced = false;
    }
    if (!url || /[\s<>\\]/.test(url) || !balanced || depth !== 0) {
        return `<${url.replace(/[<>\\]/g, '\\$&').replace(ENTITY_LIKE, '\\&')}>`;
    }
    return url.replace(ENTITY_LIKE, '\\&');
}

function titlePart(title: string): string {
    return title ? ` "${title.replace(/["\\]/g, '\\$&').replace(/&(?=#?[A-Za-z0-9]+;)/g, '\\&')}"` : '';
}

function escapeAttribute(value: string): string {
    return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
