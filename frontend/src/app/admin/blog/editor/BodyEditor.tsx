'use client';

import dynamic from 'next/dynamic';
import { useDeferredValue, useId, useState, type ReactNode } from 'react';
import { AlertTriangle, Eye, FileCode2, Loader2, PenLine } from 'lucide-react';
import { BlogArticle } from '@/components/blog/BlogArticle';
import { THIN_POST_WORDS, countBlogWords, isThinPost, readingTimeLabel } from '@/lib/blogText';
import { markdownToDoc } from './markdownDoc';

// TipTap loads only here, on /admin/blog, when the body editor opens.
const RichTextEditor = dynamic(() => import('./RichTextEditor'), {
    ssr: false,
    loading: () => (
        <p className="flex items-center gap-2 rounded-xl border border-border p-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading the editor…
        </p>
    ),
});

type View = 'visual' | 'markdown' | 'preview';

interface BodyEditorProps {
    value: string;
    onChange: (markdown: string) => void;
    onUploadImage: (file: File) => Promise<{ src: string }>;
    /** The API origin (uploaded /api/... images load from it). */
    imageOrigin: string;
    error?: string;
}

/**
 * The article body: Visual (WYSIWYG, the published look), Markdown (the
 * stored text) and Preview (the exact public renderer). All three edit or show
 * the same markdown; switching tabs never loses a change.
 */
export default function BodyEditor({ value, onChange, onUploadImage, imageOrigin, error }: BodyEditorProps) {
    const uid = useId();
    const [unsupported, setUnsupported] = useState<string[]>(() => markdownToDoc(value).unsupported);
    const [view, setView] = useState<View>(() => (unsupported.length ? 'markdown' : 'visual'));
    const [visualKey, setVisualKey] = useState(0);
    const preview = useDeferredValue(value);
    const words = countBlogWords(value);

    const show = (next: View) => {
        if (next === 'visual') {
            const missing = markdownToDoc(value).unsupported;
            setUnsupported(missing);
            if (missing.length) return;
            setVisualKey((k) => k + 1); // re-read the markdown edited in the other tab
        }
        setView(next);
    };

    return (
        <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="inline-flex rounded-lg border border-border bg-muted/50 p-0.5" role="tablist" aria-label="Body editor">
                    <Tab id={`${uid}-visual`} active={view === 'visual'} onClick={() => show('visual')} icon={<PenLine />}>Visual</Tab>
                    <Tab id={`${uid}-markdown`} active={view === 'markdown'} onClick={() => show('markdown')} icon={<FileCode2 />}>Markdown</Tab>
                    <Tab id={`${uid}-preview`} active={view === 'preview'} onClick={() => show('preview')} icon={<Eye />}>Preview</Tab>
                </div>
                <p className="text-xs text-muted-foreground" aria-live="polite">
                    <strong className="text-foreground">{words.toLocaleString('en-IN')}</strong> words · {readingTimeLabel(words)} read
                    {isThinPost(words) && value.trim() ? (
                        <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 font-semibold text-amber-800 dark:text-amber-300">
                            <AlertTriangle className="h-3 w-3" /> Thin: under {THIN_POST_WORDS} words
                        </span>
                    ) : null}
                </p>
            </div>

            {unsupported.length ? (
                <p className="mb-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-200" role="status">
                    This body uses {unsupported.join(', ')}, which the visual editor cannot show; edit it in the Markdown tab.
                </p>
            ) : null}

            <div role="tabpanel" aria-labelledby={`${uid}-${view}`}>
                {view === 'visual' ? (
                    <RichTextEditor key={visualKey} markdown={value} onChange={onChange} onUploadImage={onUploadImage}
                        imageOrigin={imageOrigin} labelledBy={`${uid}-visual`} />
                ) : view === 'markdown' ? (
                    <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_17rem]">
                        <textarea
                            value={value}
                            onChange={(e) => onChange(e.target.value)}
                            rows={26}
                            spellCheck
                            aria-label="Body (markdown)"
                            aria-invalid={Boolean(error)}
                            className="w-full min-w-0 rounded-xl border border-border bg-background px-4 py-3 font-mono text-[13px] leading-relaxed text-foreground"
                        />
                        <MarkdownHelp />
                    </div>
                ) : (
                    <div className="rounded-xl border border-border bg-background p-5 sm:p-8">
                        {preview.trim()
                            ? <BlogArticle markdown={preview} imageOrigin={imageOrigin} />
                            : <p className="text-sm text-muted-foreground">Nothing to preview yet.</p>}
                    </div>
                )}
            </div>
            {error ? <p className="mt-1 text-xs text-destructive" role="alert">{error}</p> : null}
        </div>
    );
}

function Tab({ id, active, onClick, icon, children }: { id: string; active: boolean; onClick: () => void; icon: ReactNode; children: ReactNode }) {
    return (
        <button id={id} type="button" role="tab" aria-selected={active} onClick={onClick}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors [&_svg]:h-3.5 [&_svg]:w-3.5 ${
                active ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
            }`}>
            {icon}{children}
        </button>
    );
}

const HELP: [string, string][] = [
    ['## Heading', 'section heading (in "On this page")'],
    ['### Sub-heading', 'sub-section'],
    ['**bold** *italic* ~~strike~~', 'emphasis'],
    ['[text](/questions?exam=cms)', 'link (site path or https://)'],
    ['- item / 1. item', 'lists'],
    ['- [ ] item', 'checklist item'],
    ['> text', 'quote'],
    ['> [!TIP]\n> text', 'callout: NOTE, TIP, IMPORTANT, WARNING, CAUTION'],
    ['| A | B |\n|---|---|\n| 1 | 2 |', 'table (:---: centres a column)'],
    ['![alt text](/api/blog/images/… "Caption")', 'image; alone in its paragraph it is a figure'],
    ['---', 'divider line'],
];

function MarkdownHelp() {
    return (
        <aside className="h-fit rounded-xl border border-border bg-card p-3 text-xs" aria-label="Markdown help">
            <p className="mb-2 font-semibold text-foreground">Markdown help</p>
            <p className="mb-2 text-muted-foreground">A new line is a line break; an empty line starts a new paragraph.</p>
            <dl className="space-y-1.5">
                {HELP.map(([syntax, meaning]) => (
                    <div key={syntax}>
                        <dt><code className="whitespace-pre-wrap break-all rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground">{syntax}</code></dt>
                        <dd className="text-muted-foreground">{meaning}</dd>
                    </div>
                ))}
            </dl>
        </aside>
    );
}
