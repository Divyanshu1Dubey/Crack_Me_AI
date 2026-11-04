'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ExternalLink, Loader2, Newspaper, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { blogAPI, type BlogFacets, type BlogPostAdmin, type BlogPostAdminRow } from '@/lib/blogAPI';
import BlogEditor from './BlogEditor';
import { blogListParams, describeBlogError } from './blogForm';

const PAGE_SIZE = 25;
const STATUSES: { value: '' | 'published' | 'draft'; label: string }[] = [
    { value: '', label: 'All' },
    { value: 'published', label: 'Published' },
    { value: 'draft', label: 'Drafts' },
];
const ORDERINGS = [
    { value: '', label: 'Newest first' },
    { value: '-updated', label: 'Recently edited' },
    { value: 'title', label: 'Title A–Z' },
    { value: 'date_published', label: 'Oldest first' },
];

export default function AdminBlogPage() {
    const router = useRouter();
    const { user, loading: authLoading, isAuthenticated } = useAuth();
    const isAdmin = !!user && (user.role === 'admin' || !!user.is_admin);

    const [rows, setRows] = useState<BlogPostAdminRow[]>([]);
    const [count, setCount] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [facets, setFacets] = useState<BlogFacets | null>(null);

    const [searchInput, setSearchInput] = useState('');
    const [search, setSearch] = useState('');
    const [status, setStatus] = useState<'' | 'published' | 'draft'>('');
    const [category, setCategory] = useState('');
    const [ordering, setOrdering] = useState('');

    const [editor, setEditor] = useState<{ id: number | null } | null>(null);
    const [confirmDelete, setConfirmDelete] = useState<BlogPostAdminRow | null>(null);
    const [busyId, setBusyId] = useState<number | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const requestSeq = useRef(0);

    const loadList = useCallback(async () => {
        const seq = ++requestSeq.current;
        setLoading(true);
        setError(null);
        try {
            const res = await blogAPI.list(blogListParams({ page, pageSize: PAGE_SIZE, search, status, category, ordering }));
            if (seq !== requestSeq.current) return;
            const data = res.data as { results?: BlogPostAdminRow[]; count?: number } | BlogPostAdminRow[];
            const results = Array.isArray(data) ? data : data?.results ?? [];
            setRows(results);
            setCount(Array.isArray(data) ? data.length : Number(data?.count ?? results.length));
        } catch (err) {
            if (seq !== requestSeq.current) return;
            setError(describeBlogError(err, 'loading the posts'));
            setRows([]);
            setCount(0);
        } finally {
            if (seq === requestSeq.current) setLoading(false);
        }
    }, [page, search, status, category, ordering]);

    const loadFacets = useCallback(async () => {
        try {
            const res = await blogAPI.facets();
            setFacets(res.data);
        } catch {
            /* the list shows the error */
        }
    }, []);

    useEffect(() => { if (isAdmin && !editor) loadList(); }, [isAdmin, editor, loadList]);
    useEffect(() => { if (isAdmin) loadFacets(); }, [isAdmin, loadFacets]);
    useEffect(() => {
        const t = window.setTimeout(() => setSearch(searchInput.trim()), 350);
        return () => window.clearTimeout(t);
    }, [searchInput]);
    useEffect(() => { setPage(1); }, [search, status, category, ordering]);

    const openEditor = (id: number | null) => {
        setNotice(null);
        setConfirmDelete(null);
        setEditor({ id });
        window.scrollTo({ top: 0 });
    };

    const closeEditor = () => {
        setEditor(null);
        loadFacets();
    };

    const onSaved = (post: BlogPostAdmin, created: boolean) => {
        setNotice(post.is_published
            ? `Saved “${post.title}”. The public page updates within about 10 minutes.`
            : `Saved “${post.title}” as a draft (not on the site).`);
        if (created) setEditor({ id: post.id });
        loadFacets();
    };

    async function togglePublish(row: BlogPostAdminRow) {
        setBusyId(row.id);
        setNotice(null);
        try {
            const res = await blogAPI.togglePublish(row.id);
            setRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, is_published: res.data.is_published } : r)));
            setNotice(res.data.is_published
                ? `Published “${row.title}”. It appears on the blog within about 10 minutes.`
                : `Unpublished “${row.title}”. It leaves the blog within about 10 minutes.`);
            loadFacets();
        } catch (err) {
            setNotice(describeBlogError(err, 'changing the publish state'));
        } finally {
            setBusyId(null);
        }
    }

    async function deletePost(row: BlogPostAdminRow) {
        setBusyId(row.id);
        try {
            await blogAPI.remove(row.id);
            setConfirmDelete(null);
            setNotice(`Deleted “${row.title}”. It leaves the blog within about 10 minutes.`);
            loadList();
            loadFacets();
        } catch (err) {
            setNotice(describeBlogError(err, 'deleting the post'));
        } finally {
            setBusyId(null);
        }
    }

    if (authLoading) {
        return <p className="p-6 [.page-container_&]:px-0 text-muted-foreground">Checking access…</p>;
    }
    if (!isAuthenticated || !isAdmin) {
        return (
            <div className="mx-auto max-w-5xl px-4 py-12 [.page-container_&]:px-0 text-center text-foreground">
                <p className="mb-3 text-muted-foreground">You need admin access to view this page.</p>
                <Button onClick={() => router.push('/login?next=' + encodeURIComponent('/admin/blog'))}>Sign in</Button>
            </div>
        );
    }

    const noticeBox = notice && (
        <p className="mb-3 rounded-md border border-border bg-muted px-3 py-2 text-sm text-foreground" role="status">{notice}</p>
    );

    if (editor) {
        return (
            <div className="mx-auto max-w-7xl px-4 py-6 [.page-container_&]:p-0 text-foreground">
                {noticeBox}
                <BlogEditor key={editor.id ?? 'new'} postId={editor.id} onSaved={onSaved} onClose={closeEditor}
                    categories={facets?.categories.map((c) => c.name) ?? []} />
            </div>
        );
    }

    const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));
    const statusCount = (value: '' | 'published' | 'draft') =>
        facets ? (value === '' ? facets.total : value === 'published' ? facets.published : facets.drafts) : null;

    return (
        <div className="mx-auto max-w-7xl px-4 py-6 [.page-container_&]:p-0 text-foreground">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                    <Newspaper className="h-5 w-5 text-primary" />
                    <h1 className="text-xl font-semibold">Blog posts</h1>
                    {facets && <span className="text-xs text-muted-foreground">{facets.total} posts · {facets.published} published · {facets.drafts} drafts</span>}
                </div>
                <div className="flex flex-wrap gap-2">
                    <a href="/blog" target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm text-foreground hover:bg-accent">
                        <ExternalLink className="h-4 w-4" /> View blog
                    </a>
                    <Button variant="outline" size="sm" onClick={() => { loadList(); loadFacets(); }} aria-label="Refresh">
                        <RefreshCw className="h-4 w-4" /> Refresh
                    </Button>
                    <Button size="sm" onClick={() => openEditor(null)}>
                        <Plus className="h-4 w-4" /> New post
                    </Button>
                </div>
            </div>
            <p className="mb-4 text-xs text-muted-foreground">
                The public blog (/blog, its category, tag and author pages, the feed and the sitemap) shows exactly the published
                posts listed here. Saved changes appear on the site within about 10 minutes. Deploys import new posts from the
                site&apos;s post files but never overwrite or bring back a post edited or deleted here.
            </p>

            {noticeBox}

            <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label="Status">
                {STATUSES.map((s) => {
                    const n = statusCount(s.value);
                    const active = status === s.value;
                    return (
                        <button key={s.value || 'all'} type="button" role="tab" aria-selected={active} onClick={() => setStatus(s.value)}
                            className={`rounded-full border px-3 py-1 text-xs ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-accent'}`}>
                            {s.label}{n !== null && <span className="opacity-75"> {n}</span>}
                        </button>
                    );
                })}
            </div>

            <div className="mb-4 flex flex-wrap items-end gap-2 text-sm">
                <label className="flex min-w-0 flex-1 basis-56 flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Search title, slug, text, tags</span>
                    <input type="search" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="e.g. renal"
                        className="w-full rounded-md border border-border bg-background px-2 py-1.5" />
                </label>
                <label className="flex min-w-0 max-w-full flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Category</span>
                    <select value={category} onChange={(e) => setCategory(e.target.value)}
                        className="max-w-full rounded-md border border-border bg-background px-2 py-1.5">
                        <option value="">All categories</option>
                        {facets?.categories.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.count})</option>)}
                    </select>
                </label>
                <label className="flex min-w-0 max-w-full flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Sort</span>
                    <select value={ordering} onChange={(e) => setOrdering(e.target.value)}
                        className="max-w-full rounded-md border border-border bg-background px-2 py-1.5">
                        {ORDERINGS.map((o) => <option key={o.value || 'default'} value={o.value}>{o.label}</option>)}
                    </select>
                </label>
            </div>

            {error && <p className="mb-3 text-sm text-destructive" role="alert">{error}</p>}
            {loading && <p className="mb-2 flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</p>}
            {!loading && !error && rows.length === 0 && (
                <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                    No posts in this view. <button type="button" className="text-primary hover:underline" onClick={() => openEditor(null)}>Write one</button>
                </p>
            )}

            <ul className="space-y-2" aria-label="Posts">
                {rows.map((row) => (
                    <li key={row.id} className="min-w-0 rounded-lg border border-border bg-card p-3">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-1.5">
                                    <Badge variant={row.is_published ? 'success' : 'secondary'}>{row.is_published ? 'Published' : 'Draft'}</Badge>
                                    {row.is_stub && <Badge variant="warning" title="The body is empty or a placeholder: not shown on the site">No body</Badge>}
                                    {row.pinned && <Badge variant="outline">Pinned</Badge>}
                                    {row.trending && <Badge variant="outline">Trending</Badge>}
                                    <span className="text-xs text-muted-foreground">{row.category}{row.subcategory ? ` · ${row.subcategory}` : ''}</span>
                                </div>
                                <button type="button" onClick={() => openEditor(row.id)}
                                    className="mt-1 block text-left font-medium text-foreground hover:text-primary hover:underline">
                                    {row.title}
                                </button>
                                <p className="break-all font-mono text-xs text-muted-foreground">/blog/{row.slug}</p>
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                    Published {row.date_published || '–'}{row.updated_at ? ` · updated ${row.updated_at}` : ''} · {row.reading_time}
                                    {row.updated ? ` · last saved ${new Date(row.updated).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}` : ''}
                                </p>
                            </div>
                            <div className="flex shrink-0 flex-wrap gap-1.5">
                                <Button variant="outline" size="sm" onClick={() => openEditor(row.id)}>
                                    <Pencil className="h-4 w-4" /> Edit
                                </Button>
                                <Button variant="outline" size="sm" disabled={busyId === row.id || (!row.is_published && row.is_stub)}
                                    title={!row.is_published && row.is_stub ? 'Add the article body first' : undefined}
                                    onClick={() => togglePublish(row)}>
                                    {row.is_published ? 'Unpublish' : 'Publish'}
                                </Button>
                                {row.is_published && !row.is_stub && (
                                    <a href={`/blog/${row.slug}`} target="_blank" rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm text-foreground hover:bg-accent">
                                        <ExternalLink className="h-4 w-4" /> View
                                    </a>
                                )}
                                <Button variant="outline" size="sm" className="text-destructive" disabled={busyId === row.id}
                                    onClick={() => setConfirmDelete(row)} aria-label={`Delete ${row.title}`}>
                                    <Trash2 className="h-4 w-4" /> Delete
                                </Button>
                            </div>
                        </div>
                        {confirmDelete?.id === row.id && (
                            <div className="mt-3 rounded-md border border-destructive/50 bg-destructive/10 p-3" role="alertdialog"
                                aria-labelledby={`delete-${row.id}`}>
                                <p id={`delete-${row.id}`} className="text-sm font-medium text-foreground">
                                    Delete “{row.title}” permanently?
                                </p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    It disappears from the blog within about 10 minutes and cannot be undone here. A post imported from the
                                    site&apos;s files is not brought back by later deploys. To hide it instead, unpublish it.
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                    <Button variant="destructive" size="sm" disabled={busyId === row.id} onClick={() => deletePost(row)}>
                                        {busyId === row.id && <Loader2 className="h-4 w-4 animate-spin" />} Delete permanently
                                    </Button>
                                    <Button variant="outline" size="sm" onClick={() => setConfirmDelete(null)}>Keep it</Button>
                                </div>
                            </div>
                        )}
                    </li>
                ))}
            </ul>

            {pages > 1 && (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                    <Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                    <span className="text-muted-foreground">Page {page} of {pages} · {count} post(s)</span>
                    <Button variant="outline" size="sm" disabled={page >= pages || loading} onClick={() => setPage((p) => p + 1)}>Next</Button>
                </div>
            )}
        </div>
    );
}
