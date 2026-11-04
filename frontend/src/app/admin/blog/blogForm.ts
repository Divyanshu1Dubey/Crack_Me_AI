/**
 * Pure helpers for /admin/blog: the editor's form state, its conversion to
 * and from the blog API record (backend/blog_engine BlogPostSerializer), and
 * client-side checks that mirror the API's validation.
 *
 * No React (unit-tested with node --test in tests/unit/blog-admin-form.test.ts).
 * It must never import src/lib/blog.ts: that module bundles every static post.
 *
 * Word count and reading time are not edited: the API computes both from the
 * body (blog_engine.text_stats; lib/blogText is the same rule for the live
 * count). The table of contents is not edited either: on save it is rebuilt
 * from the `##` headings (lib/blogMarkdown blogToc), keeping the anchor ids
 * the post already had.
 */
import type { BlogPostAdmin } from '@/lib/blogAPI';
import { blogToc } from '@/lib/blogMarkdown';
import { countBlogWords, readingTimeLabel } from '@/lib/blogText';

export type Difficulty = 'beginner' | 'intermediate' | 'advanced';

export interface FaqRow { q: string; a: string }
export interface TocRow { id: string; label: string }
export interface ReferenceRow { label: string; url: string; published: string }
export interface RevisionRow { date: string; note: string }

/** Everything the editor edits, as the inputs hold it. */
export interface BlogFormState {
    slug: string;
    title: string;
    description: string;
    excerpt: string;
    coverImage: string;
    category: string;
    subcategory: string;
    /** Comma-separated. */
    tags: string;
    difficulty: Difficulty;
    authorId: string;
    reviewedBy: string;
    author: string;
    authorRole: string;
    datePublished: string;
    dateModified: string;
    updatedAt: string;
    ctaLabel: string;
    ctaHref: string;
    ctaEventName: string;
    /** JSON object text, '' when none. */
    ctaEventParams: string;
    /** One path per line. */
    relatedExamPaths: string;
    faqs: FaqRow[];
    /** The stored table of contents: only its anchor ids matter (kept for headings it names). */
    toc: TocRow[];
    references: ReferenceRow[];
    revisionLog: RevisionRow[];
    body: string;
    prelude: string;
    outro: string;
    pinned: boolean;
    trending: boolean;
    isPublished: boolean;
}

/** The field the API reports an error under, for each form field. */
export const FIELD_FOR_INPUT: Record<string, string> = {
    slug: 'slug', title: 'title', description: 'description', excerpt: 'excerpt', coverImage: 'cover_image',
    category: 'category', subcategory: 'subcategory', tags: 'tags', difficulty: 'difficulty',
    authorId: 'author_id', reviewedBy: 'reviewed_by', author: 'author', authorRole: 'author_role',
    datePublished: 'date_published', dateModified: 'date_modified', updatedAt: 'updated_at',
    cta: 'primary_cta', relatedExamPaths: 'related_exam_paths',
    faqs: 'faqs', toc: 'toc', references: 'references', revisionLog: 'revision_log', body: 'body',
    prelude: 'prelude', outro: 'outro', isPublished: 'is_published',
};

/** Human labels for API field names (error summaries). */
export const FIELD_LABELS: Record<string, string> = {
    slug: 'Slug', title: 'Title', description: 'SEO description', excerpt: 'Excerpt', cover_image: 'Cover image',
    category: 'Category', subcategory: 'Subcategory', tags: 'Tags', difficulty: 'Difficulty', author_id: 'Author profile',
    reviewed_by: 'Reviewer', author: 'Author name', author_role: 'Author role', date_published: 'Published on',
    date_modified: 'Modified on', updated_at: 'Updated on', reading_time: 'Reading time', word_count: 'Word count',
    primary_cta: 'Call to action', related_exam_paths: 'Related pages', faqs: 'FAQs', toc: 'Table of contents',
    references: 'References', revision_log: 'Revision log', body: 'Body', prelude: 'Prelude', outro: 'Outro',
    is_published: 'Published', non_field_errors: 'Post', detail: 'Post', file: 'Image',
};

// Kept in step with backend/blog_engine/serializers.py.
export const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const RESERVED_SLUGS: ReadonlySet<string> = new Set(['category', 'tag', 'author', 'feed', 'feed-xml', 'og', 'page', 'opengraph-image']);
const ANCHOR_PATTERN = /^[a-z0-9][a-z0-9_-]*$/;
const EVENT_NAME_PATTERN = /^[a-z][a-z0-9_]{0,63}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
/** Stub body of the old seed: such a post is never shown publicly. */
export const PLACEHOLDER_BODY = 'full article content here.';

export function isStubBody(body: string): boolean {
    const text = body.trim().toLowerCase();
    return text === '' || text === PLACEHOLDER_BODY;
}

/** Today's local date as YYYY-MM-DD. */
export function todayIso(now: Date = new Date()): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function isIsoDate(value: string): boolean {
    if (!ISO_DATE.test(value)) return false;
    const d = new Date(`${value}T00:00:00Z`);
    return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === value;
}

/** A URL slug from a title: lowercase ASCII words joined by single hyphens. */
export function slugify(text: string): string {
    return text
        .normalize('NFKD')
        .replace(/[̀-ͯ]/g, '')
        .toLowerCase()
        .replace(/&/g, ' and ')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 120)
        .replace(/-+$/g, '');
}

/** Word count of a markdown body: the API's rule (lib/blogText countBlogWords). */
export function wordCountOf(markdown: string): number {
    return countBlogWords(markdown);
}

/** "N min" at 200 words a minute (at least 1 min): what the post page will show. */
export function estimateReadingTime(markdown: string): string {
    return readingTimeLabel(countBlogWords(markdown));
}

/**
 * The `##` headings of a body as TOC rows, with the ids the post page gives
 * them (`keep`: the stored TOC, whose ids its headings keep).
 */
export function tocFromBody(markdown: string, keep: TocRow[] = []): TocRow[] {
    return blogToc(markdown, keep);
}

/** An internal path (not protocol-relative) or an http(s) URL. */
export function isSafeLink(value: string): boolean {
    if (value.startsWith('/')) return !value.startsWith('//') && !/\s/.test(value);
    return /^https?:\/\/[^\s/]+\S*$/i.test(value);
}

export interface AuthorOption { slug: string; name: string; role: string }

/** A blank post: the editorial byline, today's dates, a draft. */
export function emptyBlogForm(today: string, profile?: AuthorOption): BlogFormState {
    return {
        slug: '', title: '', description: '', excerpt: '', coverImage: '',
        category: '', subcategory: '', tags: '', difficulty: 'intermediate',
        authorId: profile?.slug ?? 'crackcms-editorial', reviewedBy: profile?.slug ?? 'crackcms-editorial',
        author: profile?.name ?? '', authorRole: profile?.role ?? '',
        datePublished: today, dateModified: today, updatedAt: today,
        ctaLabel: 'Practise UPSC CMS PYQs', ctaHref: '/questions?exam=cms', ctaEventName: 'blog_practice_intent', ctaEventParams: '',
        relatedExamPaths: '', faqs: [], toc: [], references: [], revisionLog: [],
        body: '', prelude: '', outro: '', pinned: false, trending: false, isPublished: false,
    };
}

function str(value: unknown): string {
    return typeof value === 'string' ? value : '';
}

function list<T>(value: unknown, map: (item: Record<string, unknown>) => T): T[] {
    return Array.isArray(value)
        ? value.filter((v): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)).map(map)
        : [];
}

/** The form for a post loaded from the API. */
export function formFromPost(post: Partial<BlogPostAdmin>): BlogFormState {
    const cta = (post.primary_cta && typeof post.primary_cta === 'object' ? post.primary_cta : {}) as Record<string, unknown>;
    const params = cta.event_params ?? cta.eventParams;
    const difficulty = str(post.difficulty);
    return {
        slug: str(post.slug), title: str(post.title), description: str(post.description), excerpt: str(post.excerpt),
        coverImage: str(post.cover_image), category: str(post.category), subcategory: str(post.subcategory),
        tags: Array.isArray(post.tags) ? post.tags.filter((t) => typeof t === 'string').join(', ') : '',
        difficulty: difficulty === 'beginner' || difficulty === 'advanced' ? difficulty : 'intermediate',
        authorId: str(post.author_id), reviewedBy: str(post.reviewed_by), author: str(post.author), authorRole: str(post.author_role),
        datePublished: str(post.date_published), dateModified: str(post.date_modified), updatedAt: str(post.updated_at),
        ctaLabel: str(cta.label), ctaHref: str(cta.href), ctaEventName: str(cta.event_name ?? cta.eventName),
        ctaEventParams: params && typeof params === 'object' && !Array.isArray(params) && Object.keys(params).length
            ? JSON.stringify(params, null, 2) : '',
        relatedExamPaths: Array.isArray(post.related_exam_paths) ? post.related_exam_paths.join('\n') : '',
        faqs: list(post.faqs, (f) => ({ q: str(f.q), a: str(f.a) })),
        toc: list(post.toc, (t) => ({ id: str(t.id), label: str(t.label) })),
        references: list(post.references, (r) => ({ label: str(r.label), url: str(r.url), published: str(r.published) })),
        revisionLog: list(post.revision_log, (e) => ({ date: str(e.date), note: str(e.note) })),
        body: str(post.body), prelude: str(post.prelude), outro: str(post.outro),
        pinned: post.pinned === true, trending: post.trending === true, isPublished: post.is_published === true,
    };
}

/** Rows whose every field is blank are dropped; the rest are trimmed. */
function filledRows<T extends object>(rows: T[]): T[] {
    return rows
        .map((row) => Object.fromEntries(Object.entries(row).map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v])) as T)
        .filter((row) => Object.values(row).some((v) => typeof v === 'string' && v !== ''));
}

export type FormErrors = Partial<Record<string, string>>;

/**
 * The API payload for a form, and the problems the API would refuse (keyed
 * by form field). The payload is only sent when there are none.
 */
export function formToPayload(form: BlogFormState): { payload: Partial<BlogPostAdmin>; errors: FormErrors } {
    const errors: FormErrors = {};
    const slug = form.slug.trim();
    if (!SLUG_PATTERN.test(slug)) errors.slug = 'Use lowercase letters, numbers and single hyphens, e.g. upsc-cms-revision-plan.';
    else if (RESERVED_SLUGS.has(slug)) errors.slug = `/blog/${slug} is another page; choose another slug.`;
    if (!form.title.trim()) errors.title = 'Give the post a title.';
    for (const [key, label] of [['description', 'an SEO description'], ['excerpt', 'an excerpt'], ['category', 'a category'],
        ['author', 'the author name'], ['authorRole', 'the author role']] as const) {
        if (!form[key].trim()) errors[key] = `Add ${label}.`;
    }
    if (!SLUG_PATTERN.test(form.authorId.trim())) errors.authorId = 'Choose an author profile.';
    if (form.reviewedBy.trim() && !SLUG_PATTERN.test(form.reviewedBy.trim())) errors.reviewedBy = 'Choose a reviewer profile, or none.';
    if (!isIsoDate(form.datePublished.trim())) errors.datePublished = 'Pick the publication date.';
    for (const key of ['dateModified', 'updatedAt'] as const) {
        const value = form[key].trim();
        if (value && !isIsoDate(value)) errors[key] = 'Pick a date, or leave it empty.';
    }
    const cover = form.coverImage.trim();
    if (cover && !isSafeLink(cover)) errors.coverImage = 'Use a path such as /blog/cover.png or an https:// URL.';

    const tags: string[] = [];
    const seenTags = new Set<string>();
    for (const raw of form.tags.split(',')) {
        const tag = raw.trim();
        if (!tag || seenTags.has(tag.toLowerCase())) continue;
        seenTags.add(tag.toLowerCase());
        tags.push(tag);
    }

    const ctaLabel = form.ctaLabel.trim();
    const ctaHref = form.ctaHref.trim();
    const ctaEvent = form.ctaEventName.trim();
    let primaryCta: Record<string, unknown> = {};
    if (ctaLabel || ctaHref) {
        if (!ctaLabel || !ctaHref) errors.cta = 'Give both a button label and a link (or neither).';
        else if (!isSafeLink(ctaHref)) errors.cta = 'The link must be a site path such as /questions or an https:// URL.';
        else primaryCta = { label: ctaLabel, href: ctaHref };
        if (ctaEvent) {
            if (!EVENT_NAME_PATTERN.test(ctaEvent)) errors.cta = 'The event name uses lowercase letters, digits and _.';
            else primaryCta.event_name = ctaEvent;
        }
        if (form.ctaEventParams.trim()) {
            try {
                const params = JSON.parse(form.ctaEventParams);
                const ok = params && typeof params === 'object' && !Array.isArray(params)
                    && Object.values(params).every((v) => ['string', 'number', 'boolean'].includes(typeof v));
                if (!ok) errors.cta = 'Event parameters must be a JSON object of text, numbers or true/false.';
                else primaryCta.event_params = params;
            } catch {
                errors.cta = 'Event parameters are not valid JSON.';
            }
        }
    }

    const relatedExamPaths = form.relatedExamPaths.split(/\r?\n/).map((p) => p.trim()).filter(Boolean);
    if (relatedExamPaths.some((p) => !p.startsWith('/') || !isSafeLink(p))) {
        errors.relatedExamPaths = 'One site path per line, each starting with / (e.g. /cms).';
    }

    const faqs = filledRows(form.faqs);
    if (faqs.some((f) => !f.q || !f.a)) errors.faqs = 'Every FAQ needs a question and an answer.';
    // Built from the ## headings; stored ids are kept for the headings they name.
    const body = form.body.trim();
    const toc = tocFromBody(body, filledRows(form.toc).filter((t) => t.label && ANCHOR_PATTERN.test(t.id)));
    const references = filledRows(form.references);
    if (references.some((r) => !r.label)) errors.references = 'Every reference needs a label.';
    else if (references.some((r) => r.url && !/^https?:\/\/\S+$/i.test(r.url))) errors.references = 'Reference links start with https:// or http://.';
    const revisionLog = filledRows(form.revisionLog);
    if (revisionLog.some((e) => !isIsoDate(e.date) || !e.note)) errors.revisionLog = 'Every entry needs a date and a note.';

    if (form.isPublished && isStubBody(form.body)) errors.isPublished = 'Add the article body before publishing this post.';

    const payload: Partial<BlogPostAdmin> = {
        slug,
        title: form.title.trim(),
        description: form.description.trim(),
        excerpt: form.excerpt.trim(),
        cover_image: cover,
        category: form.category.trim(),
        subcategory: form.subcategory.trim(),
        tags,
        difficulty: form.difficulty,
        author_id: form.authorId.trim(),
        reviewed_by: form.reviewedBy.trim(),
        author: form.author.trim(),
        author_role: form.authorRole.trim(),
        date_published: form.datePublished.trim(),
        date_modified: form.dateModified.trim(),
        updated_at: form.updatedAt.trim(),
        primary_cta: primaryCta,
        related_exam_paths: relatedExamPaths,
        faqs,
        toc,
        references: references.map((r) => ({ label: r.label, ...(r.url ? { url: r.url } : {}), ...(r.published ? { published: r.published } : {}) })),
        revision_log: revisionLog,
        body,
        prelude: form.prelude.trim(),
        outro: form.outro.trim(),
        pinned: form.pinned,
        trending: form.trending,
        is_published: form.isPublished,
    };
    return { payload, errors };
}

/** Field errors of a failed API save, keyed by API field ('detail' for the rest). */
export function apiFieldErrors(error: unknown): Record<string, string> {
    const response = (error as { response?: { status?: number; data?: unknown } } | null | undefined)?.response;
    const data = response?.data;
    if (!data || typeof data !== 'object' || Array.isArray(data)) return {};
    const out: Record<string, string> = {};
    for (const [field, value] of Object.entries(data as Record<string, unknown>)) {
        const text = Array.isArray(value)
            ? value.map((v) => (typeof v === 'string' ? v : JSON.stringify(v))).join(' ')
            : typeof value === 'string' ? value : JSON.stringify(value);
        if (text) out[field] = text;
    }
    return out;
}

/** One sentence for a failed request (status, field errors, or the network). */
export function describeBlogError(error: unknown, what = 'the request'): string {
    const status = Number((error as { response?: { status?: unknown } } | null | undefined)?.response?.status);
    if (status === 401 || status === 403) return 'Admin access is needed for this.';
    if (status === 404) return 'That post no longer exists. Refresh the list.';
    if (status === 429) return 'Too many requests. Try again in a minute.';
    const fields = apiFieldErrors(error);
    const parts = Object.entries(fields).map(([field, text]) =>
        field === 'detail' || field === 'non_field_errors' ? text : `${FIELD_LABELS[field] ?? field}: ${text}`);
    if (status >= 400 && status < 500 && parts.length) return parts.join(' · ').slice(0, 500);
    if (status >= 500) return `The server could not complete ${what}. Try again.`;
    if (!Number.isFinite(status) || status <= 0) return `Could not reach the server for ${what}. Check your connection and retry.`;
    return `Could not complete ${what}.`;
}

/** True when two forms differ (unsaved changes). */
export function formsDiffer(a: BlogFormState, b: BlogFormState): boolean {
    return JSON.stringify(a) !== JSON.stringify(b);
}

/** Admin list params for the filters (page size, status, thin posts, category, search, ordering). */
export function blogListParams(filters: {
    page: number; pageSize: number; search: string; status: '' | 'published' | 'draft'; category: string; ordering: string;
    thin?: boolean;
}) {
    const params: Record<string, string | number> = { page: filters.page, page_size: filters.pageSize };
    if (filters.search.trim()) params.search = filters.search.trim();
    if (filters.status) params.is_published = filters.status === 'published' ? 'true' : 'false';
    if (filters.thin) params.thin = 'true';
    if (filters.category) params.category = filters.category;
    if (filters.ordering) params.ordering = filters.ordering;
    return params;
}

/** ?edit=<slug> / ?new=1 on /admin/blog (the "Edit post" button of a published post links here). */
export function editorTargetFromSearch(search: string): { slug: string } | { create: true } | null {
    const params = new URLSearchParams(search);
    const slug = (params.get('edit') ?? '').trim();
    if (SLUG_PATTERN.test(slug)) return { slug };
    if (params.get('new') === '1') return { create: true };
    return null;
}
