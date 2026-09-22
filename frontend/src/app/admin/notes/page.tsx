'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { questionsAPI, topicNotesAPI } from '@/lib/api';
import { Plus, Loader2, Trash2, RefreshCw, ExternalLink, BookOpen } from 'lucide-react';

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
  const isAdmin = !!user?.is_admin;

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
  const [subjects, setSubjects] = useState<Array<{ id: number; name: string }>>([]);
  const [topics, setTopics] = useState<Array<{ id: number; name: string; subject_id?: number }>>([]);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    try {
      const r = await topicNotesAPI.adminList();
      const body: any = r?.data ?? r;
      const list: TopicNoteRow[] = Array.isArray(body) ? body : (body?.results || body?.data || []);
      setNotes(list);
    } catch {
      setNotes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    fetchNotes();
  }, [isAdmin, fetchNotes]);

  // Load subjects/topics for the create form
  useEffect(() => {
    (async () => {
      try {
        const sr = await questionsAPI.getSubjects?.();
        setSubjects(Array.isArray(sr?.data) ? sr.data : []);
      } catch { /* tolerant */ }
      try {
        const tr = await questionsAPI.getTopics?.();
        setTopics(Array.isArray(tr?.data) ? tr.data : []);
      } catch { /* tolerant */ }
    })();
  }, []);

  const filteredTopics = topics.filter(t => !newSubjectId || String(t.subject_id) === String(newSubjectId));

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    if (!newTitle.trim() || !newSubjectId || !newTopicId) {
      setCreateError('Title, subject, and topic are required.');
      return;
    }
    setCreateLoading(true);
    try {
      const payload: any = {
        title: newTitle.trim(),
        subject: Number(newSubjectId),
        topic: Number(newTopicId),
        exam_type: newExamType,
        is_combined: newIsCombined,
        content: '',
      };
      const r = await topicNotesAPI.adminCreate(payload);
      const created: TopicNoteRow = r?.data ?? r;
      setNotes([created, ...notes]);
      setShowCreate(false);
      setNewTitle('');
      setNewSubjectId('');
      setNewTopicId('');
      setNewExamType('cms');
      setNewIsCombined(false);
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || err?.message || 'Failed to create note.');
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
      setNotes(notes.map(n => n.id === note.id ? { ...n, ...body } : n));
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
      setNotes(notes.filter(n => n.id !== note.id));
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Delete failed.');
    }
  }

  const examLabel = (v: string) => EXAM_CHOICES.find(e => e.value === v)?.label || v;

  if (authLoading) {
    return <p className="p-6 text-slate-400">Checking auth…</p>;
  }
  if (!isAuthenticated || !isAdmin) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-12 text-center">
        <p className="text-slate-400 mb-3">You need admin access to view this page.</p>
        <button onClick={() => router.push('/login')} className="rounded bg-indigo-600 px-4 py-2 text-white">Sign in</button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 text-slate-100">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-indigo-400" />
          <h1 className="text-xl font-semibold">Topic Notes</h1>
          <span className="text-xs text-slate-400">{notes.length} notes</span>
        </div>
        <button
          onClick={() => setShowCreate(s => !s)}
          className="inline-flex items-center gap-1.5 rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" /> New Note
        </button>
      </div>

      {genError && (
        <div className="mb-3 rounded border border-red-500/60 bg-red-900/30 px-3 py-2 text-sm text-red-200">{genError}</div>
      )}
      {genSuccess && (
        <div className="mb-3 rounded border border-emerald-500/60 bg-emerald-900/30 px-3 py-2 text-sm text-emerald-200">{genSuccess}</div>
      )}

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="mb-4 rounded-lg border border-slate-700/40 bg-slate-900/40 p-4 space-y-3">
          <h2 className="text-sm font-semibold text-slate-200">Create Topic Note</h2>
          {createError && <p className="text-xs text-red-300">{createError}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs text-slate-400">Title</span>
              <input className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm" value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="e.g. Hypertension — drug classes" />
            </label>
            <label className="block">
              <span className="text-xs text-slate-400">Subject</span>
              <select className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm" value={newSubjectId} onChange={e => setNewSubjectId(e.target.value)}>
                <option value="">Select…</option>
                {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-slate-400">Topic</span>
              <select className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm" value={newTopicId} onChange={e => setNewTopicId(e.target.value)} disabled={!newSubjectId}>
                <option value="">{newSubjectId ? 'Select…' : 'Pick a subject first'}</option>
                {filteredTopics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-slate-400">Exam</span>
              <select className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm" value={newExamType} onChange={e => setNewExamType(e.target.value)}>
                {EXAM_CHOICES.map(e => <option key={e.value} value={e.value}>{e.label}</option>)}
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={newIsCombined} onChange={e => setNewIsCombined(e.target.checked)} />
            Combined (synthesise across multiple exams on this topic)
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={createLoading} className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50">
              {createLoading ? 'Creating…' : 'Create'}
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800">Cancel</button>
          </div>
        </form>
      )}

      {/* Notes list */}
      {loading ? (
        <p className="flex items-center gap-2 text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading notes…</p>
      ) : notes.length === 0 ? (
        <div className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-8 text-center text-slate-400">
          <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-40" />
          <p>No topic notes yet.</p>
          <p className="text-xs mt-1">Create a note, then use &ldquo;Generate from Topic&rdquo; to compile PYQ explanations.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {notes.map(note => (
            <div key={note.id} className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-semibold text-slate-100 truncate">{note.title}</h3>
                    <span className="rounded bg-slate-700/60 px-1.5 py-0.5 text-[10px] uppercase">{examLabel(note.exam_type)}</span>
                    {note.is_combined && <span className="rounded bg-purple-700/60 px-1.5 py-0.5 text-[10px] text-purple-200">Combined</span>}
                    {note.ai_generated && <span className="rounded bg-violet-700/60 px-1.5 py-0.5 text-[10px] text-violet-200">AI</span>}
                    {note.is_published && <span className="rounded bg-emerald-700/60 px-1.5 py-0.5 text-[10px] text-emerald-200">Published</span>}
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-slate-400">
                    <span>{note.subject_name || `Subject #${note.subject}`}</span>
                    <span>→</span>
                    <span>{note.topic_name || `Topic #${note.topic}`}</span>
                    <span>•</span>
                    <span>{note.source_question_count ?? 0} questions</span>
                    <span>•</span>
                    <span>Updated {note.updated_at ? new Date(note.updated_at).toLocaleDateString() : '—'}</span>
                  </div>
                  {note.content_preview && (
                    <p className="mt-2 text-xs text-slate-400 line-clamp-2">{note.content_preview}</p>
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
                  <button
                    onClick={() => router.push(`/admin/notes/${note.id}`)}
                    title="Edit note"
                    className="rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(note)}
                    title="Delete"
                    className="rounded text-red-400 hover:text-red-300 px-1.5 py-1.5"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
