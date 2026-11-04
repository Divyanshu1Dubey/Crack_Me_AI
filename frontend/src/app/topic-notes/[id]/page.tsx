'use client';

/**
 * Read one published topic note (/topic-notes/<id>). The server filters the note for the viewer's
 * plan: points whose PYQs are not all free questions are counted (locked_points), never sent, and
 * points whose source question changed since the build are hidden. Every point lists its source
 * PYQs with a link to practise each one, and is marked provisional when its answer key is not
 * verified (components/notes/TopicNoteView.tsx).
 */
import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, BookOpen } from 'lucide-react';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { usePaywall } from '@/lib/paywall/paywallContext';
import { loadPublishedNote } from '@/lib/notesAPI';
import TopicNoteView from '@/components/notes/TopicNoteView';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { describeNotesError, examLabel, isBuiltNote, noteSummary, type PublishedNote } from '@/components/notes/notesData';

type LoadState = 'loading' | 'ready' | 'missing' | 'error';

export default function TopicNoteReaderPage() {
  const { ready, isAdmin, user } = useRequireAuth();
  const { show: showPaywall } = usePaywall();
  const params = useParams();
  const rawId = Array.isArray(params?.id) ? params.id[0] : params?.id;
  const id = Number(rawId);
  const validId = Number.isInteger(id) && id > 0;
  const userId = user?.id ?? null;

  const [note, setNote] = useState<PublishedNote | null>(null);
  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!ready || !validId) return;
    let cancelled = false;
    setState('loading');
    loadPublishedNote(id)
      .then(({ note: loaded }) => {
        if (cancelled) return;
        setNote(loaded);
        setState(loaded ? 'ready' : 'missing');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(describeNotesError(err, 'The note could not be loaded.'));
        setState('error');
      });
    return () => { cancelled = true; };
  }, [ready, id, validId, userId, reloadKey]);

  const back = (
    <Link href="/topic-notes" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
      <ArrowLeft className="h-4 w-4" aria-hidden="true" /> All topic notes
    </Link>
  );

  let body: ReactNode;
  if (!validId || state === 'missing') {
    body = (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
        <BookOpen className="mx-auto mb-3 h-10 w-10 opacity-30" aria-hidden="true" />
        <p>This note is not published (or no longer exists).</p>
      </div>
    );
  } else if (!ready || state === 'loading') {
    body = (
      <div className="space-y-3" aria-busy="true" aria-label="Loading the note">
        <Skeleton className="h-8 w-2/3" />
        {[1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}
      </div>
    );
  } else if (state === 'error' || !note) {
    body = (
      <div role="alert" className="flex flex-col gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm sm:flex-row sm:items-center">
        <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
        <p className="flex-1 text-foreground">{error || 'The note could not be loaded.'}</p>
        <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>Try again</Button>
      </div>
    );
  } else {
    const where = [note.subject_name, note.topic_name].filter(Boolean).join(' › ');
    const summary = noteSummary(note);
    const built = note.built_at ? new Date(note.built_at) : null;
    body = (
      <article aria-labelledby="note-title" className="space-y-4">
        <header className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline">{examLabel(note.exam_type, note.is_combined)}</Badge>
            {isBuiltNote(note) && <Badge variant="secondary">Built from PYQs</Badge>}
            {!note.is_published && isAdmin && <Badge variant="warning">Draft (admin preview)</Badge>}
          </div>
          <h1 id="note-title" className="break-words text-2xl font-bold text-foreground">{note.title}</h1>
          {where && <p className="break-words text-sm text-muted-foreground">{where}</p>}
          {(summary || built) && (
            <p className="text-xs text-muted-foreground">
              {summary}
              {summary && built ? ' · ' : ''}
              {built && !Number.isNaN(built.getTime()) ? `Built ${built.toLocaleDateString()}` : ''}
            </p>
          )}
        </header>
        <TopicNoteView note={note} onUpgrade={() => showPaywall('PYQ answers')} />
      </article>
    );
  }

  // The AppShell's .page-container already pads the page.
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 text-foreground md:p-6 [.page-container_&]:p-0">
      {back}
      {body}
    </div>
  );
}
