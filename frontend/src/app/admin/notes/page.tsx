'use client';

/**
 * Admin: topic notes. Build notes from PYQs (BuildPanel -> POST topic-notes/build/), preview each
 * note as students read it with its source PYQs (NotePreview), rebuild, edit, publish / unpublish,
 * delete, and create a manual note. Builds only write unpublished drafts; publishing is a separate,
 * explicit step. The builder routes depend on the server's TOPIC_NOTES_BUILDER flag (GET
 * topic-notes/build/ reports it); manual notes work either way.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { BookOpen, Eye, Loader2, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { notesAPI } from '@/lib/notesAPI';
import { Badge } from '@/components/ui/badge';
import { hasNextPage, listCount, listRows } from '../_lib/adminHelpers';
import { fetchAllSubjects, useSubjectTopics, type AdminSubject } from '../_lib/useAdminTaxonomy';
import BuildPanel from './BuildPanel';
import NotePreview from './NotePreview';
import {
  PROVISIONAL_MARK,
  contentEditWarning,
  describeNotesError,
  examLabel,
  type BuildReport,
  type BuilderStatus,
  type LibraryNote,
} from '@/components/notes/notesData';

const DRAFT_NOTE_CONTENT =
  '_Draft. Use "Rebuild from PYQs" (or "Generate") to fill this note, or "Edit" to write it._';

const EXAM_CHOICES = [
  { value: 'cms', label: 'UPSC CMS' },
  { value: 'neet_pg', label: 'NEET PG' },
  { value: 'ini_cet', label: 'INI-CET' },
  { value: 'usmle', label: 'USMLE' },
  { value: 'fmge', label: 'FMGE' },
  { value: 'other', label: 'Other' },
];

const LIBRARY_FILTERS = {
  exam: [
    { value: '', label: 'Every exam' },
    { value: 'cms', label: 'UPSC CMS' },
    { value: 'neet_pg', label: 'NEET PG' },
    { value: 'ini_cet', label: 'INI-CET' },
    { value: 'all', label: 'Cross-exam' },
  ],
  status: [
    { value: '', label: 'Published and drafts' },
    { value: 'published', label: 'Published' },
    { value: 'draft', label: 'Drafts' },
    { value: 'stale', label: 'Stale (source changed)' },
  ],
  method: [
    { value: '', label: 'Any method' },
    { value: 'extractive', label: 'Built from PYQs' },
    { value: 'llm', label: 'AI rewrite of PYQs' },
    { value: 'manual', label: 'Manual' },
  ],
};

const SELECT = 'rounded border border-input bg-background px-2 py-1.5 text-sm text-foreground';
const ACTION = 'inline-flex items-center gap-1 rounded border border-border px-2 py-1.5 text-xs text-foreground hover:bg-muted disabled:opacity-50';

function methodLabel(note: LibraryNote): string {
  if (note.generation_method === 'extractive') return 'From PYQs';
  if (note.generation_method === 'llm') return 'AI rewrite';
  return note.ai_generated ? 'AI' : 'Manual';
}

export default function AdminNotesPage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const isAdmin = !!user && (user.role === 'admin' || !!user.is_admin);

  const [status, setStatus] = useState<BuilderStatus | null>(null);
  const builderEnabled = Boolean(status?.enabled);

  const [notes, setNotes] = useState<LibraryNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notesTotal, setNotesTotal] = useState(0);
  const [notesNextPage, setNotesNextPage] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [filters, setFilters] = useState({ exam: '', status: '', method: '' });

  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [newSubjectId, setNewSubjectId] = useState('');
  const [newTopicId, setNewTopicId] = useState('');
  const [newExamType, setNewExamType] = useState('cms');
  const [newIsCombined, setNewIsCombined] = useState(false);
  const [subjects, setSubjects] = useState<AdminSubject[]>([]);
  const { ensureTopics, topicsFor, topicsPlaceholder } = useSubjectTopics();

  // Inline editor (there is no /admin/notes/<id> route).
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState({ title: '', content: '', is_published: false });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const libraryParams = useCallback((page: number) => {
    const params: Record<string, string | number> = { page };
    if (filters.exam) params.exam_type = filters.exam;
    if (filters.status === 'published') params.is_published = 'true';
    if (filters.status === 'draft') params.is_published = 'false';
    if (filters.status === 'stale') params.is_stale = 'true';
    if (filters.method) params.generation_method = filters.method;
    return params;
  }, [filters]);

  const fetchNotes = useCallback(async (page = 1) => {
    if (page === 1) setLoading(true);
    else setLoadingMore(true);
    try {
      const r = await notesAPI.library(libraryParams(page));
      const body = r?.data;
      const list = listRows<LibraryNote>(body);
      setNotes((prev) => (page === 1 ? list : [...prev, ...list.filter((n) => !prev.some((p) => p.id === n.id))]));
      setNotesTotal(listCount(body));
      setNotesNextPage(hasNextPage(body) ? page + 1 : null);
      setLoadError(null);
    } catch (err) {
      if (page === 1) setNotes([]);
      setLoadError(describeNotesError(err, 'The note library could not be loaded.'));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [libraryParams]);

  useEffect(() => {
    if (!isAdmin) return;
    fetchNotes(1);
  }, [isAdmin, fetchNotes]);

  useEffect(() => {
    if (!isAdmin) return;
    notesAPI.builderStatus().then((r) => setStatus(r.data)).catch(() => setStatus(null));
    // Every subject (the endpoint is paginated); topics load per subject on demand.
    fetchAllSubjects().then(setSubjects).catch(() => { /* tolerant */ });
  }, [isAdmin]);

  function replaceNote(saved: LibraryNote) {
    setNotes((prev) => prev.map((n) => (n.id === saved.id ? { ...n, ...saved } : n)));
  }

  async function refreshNote(id: number) {
    try {
      const r = await notesAPI.libraryNote(id);
      replaceNote(r.data as LibraryNote);
    } catch { /* the list refresh shows it */ }
  }

  function onBuilt(report: BuildReport) {
    const touched = report.notes.filter((row) => row.note_id && (row.action === 'create' || row.action === 'update'));
    setMessage({ tone: 'ok', text: `${touched.length} draft note${touched.length === 1 ? '' : 's'} written. Preview them below, then publish.` });
    fetchNotes(1);
  }

  function openNote(id: number) {
    setOpenId(id);
    setFilters({ exam: '', status: '', method: '' });
    if (typeof window !== 'undefined') {
      window.setTimeout(() => document.getElementById(`note-row-${id}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 400);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    if (!newTitle.trim() || !newSubjectId || !newTopicId) {
      setCreateError('Title, subject, and topic are required.');
      return;
    }
    setCreateLoading(true);
    try {
      // One note per (topic, exam, combined) (DB constraint uniq_topic_note): open an existing one.
      const existingRes = await notesAPI.library({ topic: Number(newTopicId), exam_type: newIsCombined ? 'all' : newExamType });
      const existing = listRows<LibraryNote>(existingRes?.data).find(
        (n) => Number(n.topic) === Number(newTopicId) && Boolean(n.is_combined) === newIsCombined,
      );
      if (existing) {
        setNotes((prev) => (prev.some((n) => n.id === existing.id) ? prev : [existing, ...prev]));
        setShowCreate(false);
        startEdit(existing);
        setMessage({ tone: 'ok', text: `A note already exists for this topic and exam ("${existing.title}"), so it was opened for editing.` });
        return;
      }
      const r = await notesAPI.createManual({
        title: newTitle.trim(),
        subject: Number(newSubjectId),
        topic: Number(newTopicId),
        exam_type: newIsCombined ? 'all' : newExamType,
        is_combined: newIsCombined,
        // New notes start as an unpublished draft; students only see published notes.
        content: DRAFT_NOTE_CONTENT,
      });
      const created = r.data as LibraryNote;
      const alreadyListed = notes.some((n) => n.id === created.id);
      setNotes((prev) => [created, ...prev.filter((n) => n.id !== created.id)]);
      if (!alreadyListed) setNotesTotal((t) => t + 1);
      setShowCreate(false);
      setNewTitle('');
      setNewSubjectId('');
      setNewTopicId('');
      setNewExamType('cms');
      setNewIsCombined(false);
    } catch (err) {
      setCreateError(describeNotesError(err, 'Failed to create note.'));
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleRebuild(note: LibraryNote) {
    if (builderEnabled && !note.is_built && (note.content || '').trim() && note.content !== DRAFT_NOTE_CONTENT
      && !window.confirm(`Replace the text of "${note.title}" with a note built from its PYQs?`)) {
      return;
    }
    setBusyId(note.id);
    setMessage(null);
    try {
      const r = await notesAPI.rebuild(note.id, builderEnabled ? { force: true } : {});
      const body = r.data as { detail?: string; note?: LibraryNote; build?: { counts?: Record<string, number> } };
      if (body.note?.id) replaceNote(body.note);
      else await refreshNote(note.id);
      const counts = body.build?.counts;
      const extra = counts && typeof counts.cited === 'number'
        ? ` ${counts.cited} PYQs cited (${counts.verified ?? 0} verified, ${counts.provisional ?? 0} provisional), ${counts.excluded ?? 0} excluded.`
        : '';
      setMessage({ tone: 'ok', text: `Note #${note.id}: ${body.detail || 'rebuilt.'}${extra}` });
    } catch (err) {
      setMessage({ tone: 'error', text: `Note #${note.id}: ${describeNotesError(err, 'Rebuild failed.')}` });
    } finally {
      setBusyId(null);
    }
  }

  async function handleTogglePublish(note: LibraryNote) {
    const publish = !note.is_published;
    if (publish && (note.provisional_source_count ?? 0) > 0 && !window.confirm(
      `${note.provisional_source_count} PYQ${note.provisional_source_count === 1 ? '' : 's'} behind this note have answer keys `
      + `that are not verified; students see those points marked ${PROVISIONAL_MARK} provisional. Publish it?`,
    )) {
      return;
    }
    setBusyId(note.id);
    setMessage(null);
    try {
      const r = await notesAPI.update(note.id, { is_published: publish });
      replaceNote(r.data as LibraryNote);
      setMessage({ tone: 'ok', text: `"${note.title}" is now ${publish ? 'published' : 'a draft'}.` });
    } catch (err) {
      setMessage({ tone: 'error', text: describeNotesError(err, 'The note could not be updated.') });
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(note: LibraryNote) {
    if (!window.confirm(`Delete note "${note.title}"? This cannot be undone.`)) return;
    try {
      await notesAPI.remove(note.id);
      setNotes((prev) => prev.filter((n) => n.id !== note.id));
      setNotesTotal((t) => Math.max(0, t - 1));
      if (editingNoteId === note.id) setEditingNoteId(null);
      if (openId === note.id) setOpenId(null);
    } catch (err) {
      setMessage({ tone: 'error', text: describeNotesError(err, 'Delete failed.') });
    }
  }

  function startEdit(note: LibraryNote) {
    setEditingNoteId(note.id);
    setEditDraft({ title: note.title || '', content: note.content || '', is_published: !!note.is_published });
    setEditError(null);
  }

  async function handleSaveEdit(note: LibraryNote) {
    if (!editDraft.title.trim()) {
      setEditError('Title is required.');
      return;
    }
    setEditSaving(true);
    setEditError(null);
    try {
      const data: Record<string, unknown> = { title: editDraft.title.trim(), is_published: editDraft.is_published };
      // Send the content only when it changed: a hand edit turns a built note into a manual one.
      if (editDraft.content !== (note.content || '')) data.content = editDraft.content;
      const r = await notesAPI.update(note.id, data);
      replaceNote(r.data as LibraryNote);
      setEditingNoteId(null);
    } catch (err) {
      setEditError(describeNotesError(err, 'Save failed.'));
    } finally {
      setEditSaving(false);
    }
  }

  // Theme tokens (text-foreground, bg-card, border-border, text-muted-foreground) flip with the theme.
  // No second landmark: the AppShell's .page-container already pads the page.
  if (authLoading) {
    return <p className="p-6 text-muted-foreground [.page-container_&]:px-0">Checking access…</p>;
  }
  if (!isAuthenticated || !isAdmin) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 text-center text-foreground [.page-container_&]:px-0">
        <p className="mb-3 text-muted-foreground">You need admin access to view this page.</p>
        <button onClick={() => router.push('/login?next=' + encodeURIComponent('/admin/notes'))} className="rounded bg-primary px-4 py-2 text-primary-foreground">Sign in</button>
      </div>
    );
  }

  const filteredOut = Boolean(filters.exam || filters.status || filters.method);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 text-foreground [.page-container_&]:p-0">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <BookOpen className="h-5 w-5 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
          <h1 className="text-xl font-semibold">Topic Notes</h1>
          <span className="text-xs text-muted-foreground">
            {notesTotal > notes.length ? `${notes.length} of ${notesTotal} notes` : `${notes.length} notes`}
          </span>
          {status && (
            <Badge variant={status.enabled ? 'success' : 'outline'}>
              Builder {status.enabled ? 'on' : 'off'}{status.enabled && status.ai_offline ? ' · offline' : ''}
            </Badge>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/topic-notes" className="inline-flex items-center gap-1.5 rounded border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted">
            <Eye className="h-4 w-4" aria-hidden="true" /> Student view
          </Link>
          <button
            type="button"
            onClick={() => setShowCreate((s) => !s)}
            aria-expanded={showCreate}
            className="inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" aria-hidden="true" /> New manual note
          </button>
        </div>
      </div>

      {message && (
        <div
          role={message.tone === 'error' ? 'alert' : 'status'}
          className={`mb-3 rounded border px-3 py-2 text-sm ${message.tone === 'error'
            ? 'border-red-300 bg-red-50 text-red-800 dark:border-red-500/60 dark:bg-red-900/30 dark:text-red-200'
            : 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/60 dark:bg-emerald-900/30 dark:text-emerald-200'}`}
        >
          {message.text}
        </div>
      )}

      <BuildPanel status={status} subjects={subjects} onBuilt={onBuilt} onOpenNote={openNote} />

      {showCreate && (
        <form onSubmit={handleCreate} className="mb-4 space-y-3 rounded-lg border border-border bg-card p-4">
          <h2 className="text-sm font-semibold text-foreground">New manual note</h2>
          <p className="text-xs text-muted-foreground">
            A manual note is shown as written. Free accounts read it only when every source PYQ is free; mark unverified
            answers with {PROVISIONAL_MARK}.
          </p>
          {createError && <p role="alert" className="text-xs text-red-600 dark:text-red-300">{createError}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs text-muted-foreground">Title</span>
              <input className={`mt-1 w-full ${SELECT}`} value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="e.g. Hypertension — drug classes" />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Subject</span>
              <select
                className={`mt-1 w-full ${SELECT}`}
                value={newSubjectId}
                onChange={(e) => { setNewSubjectId(e.target.value); setNewTopicId(''); ensureTopics(e.target.value); }}
              >
                <option value="">Select…</option>
                {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Topic</span>
              <select
                className={`mt-1 w-full ${SELECT}`}
                value={newTopicId}
                onChange={(e) => setNewTopicId(e.target.value)}
                onFocus={() => ensureTopics(newSubjectId)}
                onMouseDown={() => ensureTopics(newSubjectId)}
                disabled={!newSubjectId}
              >
                <option value="">{!newSubjectId ? 'Pick a subject first' : topicsPlaceholder(newSubjectId, 'Select…')}</option>
                {topicsFor(newSubjectId).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Exam</span>
              <select className={`mt-1 w-full ${SELECT}`} value={newExamType} onChange={(e) => setNewExamType(e.target.value)} disabled={newIsCombined}>
                {EXAM_CHOICES.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input type="checkbox" checked={newIsCombined} onChange={(e) => setNewIsCombined(e.target.checked)} />
            Cross-exam (one note for every exam on this topic)
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={createLoading} className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
              {createLoading ? 'Creating…' : 'Create draft'}
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="rounded border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted">Cancel</button>
          </div>
        </form>
      )}

      <section aria-labelledby="library-heading">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <h2 id="library-heading" className="text-sm font-semibold text-foreground">Library</h2>
          <div className="flex flex-wrap gap-2">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Exam</span>
              <select className={SELECT} value={filters.exam} onChange={(e) => setFilters((f) => ({ ...f, exam: e.target.value }))}>
                {LIBRARY_FILTERS.exam.map((o) => <option key={o.value || 'any'} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Status</span>
              <select className={SELECT} value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}>
                {LIBRARY_FILTERS.status.map((o) => <option key={o.value || 'any'} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Method</span>
              <select className={SELECT} value={filters.method} onChange={(e) => setFilters((f) => ({ ...f, method: e.target.value }))}>
                {LIBRARY_FILTERS.method.map((o) => <option key={o.value || 'any'} value={o.value}>{o.label}</option>)}
              </select>
            </label>
          </div>
        </div>

        {loadError && <p role="alert" className="mb-3 text-sm text-destructive">{loadError}</p>}
        {loading ? (
          <p className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading notes…</p>
        ) : notes.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
            <BookOpen className="mx-auto mb-2 h-8 w-8 opacity-40" aria-hidden="true" />
            <p>{filteredOut ? 'No notes match these filters.' : 'No topic notes yet.'}</p>
            {!filteredOut && <p className="mt-1 text-xs">Build drafts from PYQs above, or create a manual note.</p>}
          </div>
        ) : (
          <ul className="grid gap-3">
            {notes.map((note) => {
              const busy = busyId === note.id;
              const counts = note.build_counts || {};
              const editWarning = editingNoteId === note.id ? contentEditWarning(note, editDraft.content) : null;
              return (
                <li key={note.id} id={`note-row-${note.id}`} className="scroll-mt-20 rounded-lg border border-border bg-card p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <h3 className="min-w-0 break-words text-sm font-semibold text-foreground">{note.title}</h3>
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase">{examLabel(note.exam_type, note.is_combined)}</span>
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">{methodLabel(note)}</span>
                        {note.is_published
                          ? <Badge variant="success">Published</Badge>
                          : <Badge variant="outline">Draft</Badge>}
                        {note.is_stale && <Badge variant="warning">Stale: rebuild</Badge>}
                      </div>
                      <p className="mt-1 break-words text-xs text-muted-foreground">
                        {note.subject_name || (note.subject ? `Subject #${note.subject}` : 'No subject')}
                        {' › '}
                        {note.topic_name || (note.topic ? `Topic #${note.topic}` : 'whole subject')}
                        {' · '}
                        {note.is_built
                          ? `${counts.cited ?? note.source_question_count ?? 0} PYQs (${note.verified_source_count ?? 0} verified, ${note.provisional_source_count ?? 0} provisional ${PROVISIONAL_MARK}, ${note.excluded_source_count ?? 0} excluded)`
                          : `${note.source_question_count ?? 0} source PYQs`}
                        {' · '}
                        Updated {note.updated_at ? new Date(note.updated_at).toLocaleDateString() : '—'}
                      </p>
                      {note.content_preview && editingNoteId !== note.id && openId !== note.id && (
                        <p className="mt-2 line-clamp-2 break-words text-xs text-muted-foreground">{note.content_preview}</p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                      <button type="button" className={ACTION} aria-expanded={openId === note.id} onClick={() => setOpenId(openId === note.id ? null : note.id)}>
                        <Eye className="h-3 w-3" aria-hidden="true" /> {openId === note.id ? 'Hide preview' : 'Preview & sources'}
                      </button>
                      <button type="button" className={ACTION} onClick={() => handleRebuild(note)} disabled={busy}
                        title={builderEnabled ? 'Build this note again from its PYQs' : 'Generate with the AI generator (the PYQ builder is off)'}>
                        {busy ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <RefreshCw className="h-3 w-3" aria-hidden="true" />}
                        {builderEnabled ? (note.is_built ? 'Rebuild from PYQs' : 'Build from PYQs') : 'Generate (AI)'}
                      </button>
                      <button type="button" className={ACTION} onClick={() => (editingNoteId === note.id ? setEditingNoteId(null) : startEdit(note))}>
                        {editingNoteId === note.id ? 'Close editor' : 'Edit'}
                      </button>
                      <button type="button" className={ACTION} onClick={() => handleTogglePublish(note)} disabled={busy}>
                        {note.is_published ? 'Unpublish' : 'Publish'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(note)}
                        aria-label={`Delete note ${note.title}`}
                        title="Delete"
                        className="rounded px-1.5 py-1.5 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  {editingNoteId === note.id && (
                    <div className="mt-3 space-y-2">
                      {editError && <p role="alert" className="text-xs text-red-600 dark:text-red-300">{editError}</p>}
                      <label className="block">
                        <span className="text-xs text-muted-foreground">Title</span>
                        <input className={`mt-1 w-full ${SELECT}`} value={editDraft.title} onChange={(e) => setEditDraft({ ...editDraft, title: e.target.value })} />
                      </label>
                      <label className="block">
                        <span className="text-xs text-muted-foreground">Content (Markdown)</span>
                        <textarea
                          className={`mt-1 w-full font-mono ${SELECT}`}
                          rows={14}
                          value={editDraft.content}
                          onChange={(e) => setEditDraft({ ...editDraft, content: e.target.value })}
                        />
                      </label>
                      {editWarning && <p className="text-xs text-amber-700 dark:text-amber-400">{editWarning}</p>}
                      <label className="flex items-center gap-2 text-sm text-foreground">
                        <input type="checkbox" checked={editDraft.is_published} onChange={(e) => setEditDraft({ ...editDraft, is_published: e.target.checked })} />
                        Published (visible to students)
                      </label>
                      <div className="flex gap-2">
                        <button type="button" onClick={() => handleSaveEdit(note)} disabled={editSaving}
                          className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                          {editSaving ? 'Saving…' : 'Save'}
                        </button>
                        <button type="button" onClick={() => setEditingNoteId(null)} disabled={editSaving}
                          className="rounded border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted">
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {openId === note.id && <NotePreview note={note} builderEnabled={builderEnabled} />}
                </li>
              );
            })}
            {notesNextPage !== null && (
              <li className="flex justify-center">
                <button type="button" onClick={() => fetchNotes(notesNextPage)} disabled={loadingMore}
                  className="rounded border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted disabled:opacity-50">
                  {loadingMore ? 'Loading…' : 'Load more'}
                </button>
              </li>
            )}
          </ul>
        )}
      </section>
    </div>
  );
}
