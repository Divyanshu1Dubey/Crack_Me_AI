'use client';

/**
 * The visual (WYSIWYG) editor of a blog body. Loaded only on /admin/blog
 * (next/dynamic from BodyEditor), never in the public bundle. The editing
 * surface carries the article's own .blog-prose styles, so it looks like the
 * published post. The body stays markdown: it is read with markdownToDoc and
 * written back with docToMarkdown (see ./markdownDoc.ts) after each change.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { EditorContent, useEditor, useEditorState, type Editor } from '@tiptap/react';
import { Extension } from '@tiptap/core';
import { Placeholder } from '@tiptap/extensions';
import {
    Bold,
    Code2,
    Heading2,
    Heading3,
    ImagePlus,
    Italic,
    Link2,
    List,
    ListOrdered,
    Loader2,
    Minus,
    Pilcrow,
    Quote,
    Redo2,
    Strikethrough,
    Table as TableIcon,
    Underline as UnderlineIcon,
    Undo2,
} from 'lucide-react';
import { CALLOUT_KINDS, CALLOUT_LABELS, type CalloutKind } from '@/lib/blogText';
import { blogSchemaExtensions, editorImageSrc, isSafeHref } from './schema';
import { docToMarkdown, markdownToDoc, type PMNode } from './markdownDoc';

export interface RichTextEditorProps {
    /** The body when the editor opens. */
    markdown: string;
    /** The body as markdown, after each change (not called while nothing changed). */
    onChange: (markdown: string) => void;
    /** Uploads an image; resolves to the path to put in the post. */
    onUploadImage: (file: File) => Promise<{ src: string }>;
    /** The API origin, to show uploaded /api/... images. */
    imageOrigin: string;
    labelledBy?: string;
}

type Panel =
    | { kind: 'link'; href: string; text: string; editing: boolean }
    | { kind: 'image'; src: string; alt: string; caption: string; editing: boolean };

const IMAGE_TYPES = 'image/png,image/jpeg,image/gif,image/webp';
const SERIALIZE_DELAY_MS = 300;

/** What the toolbar shows as active / enabled at the selection. */
function toolbarState(e: Editor) {
    return {
        paragraph: e.isActive('paragraph') && !e.isActive('listItem') && !e.isActive('blockquote') && !e.isActive('callout'),
        h2: e.isActive('heading', { level: 2 }),
        h3: e.isActive('heading', { level: 3 }),
        bold: e.isActive('bold'),
        italic: e.isActive('italic'),
        strike: e.isActive('strike'),
        underline: e.isActive('underline'),
        bullet: e.isActive('bulletList'),
        ordered: e.isActive('orderedList'),
        quote: e.isActive('blockquote'),
        callout: e.isActive('callout') ? (String(e.getAttributes('callout').kind || 'note') as CalloutKind) : null,
        link: e.isActive('link'),
        table: e.isActive('table'),
        image: e.isActive('image'),
        codeBlock: e.isActive('codeBlock'),
        canUndo: e.can().undo(),
        canRedo: e.can().redo(),
    };
}

/** A typed URL as a link target: site paths and #anchors as they are, bare domains get https://. */
export function normalizeHref(value: string): string {
    const v = value.trim();
    if (!v || v.startsWith('/') || v.startsWith('#') || /^[a-z][a-z0-9+.-]*:/i.test(v)) return v;
    return /^[^\s/]+\.[^\s/]+/.test(v) ? `https://${v}` : v;
}

export default function RichTextEditor({ markdown, onChange, onUploadImage, imageOrigin, labelledBy }: RichTextEditorProps) {
    const [panel, setPanel] = useState<Panel | null>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const fileInput = useRef<HTMLInputElement | null>(null);
    const openLinkPanel = useRef<() => void>(() => {});
    const onChangeRef = useRef(onChange);
    useEffect(() => { onChangeRef.current = onChange; }, [onChange]);

    // Read once (BodyEditor remounts the editor to load another body). What the
    // opening body serializes to: no change from it, no onChange; back to it,
    // the exact original text.
    const [opening] = useState(() => {
        const { doc } = markdownToDoc(markdown);
        return { doc, written: docToMarkdown(doc), original: markdown };
    });
    const lastSent = useRef<string>(opening.written);
    const timer = useRef<number | undefined>(undefined);

    const extensions = useMemo(() => [
        ...blogSchemaExtensions({ imageOrigin }),
        Placeholder.configure({
            placeholder: 'Write the post. Type ## for a heading, - for a list, > for a quote; or use the toolbar.',
        }),
        Extension.create({
            name: 'blogEditorShortcuts',
            addKeyboardShortcuts() {
                return { 'Mod-k': () => { openLinkPanel.current(); return true; } };
            },
        }),
    ], [imageOrigin]);

    const flush = useCallback((editor: Editor | null) => {
        window.clearTimeout(timer.current);
        if (!editor || editor.isDestroyed) return;
        const written = docToMarkdown(editor.getJSON() as PMNode);
        if (written === lastSent.current) return;
        lastSent.current = written;
        onChangeRef.current(written === opening.written ? opening.original : written);
    }, [opening]);

    const editor = useEditor({
        extensions,
        content: opening.doc,
        immediatelyRender: false,
        editorProps: {
            attributes: {
                class: 'blog-prose',
                role: 'textbox',
                'aria-multiline': 'true',
                ...(labelledBy ? { 'aria-labelledby': labelledBy } : { 'aria-label': 'Article body' }),
            },
        },
        onUpdate: ({ editor: e }) => {
            window.clearTimeout(timer.current);
            timer.current = window.setTimeout(() => flush(e), SERIALIZE_DELAY_MS);
        },
        onBlur: ({ editor: e }) => flush(e),
    });

    useEffect(() => () => flush(editor), [editor, flush]);

    const live = useEditorState({ editor, selector: ({ editor: e }) => (e ? toolbarState(e) : null) });
    // useEditorState re-reads on the editor's transactions only: until the first
    // one after the editor is created, read the state directly.
    const state = live ?? (editor ? toolbarState(editor) : null);

    const showLinkPanel = useCallback(() => {
        if (!editor) return;
        const { from, to } = editor.state.selection;
        const href = String(editor.getAttributes('link').href ?? '');
        setPanel({ kind: 'link', href, text: editor.state.doc.textBetween(from, to, ' '), editing: Boolean(href) });
    }, [editor]);
    useEffect(() => { openLinkPanel.current = showLinkPanel; }, [showLinkPanel]);

    if (!editor || !state) {
        return <p className="flex items-center gap-2 p-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading the editor…</p>;
    }

    const chain = () => editor.chain().focus();

    const pickImage = () => {
        setUploadError(null);
        fileInput.current?.click();
    };

    const upload = async (file: File) => {
        setUploading(true);
        setUploadError(null);
        try {
            const { src } = await onUploadImage(file);
            setPanel({ kind: 'image', src, alt: file.name.replace(/\.[a-z0-9]+$/i, '').replace(/[-_]+/g, ' ').trim(), caption: '', editing: false });
        } catch (err) {
            setUploadError(err instanceof Error && err.message ? err.message : 'The upload failed.');
        } finally {
            setUploading(false);
        }
    };

    const editImage = () => {
        const attrs = editor.getAttributes('image');
        setPanel({ kind: 'image', src: String(attrs.src ?? ''), alt: String(attrs.alt ?? ''), caption: String(attrs.title ?? ''), editing: true });
    };

    return (
        // No overflow-hidden here: it would make this box the toolbar's sticky container
        // (the toolbar then sat 4rem down, over the text). The toolbar sticks under the
        // app's 4rem header while the page scrolls.
        <div className="min-w-0 rounded-xl border border-border bg-background">
            <div role="toolbar" aria-label="Formatting" className="sticky top-16 z-10 flex flex-wrap items-center gap-1 rounded-t-xl border-b border-border bg-card/95 p-1.5 backdrop-blur">
                <ToolButton label="Undo (Ctrl+Z)" disabled={!state.canUndo} onClick={() => chain().undo().run()}><Undo2 /></ToolButton>
                <ToolButton label="Redo (Ctrl+Shift+Z)" disabled={!state.canRedo} onClick={() => chain().redo().run()}><Redo2 /></ToolButton>
                <Divider />
                <ToolButton label="Paragraph text" active={state.paragraph} onClick={() => chain().setParagraph().run()}><Pilcrow /></ToolButton>
                <ToolButton label="Section heading (H2)" active={state.h2} onClick={() => chain().toggleHeading({ level: 2 }).run()}><Heading2 /></ToolButton>
                <ToolButton label="Sub-heading (H3)" active={state.h3} onClick={() => chain().toggleHeading({ level: 3 }).run()}><Heading3 /></ToolButton>
                <Divider />
                <ToolButton label="Bold (Ctrl+B)" active={state.bold} onClick={() => chain().toggleBold().run()}><Bold /></ToolButton>
                <ToolButton label="Italic (Ctrl+I)" active={state.italic} onClick={() => chain().toggleItalic().run()}><Italic /></ToolButton>
                <ToolButton label="Strikethrough" active={state.strike} onClick={() => chain().toggleStrike().run()}><Strikethrough /></ToolButton>
                <ToolButton label="Underline (Ctrl+U)" active={state.underline} onClick={() => chain().toggleUnderline().run()}><UnderlineIcon /></ToolButton>
                <ToolButton label="Link (Ctrl+K)" active={state.link} onClick={showLinkPanel}><Link2 /></ToolButton>
                <Divider />
                <ToolButton label="Bulleted list" active={state.bullet} onClick={() => chain().toggleBulletList().run()}><List /></ToolButton>
                <ToolButton label="Numbered list" active={state.ordered} onClick={() => chain().toggleOrderedList().run()}><ListOrdered /></ToolButton>
                <ToolButton label="Quote" active={state.quote} onClick={() => chain().toggleBlockquote().run()}><Quote /></ToolButton>
                <label className="sr-only" htmlFor="blog-callout-kind">Callout</label>
                <select
                    id="blog-callout-kind"
                    value={state.callout ?? ''}
                    onChange={(e) => {
                        const value = e.target.value;
                        if (value === 'remove') chain().unsetCallout().run();
                        else if (value) chain().setCallout(value as CalloutKind).run();
                    }}
                    className={`h-8 rounded-md border px-1.5 text-xs font-semibold ${state.callout ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-background text-foreground'}`}
                    title="Callout box: Note, Tip, Important, Warning or Caution"
                >
                    <option value="">{state.callout ? 'Callout' : 'Callout…'}</option>
                    {CALLOUT_KINDS.map((kind) => <option key={kind} value={kind}>{CALLOUT_LABELS[kind]}</option>)}
                    {state.callout ? <option value="remove">Remove callout</option> : null}
                </select>
                <Divider />
                <ToolButton label={state.table ? 'Table (you are in one)' : 'Insert a table'} active={state.table}
                    onClick={() => { if (!state.table) chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); }}><TableIcon /></ToolButton>
                <ToolButton label={uploading ? 'Uploading…' : 'Upload an image'} disabled={uploading} onClick={pickImage}>
                    {uploading ? <Loader2 className="animate-spin" /> : <ImagePlus />}
                </ToolButton>
                <ToolButton label="Divider line" onClick={() => chain().setHorizontalRule().run()}><Minus /></ToolButton>
                <ToolButton label="Code block" active={state.codeBlock} onClick={() => chain().toggleCodeBlock().run()}><Code2 /></ToolButton>
                <input ref={fileInput} type="file" accept={IMAGE_TYPES} className="hidden" tabIndex={-1} aria-hidden="true"
                    onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void upload(file); }} />
            </div>

            {state.table ? (
                <div className="flex flex-wrap items-center gap-1 border-b border-border bg-muted/40 px-2 py-1.5 text-xs" role="toolbar" aria-label="Table">
                    <span className="mr-1 font-semibold text-muted-foreground">Table:</span>
                    <SmallButton onClick={() => chain().addRowBefore().run()}>Row above</SmallButton>
                    <SmallButton onClick={() => chain().addRowAfter().run()}>Row below</SmallButton>
                    <SmallButton onClick={() => chain().addColumnBefore().run()}>Column left</SmallButton>
                    <SmallButton onClick={() => chain().addColumnAfter().run()}>Column right</SmallButton>
                    <SmallButton onClick={() => chain().deleteRow().run()}>Delete row</SmallButton>
                    <SmallButton onClick={() => chain().deleteColumn().run()}>Delete column</SmallButton>
                    <SmallButton danger onClick={() => chain().deleteTable().run()}>Delete table</SmallButton>
                </div>
            ) : null}
            {state.image && panel?.kind !== 'image' ? (
                <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/40 px-2 py-1.5 text-xs">
                    <span className="font-semibold text-muted-foreground">Image:</span>
                    <SmallButton onClick={editImage}>Edit alt text and caption</SmallButton>
                    <SmallButton danger onClick={() => chain().deleteSelection().run()}>Remove image</SmallButton>
                </div>
            ) : null}
            {uploadError ? <p className="border-b border-border bg-destructive/10 px-3 py-2 text-xs text-destructive" role="alert">{uploadError}</p> : null}

            {panel?.kind === 'link' ? (
                <LinkPanel
                    panel={panel}
                    onChange={setPanel}
                    onCancel={() => { setPanel(null); editor.commands.focus(); }}
                    onRemove={() => { chain().extendMarkRange('link').unsetLink().run(); setPanel(null); }}
                    onApply={(href, text) => {
                        const target = normalizeHref(href);
                        if (editor.state.selection.empty && !editor.isActive('link')) {
                            chain().insertContent({ type: 'text', text: text.trim() || target, marks: [{ type: 'link', attrs: { href: target } }] }).run();
                        } else {
                            chain().extendMarkRange('link').setLink({ href: target }).run();
                        }
                        setPanel(null);
                    }}
                />
            ) : null}
            {panel?.kind === 'image' ? (
                <ImagePanel
                    panel={panel}
                    preview={editorImageSrc(panel.src, imageOrigin)}
                    onChange={setPanel}
                    onCancel={() => { setPanel(null); editor.commands.focus(); }}
                    onApply={(alt, caption) => {
                        const attrs = { src: panel.src, alt: alt.trim(), title: caption.trim() || null };
                        if (panel.editing) chain().updateAttributes('image', attrs).run();
                        // Its own paragraph: on the site an image alone in a paragraph is a figure with its caption.
                        else chain().insertContent([{ type: 'paragraph', content: [{ type: 'image', attrs }] }]).run();
                        setPanel(null);
                    }}
                />
            ) : null}

            <EditorContent editor={editor} />
        </div>
    );
}

function ToolButton({ label, active = false, disabled = false, onClick, children }: {
    label: string; active?: boolean; disabled?: boolean; onClick: () => void; children: ReactNode;
}) {
    return (
        <button
            type="button"
            title={label}
            aria-label={label}
            aria-pressed={active}
            disabled={disabled}
            onMouseDown={(e) => e.preventDefault()} // keep the editor's selection
            onClick={onClick}
            className={`inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors disabled:opacity-40 [&_svg]:h-4 [&_svg]:w-4 ${
                active ? 'bg-primary text-primary-foreground' : 'text-foreground hover:bg-muted'
            }`}
        >
            {children}
        </button>
    );
}

function SmallButton({ onClick, danger = false, children }: { onClick: () => void; danger?: boolean; children: ReactNode }) {
    return (
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={onClick}
            className={`rounded-md border px-2 py-1 font-medium transition-colors ${danger ? 'border-destructive/40 text-destructive hover:bg-destructive/10' : 'border-border bg-background text-foreground hover:bg-muted'}`}>
            {children}
        </button>
    );
}

function Divider() {
    return <span className="mx-0.5 h-5 w-px bg-border" aria-hidden="true" />;
}

const PANEL = 'flex flex-wrap items-end gap-2 border-b border-border bg-accent/40 p-3 text-sm';
const PANEL_INPUT = 'h-9 w-full rounded-md border border-border bg-background px-2.5 text-sm text-foreground';

/**
 * Enter applies, Escape cancels. The panels sit inside the post's <form>, so
 * they are groups, not forms (a nested form is invalid HTML and Enter would
 * submit the whole post).
 */
function panelKeys(apply: () => void, cancel: () => void) {
    return (e: KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            apply();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancel();
        }
    };
}

function LinkPanel({ panel, onChange, onApply, onRemove, onCancel }: {
    panel: Extract<Panel, { kind: 'link' }>;
    onChange: (p: Panel) => void;
    onApply: (href: string, text: string) => void;
    onRemove: () => void;
    onCancel: () => void;
}) {
    const target = normalizeHref(panel.href);
    const valid = isSafeHref(target);
    const apply = () => { if (valid) onApply(panel.href, panel.text); };
    return (
        <div role="group" className={PANEL} onKeyDown={panelKeys(apply, onCancel)} aria-label="Link">
            <label className="min-w-0 flex-1 basis-60">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Link to (a page such as /questions?exam=cms, or https://…)</span>
                <input autoFocus className={PANEL_INPUT} value={panel.href} placeholder="/questions?exam=cms"
                    onChange={(e) => onChange({ ...panel, href: e.target.value })} aria-invalid={Boolean(panel.href) && !valid} />
            </label>
            {!panel.editing && !panel.text ? (
                <label className="min-w-0 flex-1 basis-48">
                    <span className="mb-1 block text-xs font-medium text-muted-foreground">Text to show</span>
                    <input className={PANEL_INPUT} value={panel.text} placeholder="Practise the PYQs"
                        onChange={(e) => onChange({ ...panel, text: e.target.value })} />
                </label>
            ) : null}
            <div className="flex gap-2">
                <button type="button" onClick={apply} disabled={!valid} className="h-9 rounded-md bg-primary px-3 text-sm font-semibold text-primary-foreground disabled:opacity-50">
                    {panel.editing ? 'Update link' : 'Add link'}
                </button>
                {panel.editing ? <button type="button" onClick={onRemove} className="h-9 rounded-md border border-border px-3 text-sm">Remove link</button> : null}
                <button type="button" onClick={onCancel} className="h-9 rounded-md px-3 text-sm text-muted-foreground hover:text-foreground">Cancel</button>
            </div>
            {panel.href && !valid ? <p className="w-full text-xs text-destructive">Use a site path (/…), #anchor, https://, mailto: or tel: link.</p> : null}
        </div>
    );
}

function ImagePanel({ panel, preview, onChange, onApply, onCancel }: {
    panel: Extract<Panel, { kind: 'image' }>;
    preview: string;
    onChange: (p: Panel) => void;
    onApply: (alt: string, caption: string) => void;
    onCancel: () => void;
}) {
    const valid = panel.alt.trim().length > 0;
    const apply = () => { if (valid) onApply(panel.alt, panel.caption); };
    return (
        <div role="group" className={PANEL} onKeyDown={panelKeys(apply, onCancel)} aria-label="Image">
            <img src={preview} alt="" className="h-16 w-24 rounded-md border border-border object-cover" />
            <label className="min-w-0 flex-1 basis-56">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Alt text: what the image shows (read aloud to blind readers)</span>
                <input autoFocus className={PANEL_INPUT} value={panel.alt} placeholder="ECG: ST elevation in leads II, III and aVF"
                    onChange={(e) => onChange({ ...panel, alt: e.target.value })} aria-invalid={!valid} />
            </label>
            <label className="min-w-0 flex-1 basis-56">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Caption under the image (optional)</span>
                <input className={PANEL_INPUT} value={panel.caption} placeholder="Inferior wall MI"
                    onChange={(e) => onChange({ ...panel, caption: e.target.value })} />
            </label>
            <div className="flex gap-2">
                <button type="button" onClick={apply} disabled={!valid} className="h-9 rounded-md bg-primary px-3 text-sm font-semibold text-primary-foreground disabled:opacity-50">
                    {panel.editing ? 'Update image' : 'Insert image'}
                </button>
                <button type="button" onClick={onCancel} className="h-9 rounded-md px-3 text-sm text-muted-foreground hover:text-foreground">Cancel</button>
            </div>
        </div>
    );
}
