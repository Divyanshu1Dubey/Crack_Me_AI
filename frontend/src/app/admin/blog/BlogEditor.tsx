'use client';

import React, { useCallback, useDeferredValue, useEffect, useId, useRef, useState } from 'react';
import { ExternalLink, ListTree, Loader2, Save, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FormattedText } from '@/components/FormattedText';
import { authors } from '@/content/authors';
import { blogAPI, type BlogPostAdmin } from '@/lib/blogAPI';
import RowsEditor from './RowsEditor';
import {
    FIELD_FOR_INPUT,
    type BlogFormState,
    type FormErrors,
    apiFieldErrors,
    describeBlogError,
    emptyBlogForm,
    estimateReadingTime,
    formFromPost,
    formToPayload,
    formsDiffer,
    isStubBody,
    slugify,
    tocFromBody,
    todayIso,
    wordCountOf,
} from './blogForm';

interface BlogEditorProps {
    /** null: a new post. */
    postId: number | null;
    /** Existing categories, offered as suggestions. */
    categories: string[];
    onSaved: (post: BlogPostAdmin, created: boolean) => void;
    onClose: () => void;
}

const INPUT = 'w-full min-w-0 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground';
const PROFILES = Object.values(authors).map((a) => ({ slug: a.slug, name: a.name, role: a.role }));
const INPUT_FOR_FIELD: Record<string, string> = Object.fromEntries(Object.entries(FIELD_FOR_INPUT).map(([k, v]) => [v, k]));

function Section({ title, children, description }: { title: string; description?: string; children: React.ReactNode }) {
    return (
        <section className="min-w-0 rounded-xl border border-border bg-card p-4">
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
            <div className="mt-3 grid min-w-0 gap-3 sm:grid-cols-2">{children}</div>
        </section>
    );
}

function Field({ id, label, hint, error, wide, children }: {
    id: string; label: string; hint?: React.ReactNode; error?: string; wide?: boolean; children: React.ReactNode;
}) {
    return (
        <div className={`min-w-0 ${wide ? 'sm:col-span-2' : ''}`}>
            <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted-foreground">{label}</label>
            {children}
            {hint && <div id={`${id}-hint`} className="mt-1 text-xs text-muted-foreground">{hint}</div>}
            {error && <p id={`${id}-error`} className="mt-1 text-xs text-destructive" role="alert">{error}</p>}
        </div>
    );
}

function Counter({ value, limit }: { value: string; limit: number }) {
    const n = value.trim().length;
    return <span className={n > limit ? 'text-amber-700 dark:text-amber-400' : ''}>{n}/{limit} characters{n > limit ? ' (search results cut it)' : ''}</span>;
}

export default function BlogEditor({ postId, categories, onSaved, onClose }: BlogEditorProps) {
    const uid = useId();
    const id = (name: string) => `${uid}-${name}`;
    const [form, setForm] = useState<BlogFormState | null>(postId ? null : emptyBlogForm(todayIso(), PROFILES[0]));
    const [initial, setInitial] = useState<BlogFormState | null>(form);
    const [savedSlug, setSavedSlug] = useState<string>('');
    const [loadError, setLoadError] = useState<string | null>(null);
    const [errors, setErrors] = useState<FormErrors>({});
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [slugTouched, setSlugTouched] = useState(Boolean(postId));
    const [bodyView, setBodyView] = useState<'write' | 'preview'>('write');
    const summaryRef = useRef<HTMLDivElement | null>(null);
    const deferredBody = useDeferredValue(form?.body ?? '');

    const load = useCallback(async () => {
        if (!postId) return;
        setLoadError(null);
        try {
            const res = await blogAPI.get(postId);
            const loaded = formFromPost(res.data);
            setForm(loaded);
            setInitial(loaded);
            setSavedSlug(res.data.slug);
        } catch (err) {
            setLoadError(describeBlogError(err, 'loading the post'));
        }
    }, [postId]);

    useEffect(() => { load(); }, [load]);

    const dirty = Boolean(form && initial && formsDiffer(form, initial));
    useEffect(() => {
        if (!dirty) return;
        const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
        window.addEventListener('beforeunload', warn);
        return () => window.removeEventListener('beforeunload', warn);
    }, [dirty]);

    if (loadError) {
        return (
            <div className="rounded-xl border border-border bg-card p-6 text-center">
                <p className="mb-3 text-sm text-destructive" role="alert">{loadError}</p>
                <div className="flex justify-center gap-2">
                    <Button variant="outline" onClick={load}>Retry</Button>
                    <Button variant="ghost" onClick={onClose}>Back to all posts</Button>
                </div>
            </div>
        );
    }
    if (!form) {
        return <p className="flex items-center gap-2 p-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading the post…</p>;
    }

    const set = <K extends keyof BlogFormState>(key: K, value: BlogFormState[K]) => {
        setForm((prev) => {
            if (!prev) return prev;
            const next = { ...prev, [key]: value };
            if (key === 'title' && !slugTouched) next.slug = slugify(String(value));
            return next;
        });
    };

    const setProfile = (key: 'authorId' | 'reviewedBy', slug: string) => {
        setForm((prev) => {
            if (!prev) return prev;
            const next = { ...prev, [key]: slug };
            if (key === 'authorId') {
                const before = PROFILES.find((p) => p.slug === prev.authorId);
                const after = PROFILES.find((p) => p.slug === slug);
                if (after && (!prev.author || prev.author === before?.name)) next.author = after.name;
                if (after && (!prev.authorRole || prev.authorRole === before?.role)) next.authorRole = after.role;
            }
            return next;
        });
    };

    const close = () => {
        if (dirty && !window.confirm('Discard your unsaved changes to this post?')) return;
        onClose();
    };

    const save = async (event: React.FormEvent) => {
        event.preventDefault();
        setSaveError(null);
        const { payload, errors: problems } = formToPayload(form);
        setErrors(problems);
        if (Object.keys(problems).length) {
            setSaveError('Fix the fields marked below, then save again.');
            summaryRef.current?.scrollIntoView({ block: 'start' });
            return;
        }
        setSaving(true);
        try {
            const res = postId ? await blogAPI.update(postId, payload) : await blogAPI.create(payload);
            const saved = formFromPost(res.data);
            setForm(saved);
            setInitial(saved);
            setSavedSlug(res.data.slug);
            setSlugTouched(true);
            onSaved(res.data, !postId);
        } catch (err) {
            const fields = apiFieldErrors(err);
            const mapped: FormErrors = {};
            for (const [field, text] of Object.entries(fields)) mapped[INPUT_FOR_FIELD[field] ?? field] = text;
            setErrors(mapped);
            setSaveError(describeBlogError(err, 'saving the post'));
            summaryRef.current?.scrollIntoView({ block: 'start' });
        } finally {
            setSaving(false);
        }
    };

    const describedBy = (name: string) => [errors[name] ? `${id(name)}-error` : '', `${id(name)}-hint`].filter(Boolean).join(' ') || undefined;
    const input = (name: keyof BlogFormState & string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
        <input id={id(name)} className={INPUT} value={String(form[name] ?? '')} aria-invalid={Boolean(errors[name])}
            aria-describedby={describedBy(name)} onChange={(e) => set(name, e.target.value as never)} {...extra} />
    );
    const area = (name: keyof BlogFormState & string, rows: number, extra: React.TextareaHTMLAttributes<HTMLTextAreaElement> = {}) => (
        <textarea id={id(name)} className={INPUT} rows={rows} value={String(form[name] ?? '')} aria-invalid={Boolean(errors[name])}
            aria-describedby={describedBy(name)} onChange={(e) => set(name, e.target.value as never)} {...extra} />
    );
    const slugChanged = Boolean(postId && savedSlug && form.slug.trim() !== savedSlug);
    const profileKnown = (slug: string) => PROFILES.some((p) => p.slug === slug);
    const errorCount = Object.keys(errors).length;

    return (
        <form onSubmit={save} noValidate aria-labelledby={id('heading')} className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <Button type="button" variant="ghost" size="sm" onClick={close}>← All posts</Button>
                    <h1 id={id('heading')} className="text-xl font-semibold text-foreground">{postId ? 'Edit post' : 'New post'}</h1>
                    <Badge variant={form.isPublished ? 'success' : 'secondary'}>{form.isPublished ? 'Published' : 'Draft'}</Badge>
                    {dirty && <span className="text-xs text-amber-700 dark:text-amber-400">Unsaved changes</span>}
                </div>
                <div className="flex flex-wrap gap-2">
                    {postId && initial?.isPublished && savedSlug && (
                        <a href={`/blog/${savedSlug}`} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm text-foreground hover:bg-accent">
                            <ExternalLink className="h-4 w-4" /> View
                        </a>
                    )}
                    <Button type="button" variant="outline" size="sm" onClick={close}><X className="h-4 w-4" /> Cancel</Button>
                    <Button type="submit" size="sm" disabled={saving}>
                        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
                    </Button>
                </div>
            </div>

            <div ref={summaryRef} className="scroll-mt-20">
                {saveError && (
                    <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
                        <p>{saveError}</p>
                        {errorCount > 0 && <p className="mt-1 text-xs">{errorCount} field{errorCount === 1 ? '' : 's'} need attention.</p>}
                    </div>
                )}
            </div>

            <Section title="Post" description="Title, address and the texts search results and cards show.">
                <Field id={id('title')} label="Title" wide error={errors.title} hint={<Counter value={form.title} limit={60} />}>
                    {input('title', { required: true })}
                </Field>
                <Field id={id('slug')} label="Slug (the address: /blog/slug)" wide error={errors.slug}
                    hint={slugChanged
                        ? <span className="text-amber-700 dark:text-amber-400">Changing the slug changes the address; links to /blog/{savedSlug} will stop working.</span>
                        : 'Lowercase letters, numbers and hyphens.'}>
                    <input id={id('slug')} className={INPUT} value={form.slug} aria-invalid={Boolean(errors.slug)}
                        aria-describedby={describedBy('slug')} spellCheck={false}
                        onChange={(e) => { setSlugTouched(true); set('slug', e.target.value); }} />
                </Field>
                <Field id={id('description')} label="SEO description" wide error={errors.description}
                    hint={<Counter value={form.description} limit={160} />}>
                    {area('description', 2)}
                </Field>
                <Field id={id('excerpt')} label="Excerpt (cards and the post intro)" wide error={errors.excerpt}
                    hint={<Counter value={form.excerpt} limit={180} />}>
                    {area('excerpt', 3)}
                </Field>
            </Section>

            <section className="min-w-0 rounded-xl border border-border bg-card p-4" aria-labelledby={id('body-heading')}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 id={id('body-heading')} className="text-base font-semibold text-foreground">Article body</h2>
                    <div className="flex gap-1 lg:hidden" role="tablist" aria-label="Body view">
                        {(['write', 'preview'] as const).map((view) => (
                            <button key={view} type="button" role="tab" aria-selected={bodyView === view} onClick={() => setBodyView(view)}
                                className={`rounded-full border px-3 py-1 text-xs ${bodyView === view ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-foreground hover:bg-accent'}`}>
                                {view === 'write' ? 'Write' : 'Preview'}
                            </button>
                        ))}
                    </div>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    Markdown: ## headings, lists, **bold**, [links](/cms) and tables. The preview renders it the way the post page does.
                </p>
                <div className="mt-3 grid min-w-0 gap-3 lg:grid-cols-2">
                    <div className={`min-w-0 ${bodyView === 'preview' ? 'hidden lg:block' : ''}`}>
                        <label htmlFor={id('body')} className="mb-1 block text-xs font-medium text-muted-foreground">Body (markdown)</label>
                        <textarea id={id('body')} value={form.body} rows={22} spellCheck
                            aria-invalid={Boolean(errors.body)} aria-describedby={describedBy('body')}
                            onChange={(e) => set('body', e.target.value)}
                            className={`${INPUT} font-mono text-[13px] leading-relaxed`} />
                        <div id={`${id('body')}-hint`} className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            <span>{wordCountOf(form.body)} words · about {estimateReadingTime(form.body)}</span>
                            <Button type="button" variant="outline" size="sm" onClick={() => {
                                set('wordCount', String(wordCountOf(form.body)));
                                set('readingTime', estimateReadingTime(form.body));
                            }}>Use for word count and reading time</Button>
                        </div>
                        {errors.body && <p id={`${id('body')}-error`} className="mt-1 text-xs text-destructive" role="alert">{errors.body}</p>}
                    </div>
                    <div className={`min-w-0 ${bodyView === 'write' ? 'hidden lg:block' : ''}`} role="region" aria-label="Body preview">
                        <p className="mb-1 text-xs font-medium text-muted-foreground">Preview</p>
                        <div className="blog-article max-h-[70vh] min-w-0 overflow-y-auto rounded-md border border-border bg-background p-3 text-foreground">
                            {deferredBody.trim()
                                ? <FormattedText text={deferredBody} />
                                : <p className="text-sm text-muted-foreground">Nothing to preview yet.</p>}
                        </div>
                    </div>
                </div>
            </section>

            <Section title="Classification">
                <Field id={id('category')} label="Category (its page: /blog/category/…)" error={errors.category}>
                    {input('category', { list: id('categories') })}
                    <datalist id={id('categories')}>
                        {categories.map((c) => <option key={c} value={c} />)}
                    </datalist>
                </Field>
                <Field id={id('subcategory')} label="Subcategory" error={errors.subcategory}>{input('subcategory')}</Field>
                <Field id={id('tags')} label="Tags (comma-separated)" wide error={errors.tags}
                    hint="Each tag has a page at /blog/tag/…; tags with 3 or more posts are indexed.">
                    {input('tags', { placeholder: 'UPSC CMS, Physiology, High-Yield' })}
                </Field>
                <Field id={id('difficulty')} label="Difficulty" error={errors.difficulty}>
                    <select id={id('difficulty')} className={INPUT} value={form.difficulty}
                        onChange={(e) => set('difficulty', e.target.value as BlogFormState['difficulty'])}>
                        <option value="beginner">Beginner</option>
                        <option value="intermediate">Intermediate</option>
                        <option value="advanced">Advanced</option>
                    </select>
                </Field>
            </Section>

            <Section title="Byline and dates" description="Profiles come from the site's author list (src/content/authors.ts).">
                <Field id={id('authorId')} label="Author profile" error={errors.authorId}>
                    <select id={id('authorId')} className={INPUT} value={form.authorId} onChange={(e) => setProfile('authorId', e.target.value)}>
                        {!profileKnown(form.authorId) && <option value={form.authorId}>{form.authorId || 'Choose a profile'} (not a registered profile)</option>}
                        {PROFILES.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
                    </select>
                </Field>
                <Field id={id('reviewedBy')} label="Reviewed by" error={errors.reviewedBy}>
                    <select id={id('reviewedBy')} className={INPUT} value={form.reviewedBy} onChange={(e) => setProfile('reviewedBy', e.target.value)}>
                        <option value="">No reviewer</option>
                        {form.reviewedBy && !profileKnown(form.reviewedBy) && <option value={form.reviewedBy}>{form.reviewedBy} (not a registered profile)</option>}
                        {PROFILES.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
                    </select>
                </Field>
                <Field id={id('author')} label="Author name (byline)" error={errors.author}>{input('author')}</Field>
                <Field id={id('authorRole')} label="Author role" error={errors.authorRole}>{input('authorRole')}</Field>
                <Field id={id('datePublished')} label="Published on" error={errors.datePublished}>{input('datePublished', { type: 'date' })}</Field>
                <Field id={id('dateModified')} label="Modified on (structured data)" error={errors.dateModified}
                    hint={<button type="button" className="text-primary hover:underline" onClick={() => set('dateModified', todayIso())}>Set to today</button>}>
                    {input('dateModified', { type: 'date' })}
                </Field>
                <Field id={id('updatedAt')} label={'Updated on (shown as "Updated …")'} error={errors.updatedAt}
                    hint={<button type="button" className="text-primary hover:underline" onClick={() => set('updatedAt', todayIso())}>Set to today</button>}>
                    {input('updatedAt', { type: 'date' })}
                </Field>
                <Field id={id('readingTime')} label="Reading time" error={errors.readingTime}>{input('readingTime', { placeholder: '8 min' })}</Field>
                <Field id={id('wordCount')} label="Word count" error={errors.wordCount}>{input('wordCount', { inputMode: 'numeric' })}</Field>
            </Section>

            <Section title="Call to action and links" description="The button under the post title and at the end of the post.">
                <Field id={id('ctaLabel')} label="Button label" error={errors.cta}>{input('ctaLabel', { placeholder: 'Practise 50 matched PYQs' })}</Field>
                <Field id={id('ctaHref')} label="Button link">{input('ctaHref', { placeholder: '/questions?exam=cms' })}</Field>
                <Field id={id('ctaEventName')} label="Analytics event name">{input('ctaEventName', { placeholder: 'blog_practice_intent' })}</Field>
                <Field id={id('ctaEventParams')} label="Analytics event parameters (JSON)">
                    {area('ctaEventParams', 3, { spellCheck: false, placeholder: '{"source": "my-post", "surface": "inline_cta"}', className: `${INPUT} font-mono text-xs` })}
                </Field>
                <Field id={id('relatedExamPaths')} label="Related pages (one path per line)" error={errors.relatedExamPaths}>
                    {area('relatedExamPaths', 3, { spellCheck: false, placeholder: '/cms\n/neet-pg' })}
                </Field>
                <Field id={id('coverImage')} label="Cover image (optional)" error={errors.coverImage}
                    hint="The post page and social cards use the generated image; this path is stored only.">
                    {input('coverImage', { placeholder: '/blog/my-cover.png' })}
                </Field>
            </Section>

            <div className="grid min-w-0 gap-4 xl:grid-cols-2">
                <RowsEditor legend="FAQs" hint="Shown at the end of the post and sent to search engines as FAQ data."
                    rows={form.faqs} blank={{ q: '', a: '' }} addLabel="Add FAQ" error={errors.faqs}
                    columns={[{ key: 'q', label: 'Question', wide: true }, { key: 'a', label: 'Answer', multiline: true }]}
                    onChange={(rows) => set('faqs', rows)} />
                <RowsEditor legend="Table of contents" hint="Empty: the post page lists the ## headings itself."
                    rows={form.toc} blank={{ id: '', label: '' }} addLabel="Add entry" error={errors.toc}
                    columns={[{ key: 'label', label: 'Label' }, { key: 'id', label: 'Anchor id' }]}
                    onChange={(rows) => set('toc', rows)}
                    actions={(
                        <Button type="button" variant="outline" size="sm" onClick={() => set('toc', tocFromBody(form.body))}>
                            <ListTree className="h-4 w-4" /> Build from ## headings
                        </Button>
                    )} />
                <RowsEditor legend="References" hint="Listed under the post and cited in its structured data."
                    rows={form.references} blank={{ label: '', url: '', published: '' }} addLabel="Add reference" error={errors.references}
                    columns={[{ key: 'label', label: 'Reference', wide: true }, { key: 'url', label: 'Link (optional)', type: 'url' },
                        { key: 'published', label: 'Published (optional)' }]}
                    onChange={(rows) => set('references', rows)} />
                <RowsEditor legend="Revision log" hint="Shown at the end of the post, oldest first."
                    rows={form.revisionLog} blank={{ date: todayIso(), note: '' }} addLabel="Add revision" error={errors.revisionLog}
                    columns={[{ key: 'date', label: 'Date', type: 'date' }, { key: 'note', label: 'What changed', wide: true }]}
                    onChange={(rows) => set('revisionLog', rows)} />
            </div>

            <details className="min-w-0 rounded-xl border border-border bg-card p-4">
                <summary className="cursor-pointer text-base font-semibold text-foreground">Prelude and outro (markdown, optional)</summary>
                <p className="mt-1 text-xs text-muted-foreground">Stored with the post; the post page does not display them at present.</p>
                <div className="mt-3 grid min-w-0 gap-3 sm:grid-cols-2">
                    <Field id={id('prelude')} label="Prelude" error={errors.prelude}>{area('prelude', 4)}</Field>
                    <Field id={id('outro')} label="Outro" error={errors.outro}>{area('outro', 4)}</Field>
                </div>
            </details>

            <section className="min-w-0 rounded-xl border border-border bg-card p-4" aria-labelledby={id('visibility')}>
                <h2 id={id('visibility')} className="text-base font-semibold text-foreground">Visibility</h2>
                <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-sm text-foreground">
                    <label className="flex items-center gap-2">
                        <input type="checkbox" checked={form.isPublished} onChange={(e) => set('isPublished', e.target.checked)}
                            aria-describedby={errors.isPublished ? `${id('isPublished')}-error` : undefined} />
                        Published (on /blog)
                    </label>
                    <label className="flex items-center gap-2">
                        <input type="checkbox" checked={form.pinned} onChange={(e) => set('pinned', e.target.checked)} /> Pinned
                    </label>
                    <label className="flex items-center gap-2">
                        <input type="checkbox" checked={form.trending} onChange={(e) => set('trending', e.target.checked)} /> Trending
                    </label>
                </div>
                {errors.isPublished && <p id={`${id('isPublished')}-error`} className="mt-1 text-xs text-destructive" role="alert">{errors.isPublished}</p>}
                {form.isPublished && isStubBody(form.body) && !errors.isPublished && (
                    <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">A post without a body is not shown on the site.</p>
                )}
                <p className="mt-2 text-xs text-muted-foreground">Saved changes reach the public blog, its feed and the sitemap within about 10 minutes.</p>
            </section>

            <div className="flex flex-wrap justify-end gap-2">
                <Button type="button" variant="outline" onClick={close}>Cancel</Button>
                <Button type="submit" disabled={saving}>
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
                </Button>
            </div>
        </form>
    );
}
