'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { topicNotesAPI } from '@/lib/api';
import { Plus, Loader2, Trash2, RefreshCw, BookOpen } from 'lucide-react';
import { hasNextPage, listCount, listRows } from '../_lib/adminHelpers';
import { fetchAllSubjects, useSubjectTopics, type AdminSubject } from '../_lib/useAdminTaxonomy';

interface TopicNoteRow {
  id: number;
  title: string;
  content: string;
  content_preview?: string;
  subject: number;
  topic: number;
  subject_name?: string;
  topic_name?: string;
  exam_type: string;
  is_combined: boolean;
  ai_generated?: boolean;
  is_published?: boolean;
  source_question_count?: number;
  created_at?: string;
  updated_at?: string;
}

const DRAFT_NOTE_CONTENT =
  '_Draft. Use "Generate" to compile this topic\'s PYQ explanations, or "Edit" to write the note._';

const EXAM_CHOICES = [
  { value: 'cms', label: 'UPSC CMS' },
  { value: 'neet_pg', label: 'NEET PG' },
  { value: 'ini_cet', label: 'INICET' },
  { value: 'usmle', label: 'USMLE' },
  { value: 'fmge', label: 'FMGE' },
  { value: 'other', label: 'Other' },
];

export default function AdminNotesPage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const isAdmin = !!user && (user.role === 'admin' || !!user.is_admin);

  const [notes, setNotes] = useState<TopicNoteRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<number | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [genSuccess, setGenSuccess] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Create form state
  const [newTitle, setNewTitle] = useState('');
  const [newSubjectId, setNewSubjectId] = useState('');
  const [newTopicId, setNewTopicId] = useState('');
  const [newExamType, setNewExamType] = useState('cms');
  const [newIsCombined, setNewIsCombined] = useState(false);
  const [subjects, setSubjects] = useState<AdminSubject[]>([]);
  const { ensureTopics, topicsFor, topicsPlaceholder } = useSubjectTopics();

  // List paging (the library endpoint returns 20 notes per page).
  const [notesTotal, setNotesTotal] = useState(0);
  const [notesNextPage, setNotesNextPage] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  // Inline editor (there is no /admin/notes/<id> route).
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState({ title: '', content: '', is_published: false });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const fetchNotes = useCallback(async (page = 1) => {
    if (page === 1) setLoading(true);
    else setLoadingMore(true);
    try {
      const r = await topicNotesAPI.adminList({ page });
      const body: any = r?.data ?? r;
      const list = listRows<TopicNoteRow>(body);
      setNotes((prev) => (page === 1 ? list : [...prev, ...list]));
      setNotesTotal(listCount(body));
      setNotesNextPage(hasNextPage(body) ? page + 1 : null);
    } catch {
      if (page === 1) setNotes([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    fetchNotes(1);
  }, [isAdmin, fetchNotes]);

  // Subjects for the create form: every page (the endpoint is paginated, so
  // treating the response as an array left the picker empty). Topics are
  // loaded for the chosen subject (TopicSerializer exposes `subject`, not
  // `subject_id`, so the old filter matched nothing either).
  useEffect(() => {
    fetchAllSubjects()
      .then(setSubjects)
      .catch(() => { /* tolerant */ });
  }, []);

  const filteredTopics = topicsFor(newSubjectId);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    if (!newTitle.trim() || !newSubjectId || !newTopicId) {
      setCreateError('Title, subject, and topic are required.');
      return;
    }
    setCreateLoading(true);
    try {
      // One note per (topic, exam, combined) (DB constraint uniq_topic_note).
      // If it already exists, open it instead of creating: the create
      // endpoint would otherwise reject it or overwrite it in place.
      const existingRes = await topicNotesAPI.adminList({ topic: Number(newTopicId), exam_type: newExamType });
      const existing = listRows<TopicNoteRow>(existingRes?.data).find(
        (n) => Number(n.topic) === Number(newTopicId) && Boolean(n.is_combined) === newIsCombined,
      );
      if (existing) {
        setNotes((prev) => (prev.some((n) => n.id === existing.id) ? prev : [existing, ...prev]));
        setShowCreate(false);
        startEdit(existing);
        setGenSuccess(`A note already exists for this topic and exam ("${existing.title}"), so it was opened for editing.`);
        return;
      }
      const payload: any = {
        title: newTitle.trim(),
        subject: Number(newSubjectId),
        topic: Number(newTopicId),
        exam_type: newExamType,
        is_combined: newIsCombined,
        // TopicNote.content may not be blank (the serializer rejected the
        // empty string, so every create failed). New notes start as an
        // unpublished draft; students only see published notes.
        content: DRAFT_NOTE_CONTENT,
      };
      const r = await topicNotesAPI.adminCreate(payload);
      const created: TopicNoteRow = r?.data ?? r;
      // The create endpoint returns an existing note for the same
      // exam/subject/topic/title instead of a duplicate; don't list it twice.
      const alreadyListed = notes.some((n) => n.id === created.id);
      setNotes((prev) => [created, ...prev.filter((n) => n.id !== created.id)]);
      if (!alreadyListed) setNotesTotal((t) => t + 1);
      setShowCreate(false);
      setNewTitle('');
      setNewSubjectId('');
      setNewTopicId('');
      setNewExamType('cms');
      setNewIsCombined(false);
    } catch (err: any) {
      const data = err?.response?.data;
      setCreateError(
        data?.detail || data?.error ||
        (data && typeof data === 'object' ? JSON.stringify(data).slice(0, 300) : '') ||
        err?.message || 'Failed to create note.',
      );
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleGenerate(note: TopicNoteRow) {
    setGenerating(note.id);
    setGenError(null);
    setGenSuccess(null);
    try {
      const r = await topicNotesAPI.adminGenerate(note.id);
      const body: any = r?.data ?? r;
      const msg = body?.detail || body?.message || 'Note generated.';
      setGenSuccess(`Note #${note.id}: ${msg}`);
      // Refresh the note in the list
      setNotes((prev) => prev.map(n => n.id === note.id ? { ...n, ...body } : n));
    } catch (err: any) {
      setGenError(err?.response?.data?.detail || err?.response?.data?.error || err?.message || 'Generation failed.');
    } finally {
      setGenerating(null);
    }
  }

  async function handleDelete(note: TopicNoteRow) {
    if (!window.confirm(`Delete note "${note.title}"? This cannot be undone.`)) return;
    try {
      await topicNotesAPI.delete(note.id);
      setNotes((prev) => prev.filter(n => n.id !== note.id));
      setNotesTotal((t) => Math.max(0, t - 1));
      if (editingNoteId === note.id) setEditingNoteId(null);
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Delete failed.');
    }
  }

  function startEdit(note: TopicNoteRow) {
    setEditingNoteId(note.id);
    setEditDraft({ title: note.title || '', content: note.content || '', is_published: !!note.is_published });
    setEditError(null);
  }

  async function handleSaveEdit(note: TopicNoteRow) {
    if (!editDraft.title.trim()) {
      setEditError('Title is required.');
      return;
    }
    setEditSaving(true);
    setEditError(null);
    try {
      const r = await topicNotesAPI.update(note.id, {
        title: editDraft.title.trim(),
        content: editDraft.content,
        is_published: editDraft.is_published,
      });
      const saved: TopicNoteRow = r?.data ?? r;
      setNotes((prev) => prev.map((n) => (n.id === note.id ? { ...n, ...saved } : n)));
      setEditingNoteId(null);
    } catch (err: any) {
      const data = err?.response?.data;
      setEditError(data?.detail || data?.error || (data && typeof data === 'object' ? JSON.stringify(data).slice(0, 300) : '') || err?.message || 'Save failed.');
    } finally {
      setEditSaving(false);
    }
  }

  const examLabel = (v: string) => EXAM_CHOICES.find(e => e.value === v)?.label || v;

  // Colours come from the theme tokens (text-foreground, bg-card,
  // border-border, text-muted-foreground, ...), which flip with the theme:
  // the hard-coded dark slate palette made the page white-on-white in light mode.
  // Plain divs, no second landmark: the AppShell layout sits inside the root
  // layout's main landmark, and its .page-container already pads the page.
  if (authLoading) {
    return <p className="p-6 [.page-container_&]:px-0 text-muted-foreground">Checking auth…</p>;
  }
  if (!isAuthenticated || !isAdmin) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 [.page-container_&]:px-0 text-center text-foreground">
        <p className="text-muted-foreground mb-3">You need admin access to view this page.</p>
        <button onClick={() => router.push('/login')} className="rounded bg-indigo-600 px-4 py-2 text-white">Sign in</button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 [.page-container_&]:p-0 text-foreground">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
          <h1 className="text-xl font-semibold">Topic Notes</h1>
          <span className="text-xs text-muted-foreground">
            {notesTotal > notes.length ? `${notes.length} of ${notesTotal} notes` : `${notes.length} notes`}
          </span>
        </div>
        <button
          onClick={() => setShowCreate(s => !s)}
          className="inline-flex items-center gap-1.5 rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" /> New Note
        </button>
      </div>

      {genError && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/60 dark:bg-red-900/30 dark:text-red-200">{genError}</div>
      )}
      {genSuccess && (
        <div className="mb-3 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-500/60 dark:bg-emerald-900/30 dark:text-emerald-200">{genSuccess}</div>
      )}

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="mb-4 rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-sm font-semibold text-foreground">Create Topic Note</h2>
          {createError && <p className="text-xs text-red-600 dark:text-red-300">{createError}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs text-muted-foreground">Title</span>
              <input className="mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm" value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="e.g. Hypertension — drug classes" />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Subject</span>
              <select
                className="mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm"
                value={newSubjectId}
                onChange={e => { setNewSubjectId(e.target.value); setNewTopicId(''); ensureTopics(e.target.value); }}
              >
                <option value="">Select…</option>
                {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Topic</span>
              <select
                className="mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm"
                value={newTopicId}
                onChange={e => setNewTopicId(e.target.value)}
                onFocus={() => ensureTopics(newSubjectId)}
                onMouseDown={() => ensureTopics(newSubjectId)}
                disabled={!newSubjectId}
              >
                <option value="">{!newSubjectId ? 'Pick a subject first' : topicsPlaceholder(newSubjectId, 'Select…')}</option>
                {filteredTopics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Exam</span>
              <select className="mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm" value={newExamType} onChange={e => setNewExamType(e.target.value)}>
                {EXAM_CHOICES.map(e => <option key={e.value} value={e.value}>{e.label}</option>)}
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input type="checkbox" checked={newIsCombined} onChange={e => setNewIsCombined(e.target.checked)} />
            Combined (synthesise across multiple exams on this topic)
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={createLoading} className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50">
              {createLoading ? 'Creating…' : 'Create'}
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="rounded border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted">Cancel</button>
          </div>
        </form>
      )}

      {/* Notes list */}
      {loading ? (
        <p className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading notes…</p>
      ) : notes.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
          <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-40" />
          <p>No topic notes yet.</p>
          <p className="text-xs mt-1">Create a note, then use &ldquo;Generate from Topic&rdquo; to compile PYQ explanations.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {notes.map(note => (
            <div key={note.id} className="rounded-lg border border-border bg-card p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-semibold text-foreground truncate">{note.title}</h3>
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase">{examLabel(note.exam_type)}</span>
                    {note.is_combined && <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] text-purple-700 dark:bg-purple-700/60 dark:text-purple-200">Combined</span>}
                    {note.ai_generated && <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-700 dark:bg-violet-700/60 dark:text-violet-200">AI</span>}
                    {note.is_published && <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] text-emerald-700 dark:bg-emerald-700/60 dark:text-emerald-200">Published</span>}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span>{note.subject_name || `Subject #${note.subject}`}</span>
                    <span>→</span>
                    <span>{note.topic_name || `Topic #${note.topic}`}</span>
                    <span>•</span>
                    <span>{note.source_question_count ?? 0} questions</span>
                    <span>•</span>
                    <span>Updated {note.updated_at ? new Date(note.updated_at).toLocaleDateString() : '—'}</span>
                  </div>
                  {note.content_preview && editingNoteId !== note.id && (
                    <p className="mt-2 text-xs text-muted-foreground line-clamp-2">{note.content_preview}</p>
                  )}
                  {editingNoteId === note.id && (
                    <div className="mt-3 space-y-2">
                      {editError && <p className="text-xs text-red-600 dark:text-red-300">{editError}</p>}
                      <label className="block">
                        <span className="text-xs text-muted-foreground">Title</span>
                        <input
                          className="mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm"
                          value={editDraft.title}
                          onChange={e => setEditDraft({ ...editDraft, title: e.target.value })}
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs text-muted-foreground">Content (Markdown)</span>
                        <textarea
                          className="mt-1 w-full rounded border border-input bg-background px-2 py-1.5 text-sm font-mono"
                          rows={14}
                          value={editDraft.content}
                          onChange={e => setEditDraft({ ...editDraft, content: e.target.value })}
                        />
                      </label>
                      <label className="flex items-center gap-2 text-sm text-foreground">
                        <input
                          type="checkbox"
                          checked={editDraft.is_published}
                          onChange={e => setEditDraft({ ...editDraft, is_published: e.target.checked })}
                        />
                        Published (visible to students)
                      </label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleSaveEdit(note)}
                          disabled={editSaving}
                          className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
                        >
                          {editSaving ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingNoteId(null)}
                          disabled={editSaving}
                          className="rounded border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => handleGenerate(note)}
                    disabled={generating === note.id}
                    title="Generate/regenerate from PYQ explanations"
                    className="inline-flex items-center gap-1 rounded bg-violet-600 px-2.5 py-1.5 text-xs text-white hover:bg-violet-700 disabled:opacity-50"
                  >
                    {generating === note.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                    {generating === note.id ? 'Generating…' : 'Generate'}
                  </button>
                  {/* Edits inline: the old link went to /admin/notes/<id>, a route that does not exist. */}
                  <button
                    onClick={() => (editingNoteId === note.id ? setEditingNoteId(null) : startEdit(note))}
                    title="Edit note"
                    className="rounded border border-border px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted"
                  >
                    {editingNoteId === note.id ? 'Close' : 'Edit'}
                  </button>
                  <button
                    onClick={() => handleDelete(note)}
                    title="Delete"
                    aria-label={`Delete note ${note.title}`}
                    className="rounded text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 px-1.5 py-1.5"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {notesNextPage !== null && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => fetchNotes(notesNextPage)}
                disabled={loadingMore}
                className="rounded border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted disabled:opacity-50"
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
