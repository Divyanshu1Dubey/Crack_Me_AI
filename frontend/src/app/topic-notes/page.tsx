'use client';

/**
 * Topic Notes — browse the published notes by exam, subject and topic (signed-in students and
 * admins). A note is read at /topic-notes/<id>. The list is filtered by the server for the viewer's
 * plan (questions/views_notes.py): free accounts see how many points are part of Premium, never
 * their answers. Admins build and publish notes at /admin/notes.
 */
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, BookOpen, Lock, Search, Settings2 } from 'lucide-react';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { notesAPI } from '@/lib/notesAPI';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { stripMarkdown } from '@/components/FormattedText';
import {
  EXAM_FILTERS,
  PROVISIONAL_MARK,
  describeNotesError,
  examLabel,
  facetTopics,
  isBuiltNote,
  lockedTeaser,
  noteListParams,
  noteSummary,
  type NoteFacets,
  type PublishedNote,
} from '@/components/notes/notesData';

const PAGE_SIZE = 12;
const CONTROL_CLS = 'w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground';

/** Rows of a list endpoint that may or may not be paginated. */
function rowsOf(body: unknown): PublishedNote[] {
  if (Array.isArray(body)) return body as PublishedNote[];
  const results = (body as { results?: unknown } | null)?.results;
  return Array.isArray(results) ? (results as PublishedNote[]) : [];
}

function hasNextPage(body: unknown): boolean {
  return Boolean((body as { next?: unknown } | null)?.next);
}

function NoteCard({ note }: { note: PublishedNote }) {
  const built = isBuiltNote(note);
  const where = [note.subject_name, note.topic_name].filter(Boolean).join(' › ');
  const summary = noteSummary(note);
  const teaser = lockedTeaser(note.locked_points);
  const preview = !built && !note.answers_locked ? stripMarkdown(note.content_preview || '') : '';
  return (
    <li>
      <Link
        href={`/topic-notes/${note.id}`}
        className="block rounded-lg border border-border bg-card p-4 text-foreground transition-colors hover:bg-accent/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex flex-wrap items-center gap-1.5">
          <h2 className="min-w-0 break-words font-semibold">{note.title}</h2>
          <Badge variant="outline">{examLabel(note.exam_type, note.is_combined)}</Badge>
          {built && <Badge variant="secondary">From PYQs</Badge>}
        </div>
        {where && <p className="mt-1 break-words text-xs text-muted-foreground">{where}</p>}
        {summary && (
          <p className="mt-1 text-xs text-muted-foreground">
            {summary}
            {note.provisional_source_count > 0 && (
              <span className="text-amber-700 dark:text-amber-400"> · {PROVISIONAL_MARK} includes provisional keys</span>
            )}
          </p>
        )}
        {note.is_stale && <p className="mt-1 text-xs text-muted-foreground">Being updated: a source question changed.</p>}
        {teaser && (
          <p className="mt-1 flex items-center gap-1 text-xs text-primary">
            <Lock className="h-3 w-3" aria-hidden="true" /> {teaser}
          </p>
        )}
        {note.answers_locked && !built && (
          <p className="mt-1 flex items-center gap-1 text-xs text-primary">
            <Lock className="h-3 w-3" aria-hidden="true" /> Part of Premium
          </p>
        )}
        {preview && <p className="mt-2 line-clamp-2 break-words text-sm text-muted-foreground">{preview}</p>}
      </Link>
    </li>
  );
}

export default function TopicNotesPage() {
  // Logged-out visitors are redirected to /login?next=/topic-notes (middleware + useRequireAuth).
  const { ready, isAdmin, user } = useRequireAuth();
  const userId = user?.id ?? null;

  const [exam, setExam] = useState('');
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [facets, setFacets] = useState<NoteFacets | null>(null);

  const [notes, setNotes] = useState<PublishedNote[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // Search titles once typing pauses.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Subjects / topics that have notes for the chosen exam.
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    notesAPI.facets(exam ? { exam_type: exam } : undefined)
      .then((res) => { if (!cancelled) setFacets(res.data); })
      .catch(() => { if (!cancelled) setFacets(null); });
    return () => { cancelled = true; };
  }, [ready, exam, userId]);

  // First page whenever a filter changes (only the latest request may write the list).
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setLoading(true);
    notesAPI.published({ ...noteListParams({ exam, subject, topic, q: search, page: 1 }), page_size: PAGE_SIZE })
      .then((res) => {
        if (cancelled) return;
        const rows = rowsOf(res.data);
        setNotes(rows);
        setCount(Number((res.data as { count?: number })?.count ?? rows.length));
        setPage(1);
        setHasMore(hasNextPage(res.data));
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setNotes([]);
        setHasMore(false);
        setError(describeNotesError(err, 'Topic notes could not be loaded.'));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ready, exam, subject, topic, search, userId, reloadKey]);

  const loadMore = async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const next = page + 1;
      const res = await notesAPI.published({ ...noteListParams({ exam, subject, topic, q: search, page: next }), page_size: PAGE_SIZE });
      const rows = rowsOf(res.data);
      setNotes((prev) => [...prev, ...rows.filter((row) => !prev.some((p) => p.id === row.id))]);
      setPage(next);
      setHasMore(hasNextPage(res.data));
    } catch (err) {
      setError(describeNotesError(err, 'More notes could not be loaded.'));
    } finally {
      setLoadingMore(false);
    }
  };

  const filtered = Boolean(exam || subject || topic || search);
  const clearFilters = () => { setExam(''); setSubject(''); setTopic(''); setQuery(''); setSearch(''); };
  const topics = facetTopics(facets, subject);
  // An exam's filter also lists the cross-exam notes, so its count includes them.
  const examCount = (value: string): number | undefined => {
    if (!facets) return undefined;
    const of = (v: string) => facets.exams.find((e) => e.value === v)?.count ?? 0;
    return value === 'all' ? of('all') : of(value) + of('all');
  };

  // The AppShell's .page-container already pads the page: no second gutter inside it.
  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 text-foreground md:p-6 [.page-container_&]:p-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="shrink-0 rounded-lg bg-emerald-100 p-2 dark:bg-emerald-900/30">
            <BookOpen className="h-6 w-6 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h1 className="text-2xl font-bold">Topic Notes</h1>
            <p className="text-sm text-muted-foreground">
              Revision notes built from previous-year questions. Every point links to the PYQs it comes from;{' '}
              {PROVISIONAL_MARK} marks a point whose answer key is not verified yet.
            </p>
          </div>
        </div>
        {isAdmin && (
          <Button asChild variant="outline" size="sm">
            <Link href="/admin/notes"><Settings2 className="h-4 w-4" aria-hidden="true" /> Notes builder</Link>
          </Button>
        )}
      </div>

      <div className="space-y-3 rounded-lg border border-border bg-card p-3 sm:p-4">
        <div role="group" aria-label="Exam" className="flex flex-wrap gap-1.5">
          {EXAM_FILTERS.map((option) => {
            const active = exam === option.value;
            const n = option.value ? examCount(option.value) : undefined;
            return (
              <button
                key={option.value || 'all-notes'}
                type="button"
                aria-pressed={active}
                onClick={() => { setExam(option.value); setSubject(''); setTopic(''); }}
                className={`rounded-full border px-3 py-1 text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-foreground hover:bg-accent'}`}
              >
                {option.label}{typeof n === 'number' ? ` · ${n}` : ''}
              </button>
            );
          })}
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block min-w-0">
            <span className="text-xs text-muted-foreground">Subject</span>
            <select
              className={`${CONTROL_CLS} mt-1`}
              value={subject}
              onChange={(e) => { setSubject(e.target.value); setTopic(''); }}
              disabled={!facets || facets.subjects.length === 0}
            >
              <option value="">All subjects</option>
              {(facets?.subjects ?? []).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.count})</option>)}
            </select>
          </label>
          <label className="block min-w-0">
            <span className="text-xs text-muted-foreground">Topic</span>
            <select
              className={`${CONTROL_CLS} mt-1`}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={!subject || topics.length === 0}
            >
              <option value="">{subject ? 'All topics' : 'Pick a subject first'}</option>
              {topics.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.count})</option>)}
            </select>
          </label>
          <label className="block min-w-0">
            <span className="text-xs text-muted-foreground">Search titles</span>
            <span className="relative mt-1 block">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. antidotes"
                className={`${CONTROL_CLS} pl-8`}
              />
            </span>
          </label>
        </div>
      </div>

      {error && (
        <div role="alert" className="flex flex-col gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm sm:flex-row sm:items-center">
          <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
          <p className="flex-1 text-foreground">{error}</p>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>Try again</Button>
        </div>
      )}

      {!ready || loading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading notes">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : notes.length === 0 ? (
        !error && (
          <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
            <BookOpen className="mx-auto mb-3 h-10 w-10 opacity-30" aria-hidden="true" />
            <p>
              {filtered
                ? 'No published notes match these filters yet.'
                : 'No topic notes have been published yet. They are built from previous-year questions and reviewed by the CrackLabs team.'}
            </p>
            {filtered && (
              <Button variant="outline" size="sm" className="mt-4" onClick={clearFilters}>Clear filters</Button>
            )}
          </div>
        )
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {count} note{count === 1 ? '' : 's'}
          </p>
          <ul className="space-y-3">
            {notes.map((note) => <NoteCard key={note.id} note={note} />)}
          </ul>
          {hasMore && (
            <div className="text-center">
              <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? 'Loading…' : 'Load more notes'}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
