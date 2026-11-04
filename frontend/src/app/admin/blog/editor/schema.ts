/**
 * The visual editor's document schema (TipTap / ProseMirror): what a blog body
 * can hold while it is edited visually. markdownDoc.ts reads markdown into this
 * schema and writes it back; tests/unit/blog-editor-roundtrip.test.ts checks
 * every seeded post survives that unchanged.
 *
 * StarterKit (paragraphs, ## to ######, bold, italic, ~~strike~~, underline,
 * code, links, lists, quotes, code blocks, rules, line breaks, undo) plus:
 *  - tables (GFM: one header row, inline content in cells, column alignment);
 *  - images, inline (a paragraph holding only an image is a figure on the site;
 *    its title is the caption);
 *  - callouts (`> [!NOTE]` ... `> [!CAUTION]`);
 *  - htmlBlock / htmlInline: raw HTML the visual editor cannot show, kept
 *    verbatim (edit it in the Markdown tab);
 *  - attributes markdown needs: a list's tight/loose spacing, a task item's
 *    checked state, a line break written as <br>, a cell's alignment.
 * No React here: the unit tests build this schema in Node.
 */
import { Extension, Node, mergeAttributes, type Extensions } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Code from '@tiptap/extension-code';
import Image from '@tiptap/extension-image';
import { Table, TableCell, TableHeader, TableRow } from '@tiptap/extension-table';
import { CALLOUT_LABELS, calloutKind, type CalloutKind } from '@/lib/blogText';

declare module '@tiptap/core' {
    interface Commands<ReturnType> {
        callout: {
            /** Wrap the selection in a callout, or change the kind of the callout it is in. */
            setCallout: (kind: CalloutKind) => ReturnType;
            /** Turn the callout around the selection back into plain blocks. */
            unsetCallout: () => ReturnType;
        };
    }
}

export type TableAlign = 'left' | 'center' | 'right' | null;

export function tableAlign(value: unknown): TableAlign {
    const v = String(value ?? '').trim().toLowerCase();
    return v === 'left' || v === 'center' || v === 'right' ? v : null;
}

/** Link targets the editor accepts: site paths, #anchors, http(s), mailto and tel. */
export function isSafeHref(href: string): boolean {
    const value = href.trim();
    if (!value || /\s/.test(value)) return false;
    if (value.startsWith('/')) return !value.startsWith('//');
    if (value.startsWith('#')) return true;
    return /^(https?:\/\/[^/\s]+|mailto:[^\s]+|tel:[+\d][\d\s()-]*)/i.test(value);
}

/** An /api/... image path as the editor shows it (on the API origin); the stored src stays the path. */
export function editorImageSrc(src: unknown, imageOrigin = ''): string {
    const value = typeof src === 'string' ? src : '';
    return value.startsWith('/api/') && imageOrigin ? `${imageOrigin.replace(/\/+$/, '')}${value}` : value;
}

/** Attributes markdown needs that StarterKit's nodes do not have. */
export const BlogMarkdownAttributes = Extension.create({
    name: 'blogMarkdownAttributes',
    addGlobalAttributes() {
        return [
            {
                // A loose list (blank lines between items) renders its items as paragraphs.
                types: ['bulletList', 'orderedList'],
                attributes: { tight: { default: true, rendered: false } },
            },
            {
                types: ['listItem'],
                attributes: {
                    checked: {
                        default: null,
                        parseHTML: (el: HTMLElement) => {
                            const value = el.getAttribute('data-checked');
                            return value === null ? null : value === 'true';
                        },
                        renderHTML: (attrs: Record<string, unknown>) =>
                            typeof attrs.checked === 'boolean' ? { 'data-checked': String(attrs.checked) } : {},
                    },
                },
            },
            {
                // 'html': the break was written as <br> (kept so the body round-trips exactly).
                types: ['hardBreak'],
                attributes: { source: { default: null, rendered: false } },
            },
            {
                types: ['tableCell', 'tableHeader'],
                attributes: {
                    align: {
                        default: null,
                        parseHTML: (el: HTMLElement) => tableAlign(el.style.textAlign || el.getAttribute('align')),
                        renderHTML: (attrs: Record<string, unknown>) =>
                            attrs.align ? { style: `text-align: ${tableAlign(attrs.align)}` } : {},
                    },
                },
            },
        ];
    },
});

export const Callout = Node.create({
    name: 'callout',
    group: 'block',
    content: 'block+',
    defining: true,
    addAttributes() {
        return {
            kind: {
                default: 'note',
                parseHTML: (el: HTMLElement) => calloutKind(el.getAttribute('data-callout')),
                renderHTML: () => ({}),
            },
        };
    },
    parseHTML() {
        // The site renders a title paragraph inside the box: never part of the content.
        return [{ tag: 'p.callout-title', ignore: true, priority: 100 }, { tag: 'div[data-callout]' }];
    },
    renderHTML({ node, HTMLAttributes }) {
        const kind = calloutKind(node.attrs.kind);
        return ['div', mergeAttributes(HTMLAttributes, {
            class: `callout callout-${kind}`,
            'data-callout': kind,
            'data-label': CALLOUT_LABELS[kind],
        }), 0];
    },
    addCommands() {
        return {
            setCallout: (kind: CalloutKind) => ({ editor, commands }) =>
                editor.isActive(this.name) ? commands.updateAttributes(this.name, { kind }) : commands.wrapIn(this.name, { kind }),
            unsetCallout: () => ({ commands }) => commands.lift(this.name),
        };
    },
});

/** Raw HTML block the visual editor keeps verbatim (shown as its source). */
export const HtmlBlock = Node.create({
    name: 'htmlBlock',
    group: 'block',
    atom: true,
    selectable: true,
    addAttributes() {
        return { html: { default: '', rendered: false } };
    },
    parseHTML() {
        return [{ tag: 'pre[data-html-block]', getAttrs: (el: HTMLElement) => ({ html: el.textContent ?? '' }) }];
    },
    renderHTML({ node }) {
        return ['pre', { 'data-html-block': '', class: 'html-block', title: 'Raw HTML: edit it in the Markdown tab' }, String(node.attrs.html ?? '')];
    },
});

/** Raw inline HTML (e.g. <sup>) the visual editor keeps verbatim. */
export const HtmlInline = Node.create({
    name: 'htmlInline',
    group: 'inline',
    inline: true,
    atom: true,
    selectable: true,
    addAttributes() {
        return { html: { default: '', rendered: false } };
    },
    parseHTML() {
        return [{ tag: 'code[data-html-inline]', getAttrs: (el: HTMLElement) => ({ html: el.textContent ?? '' }) }];
    },
    renderHTML({ node }) {
        return ['code', { 'data-html-inline': '', class: 'html-inline', title: 'Raw HTML: edit it in the Markdown tab' }, String(node.attrs.html ?? '')];
    },
});

export interface BlogEditorSchemaOptions {
    /** The API origin, to show /api/blog/images/... uploads in the editor. */
    imageOrigin?: string;
}

/** The extensions that define the schema (the editor adds Placeholder on top). */
export function blogSchemaExtensions(options: BlogEditorSchemaOptions = {}): Extensions {
    const imageOrigin = options.imageOrigin ?? '';
    return [
        StarterKit.configure({
            heading: { levels: [2, 3, 4, 5, 6] },
            code: false,
            link: {
                openOnClick: false,
                autolink: true,
                linkOnPaste: true,
                defaultProtocol: 'https',
                HTMLAttributes: { target: null, rel: null, class: null },
                isAllowedUri: (url) => isSafeHref(url),
            },
        }),
        // Markdown allows **`code`** and [`code`](/link): the code mark must not drop other marks.
        Code.extend({ excludes: '' }),
        Image.extend({
            renderHTML({ HTMLAttributes }) {
                return ['img', mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
                    src: editorImageSrc(HTMLAttributes.src, imageOrigin),
                })];
            },
        }).configure({ inline: true, allowBase64: false }),
        Table.configure({ resizable: false, allowTableNodeSelection: true }),
        TableRow,
        // GFM cells hold inline content only.
        TableHeader.extend({ content: 'paragraph+' }),
        TableCell.extend({ content: 'paragraph+' }),
        Callout,
        HtmlBlock,
        HtmlInline,
        BlogMarkdownAttributes,
    ];
}
