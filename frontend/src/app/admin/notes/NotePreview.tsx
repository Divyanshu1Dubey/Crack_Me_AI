'use client';

/**
 * Admin preview of one note: "Note" renders it as a premium student reads it (the published detail
 * route, which serves admins unpublished drafts too), "Sources" lists every PYQ a built note cites
 * or left out, with its key status, reason and whether it changed since the build
 * (GET /api/questions/topic-notes/library/<id>/sources/).
 */
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { FormattedText } from '@/components/FormattedText';
import TopicNoteView from '@/components/notes/TopicNoteView';
import { notesAPI } from '@/lib/notesAPI';
import {
  describeNotesError,
  keyStatusTone,
  practiceHref,
  reasonLabel,
  type LibraryNote,
  type NoteSourceRow,
  type PublishedNote,
} from '@/components/notes/notesData';

type Tab = 'note' | 'sources';
type CitedFilter = '' | 'true' | 'false';

interface SourcesBody {
  is_stale: boolean;
  counts: { cited: number; not_cited: number; changed_since_build: number };
  excluded_reasons: Record<string, number>;
  results: NoteSourceRow[];
}

function NoteTab({ note, builderEnabled }: { note: LibraryNote; builderEnabled: boolean }) {
  const [detail, setDetail] = useState<PublishedNote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(builderEnabled);

  useEffect(() => {
    if (!builderEnabled) return;
    let cancelled = false;
    setLoading(true);
    notesAPI.publishedDetail(note.id)
      .then((res) => { if (!cancelled) { setDetail(res.data); setError(null); } })
      .catch((err) => { if (!cancelled) setError(describeNotesError(err, 'The preview could not be loaded.')); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [note.id, note.updated_at, builderEnabled]);

  if (!builderEnabled) {
    return note.content?.trim()
      ? <div className="break-words text-sm"><FormattedText text={note.content} /></div>
      : <p className="text-sm text-muted-foreground">This note has no content yet.</p>;
  }
  if (loading) return <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading the preview…</p>;
  if (error || !detail) return <p role="alert" className="text-sm text-destructive">{error || 'No preview.'}</p>;
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">As a Premium student reads it{note.is_published ? '' : ' once published'}. Free accounts see only the points whose PYQs are all free questions.</p>
      <TopicNoteView note={detail} />
    </div>
  );
}

function SourcesTab({ note, builderEnabled }: { note: LibraryNote; builderEnabled: boolean }) {
  const [cited, setCited] = useState<CitedFilter>('');
  const [body, setBody] = useState<SourcesBody | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!builderEnabled) return;
    let cancelled = false;
    setLoading(true);
    notesAPI.sources(note.id, cited ? { cited } : undefined)
      .then((res) => { if (!cancelled) { setBody(res.data as SourcesBody); setError(null); } })
      .catch((err) => { if (!cancelled) setError(describeNotesError(err, 'The sources could not be loaded.')); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [note.id, note.updated_at, cited, builderEnabled]);

  if (!builderEnabled) {
    return <p className="text-sm text-muted-foreground">Sources are listed for built notes while the builder is switched on.</p>;
  }
  if (!note.is_built && !(note.source_question_ids ?? []).length) {
    return <p className="text-sm text-muted-foreground">A manual note has no recorded sources. Build it from PYQs to list them.</p>;
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-2 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Show</span>
          <select value={cited} onChange={(e) => setCited(e.target.value as CitedFilter)} className="rounded-md border border-input bg-background px-2 py-1.5 text-sm">
            <option value="">Every PYQ</option>
            <option value="true">Cited in the note</option>
            <option value="false">Left out</option>
          </select>
        </label>
        {body && (
          <p className="pb-1.5 text-xs text-muted-foreground">
            {body.counts.cited} cited · {body.counts.not_cited} left out
            {body.counts.changed_since_build > 0 && <span className="text-amber-700 dark:text-amber-400"> · {body.counts.changed_since_build} changed since the build (rebuild the note)</span>}
          </p>
        )}
      </div>
      {loading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading…</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {body && !loading && (
        body.results.length === 0 ? <p className="text-sm text-muted-foreground">Nothing in this view.</p> : (
          <ul className="space-y-1.5">
            {body.results.map((row) => (
              <li key={row.question} className={`rounded-md border p-2 text-sm ${row.changed_since_build ? 'border-amber-500/60' : 'border-border'}`}>
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <Link href={practiceHref(row.question)} className="font-semibold text-primary hover:underline">Q{row.question}</Link>
                  <span className="text-muted-foreground">{row.asked_in}</span>
                  <Badge variant={keyStatusTone(row.key_status)}>{row.key_status}</Badge>
                  {!row.cited && <Badge variant="outline">left out</Badge>}
                  {row.reason && <span className="text-muted-foreground">{reasonLabel(row.reason)}</span>}
                  {row.changed_since_build && <Badge variant="warning">changed since the build</Badge>}
                  {!row.is_active && <Badge variant="outline">inactive</Badge>}
                </div>
                <p className="mt-1 break-words text-sm text-foreground">{row.stem_preview}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Key {row.current_key || '–'}
                  {row.cited && row.answer_at_build && row.answer_at_build !== row.current_key && ` (was ${row.answer_at_build} when built)`}
                </p>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

export default function NotePreview({ note, builderEnabled }: { note: LibraryNote; builderEnabled: boolean }) {
  const [tab, setTab] = useState<Tab>('note');
  const tabs: { value: Tab; label: string }[] = [
    { value: 'note', label: 'Note' },
    { value: 'sources', label: 'Sources' },
  ];
  return (
    <div className="mt-3 rounded-lg border border-border bg-background p-3">
      <div role="tablist" aria-label={`Preview of ${note.title}`} className="mb-3 flex gap-1.5">
        {tabs.map((t) => (
          <button
            key={t.value}
            type="button"
            role="tab"
            id={`note-${note.id}-tab-${t.value}`}
            aria-selected={tab === t.value}
            aria-controls={`note-${note.id}-panel-${t.value}`}
            onClick={() => setTab(t.value)}
            className={`rounded-full border px-3 py-1 text-xs ${tab === t.value ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-foreground hover:bg-accent'}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`note-${note.id}-panel-${tab}`} aria-labelledby={`note-${note.id}-tab-${tab}`}>
        {tab === 'note' ? <NoteTab note={note} builderEnabled={builderEnabled} /> : <SourcesTab note={note} builderEnabled={builderEnabled} />}
      </div>
    </div>
  );
}
