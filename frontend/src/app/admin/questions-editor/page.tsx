'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { questionsAPI } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import QuestionEditModal from './QuestionEditModal';

export default function AdminQuestionsEditorPage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  // Client-side admin gate. The backend still enforces `IsAdminUser` on every
  // mutation, but hiding destructive UI from non-admins keeps student
  // sessions tidy and the audit log clean.
  const isAdmin = !!user?.is_admin;

  const [questions, setQuestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Filters
  const [needsReview, setNeedsReview] = useState(false);
  const [isDropped, setIsDropped] = useState(false);
  const [search, setSearch] = useState('');
  const [examType, setExamType] = useState<string>('');
  const [year, setYear] = useState<string>('');

  // Edit modal state
  const [editing, setEditing] = useState<any | null>(null);
  const onEdit = (q: any) => setEditing(q);

  // Merge-duplicates modal state (Bug 4 — surface duplicate questions in the list).
  const [mergeFor, setMergeFor] = useState<any | null>(null);
  const [mergeCluster, setMergeCluster] = useState<any | null>(null);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [mergeSubmitting, setMergeSubmitting] = useState(false);
  const [mergeDropIds, setMergeDropIds] = useState<number[]>([]);
  const [mergeError, setMergeError] = useState<string | null>(null);

  // Remove-from-bank modal state (durable soft-delete).
  const [removeFor, setRemoveFor] = useState<any | null>(null);
  const [removeReason, setRemoveReason] = useState('');
  const [removeConfirmId, setRemoveConfirmId] = useState('');
  const [removeSubmitting, setRemoveSubmitting] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  // Drag and drop state
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);

  // Subjects and Topics for inline editing
  const [subjects, setSubjects] = useState<any[]>([]);
  const [topics, setTopics] = useState<any[]>([]);

  // Per-exam counts so the user can see which exam has what before filtering
  const [examCounts, setExamCounts] = useState<Record<string, number>>({});

  // Senior secondary filters (separate row so the exam chips are uncluttered)
  const [subjectId, setSubjectId] = useState<string>('');
  const [topicId, setTopicId] = useState<string>('');
  const [difficulty, setDifficulty] = useState<string>('');
  const [isControversial, setIsControversial] = useState(false);
  const [isImageBased, setIsImageBased] = useState(false);

  const fetchTaxonomy = async () => {
    try {
      const resSub = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.9:8000/api'}/questions/subjects/`);
      const dataSub = await resSub.json();
      setSubjects(dataSub.results || dataSub || []);

      const resTop = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.9:8000/api'}/questions/topics/`);
      const dataTop = await resTop.json();
      setTopics(dataTop.results || dataTop || []);
    } catch (e) {
      console.error(e);
    }
  };

  // Count how many questions match each exam track so the user can see
  // at-a-glance how much content lives in each track. Cached until the page is reloaded.
  const fetchExamCounts = async () => {
    const tracks: Array<{ key: string; label: string; color: string }> = [
      { key: '', label: 'All Exams', color: 'gray' },
      { key: 'cms', label: 'UPSC CMS', color: 'blue' },
      { key: 'neet_pg', label: 'NEET PG', color: 'emerald' },
      { key: 'ini_cet', label: 'INI-CET', color: 'purple' },
      { key: 'usmle', label: 'USMLE', color: 'amber' },
      { key: 'fmge', label: 'FMGE', color: 'rose' },
    ];
    try {
      const results = await Promise.all(
        tracks.map(async (t) => {
          const params: any = { page: 1, page_size: 1 };
          if (t.key) params.exam_type = t.key;
          const res = await questionsAPI.list(params);
          return [t.key, Number(res.data.count ?? 0)] as const;
        })
      );
      setExamCounts(Object.fromEntries(results));
    } catch (e) {
      console.error('Failed to fetch exam counts', e);
    }
  };

  useEffect(() => {
    fetchTaxonomy();
    fetchExamCounts();
  }, []);

  const fetchQuestions = async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 20, ordering: 'display_number' };
      if (needsReview) params.needs_review = true;
      if (isDropped) params.is_dropped = true;
      if (examType) params.exam_type = examType;
      if (year) params.year = year;
      if (subjectId) params.subject = subjectId;
      if (topicId) params.topic = topicId;
      if (difficulty) params.difficulty = difficulty;
      if (isControversial) params.is_controversial = true;
      if (isImageBased) params.is_image_based = true;
      if (search) params.search = search;

      const res = await questionsAPI.list(params);
      setQuestions(res.data.results || res.data); // Handle both paginated and non-paginated responses
      if (res.data.count !== undefined) {
        setTotalPages(Math.max(1, Math.ceil(res.data.count / 20)));
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuestions();
  }, [page, needsReview, isDropped, examType, year, subjectId, topicId, difficulty, isControversial, isImageBased]);

  // Client-side admin gate. Backend enforces permissions; this just keeps
  // non-admins from seeing destructive affordances.
  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }
    if (!isAdmin) {
      router.replace('/dashboard');
    }
  }, [authLoading, isAuthenticated, isAdmin, router]);

  // Reset page whenever filters change so the user doesn't sit on an empty page
  const resetPage = () => setPage(1);

  const clearAllFilters = () => {
    setExamType('');
    setYear('');
    setSubjectId('');
    setTopicId('');
    setDifficulty('');
    setNeedsReview(false);
    setIsDropped(false);
    setIsControversial(false);
    setIsImageBased(false);
    setSearch('');
    resetPage();
  };

  // Exam-type chips — the primary way the user narrows the question bank.
  // Each chip shows the live count for that exam so the user can see at-a-glance
  // which track has the most content.
  const examChips: Array<{ key: string; label: string; ring: string; activeBg: string; activeText: string }> = [
    { key: '', label: 'All Exams', ring: 'ring-gray-300', activeBg: 'bg-gray-900', activeText: 'text-white' },
    { key: 'cms', label: 'UPSC CMS', ring: 'ring-blue-300', activeBg: 'bg-blue-600', activeText: 'text-white' },
    { key: 'neet_pg', label: 'NEET PG', ring: 'ring-emerald-300', activeBg: 'bg-emerald-600', activeText: 'text-white' },
    { key: 'ini_cet', label: 'INI-CET', ring: 'ring-purple-300', activeBg: 'bg-purple-600', activeText: 'text-white' },
    { key: 'usmle', label: 'USMLE', ring: 'ring-amber-300', activeBg: 'bg-amber-600', activeText: 'text-white' },
    { key: 'fmge', label: 'FMGE', ring: 'ring-rose-300', activeBg: 'bg-rose-600', activeText: 'text-white' },
  ];

  const activeFiltersCount =
    (examType ? 1 : 0) +
    (year ? 1 : 0) +
    (subjectId ? 1 : 0) +
    (topicId ? 1 : 0) +
    (difficulty ? 1 : 0) +
    (needsReview ? 1 : 0) +
    (isDropped ? 1 : 0) +
    (isControversial ? 1 : 0) +
    (isImageBased ? 1 : 0) +
    (search ? 1 : 0);

  const handleUpdate = async (id: number, field: string, value: any) => {
    try {
      // Auto-flag admin_edited = true on any edit
      await questionsAPI.update(id, { 
        [field]: value,
        admin_edited: true 
      });
      // Update local state
      setQuestions(questions.map(q => q.id === id ? { ...q, [field]: value, admin_edited: true } : q));
    } catch (error) {
      console.error(error);
      alert('Failed to update question');
      fetchQuestions(); // Revert on failure
    }
  };

  const handleDrop = async (dropIdx: number) => {
    if (draggedIdx === null || draggedIdx === dropIdx) return;

    const newQuestions = [...questions];
    const draggedItem = newQuestions[draggedIdx];
    newQuestions.splice(draggedIdx, 1);
    newQuestions.splice(dropIdx, 0, draggedItem);

    // Re-assign display numbers based on new order (simplistic approach for current page)
    const updatedQuestions = newQuestions.map((q, idx) => ({
      ...q,
      display_number: (page - 1) * 20 + idx + 1
    }));

    setQuestions(updatedQuestions);
    setDraggedIdx(null);

    // Bulk update metadata on backend
    try {
      await Promise.all(updatedQuestions.map(q =>
        questionsAPI.update(q.id, { display_number: q.display_number, admin_edited: true })
      ));
    } catch (e) {
      console.error(e);
      alert('Error updating display numbers');
      fetchQuestions();
    }
  };

  // Open the merge-duplicates dialog: fetch the cluster members so the admin
  // can confirm which siblings to soft-drop. The canonical row (lowest id, or
  // the one the script picked) stays; everything else in the cluster gets
  // is_dropped=True + is_active=False on confirm.
  const openMergeDuplicates = async (q: any) => {
    setMergeFor(q);
    setMergeCluster(null);
    setMergeDropIds([]);
    setMergeError(null);
    setMergeLoading(true);
    try {
      const res = await questionsAPI.listDuplicates(q.id);
      setMergeCluster(res.data);
      // Pre-select every member except the canonical — admin can untick if needed.
      const canonicalId: number = res.data?.canonical_id ?? q.id;
      const memberIds: number[] = (res.data?.members || [])
        .map((m: any) => m.id)
        .filter((id: number) => id !== canonicalId);
      // Belt-and-suspenders: also drop any row the backend marked canonical,
      // in case canonical_id and is_canonical diverge (asymmetric cluster).
      const finalDropIds = memberIds.filter(
        (id) => !(res.data?.members || []).some(
          (m: any) => m.id === id && m.is_canonical === true,
        ),
      );
      setMergeDropIds(finalDropIds);
    } catch (e: any) {
      console.error('Failed to load duplicates', e);
      setMergeError(
        e?.response?.data?.detail ||
          'Could not load duplicate cluster (question may not be in any cluster).'
      );
    } finally {
      setMergeLoading(false);
    }
  };

  const closeMergeDuplicates = () => {
    setMergeFor(null);
    setMergeCluster(null);
    setMergeDropIds([]);
    setMergeError(null);
  };

  const toggleMergeDrop = (id: number) => {
    setMergeDropIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const submitMergeDuplicates = async () => {
    if (!mergeFor) return;
    if (mergeDropIds.length === 0) {
      alert('Select at least one duplicate to drop.');
      return;
    }
    const confirmMsg =
      `Soft-drop ${mergeDropIds.length} duplicate question(s)? They will be hidden from ` +
      `the student app but kept in the database for audit.`;
    if (!window.confirm(confirmMsg)) return;

    setMergeSubmitting(true);
    try {
      await questionsAPI.mergeDuplicates(mergeFor.id, { duplicate_ids: mergeDropIds });
      // Refresh the list — soft-dropped rows won't show by default; if the
      // admin had "Dropped" filter on they'll still appear with is_dropped=true.
      await fetchQuestions();
      closeMergeDuplicates();
    } catch (e: any) {
      console.error('Failed to merge duplicates', e);
      setMergeError(
        e?.response?.data?.detail || 'Merge failed — check the server logs.'
      );
    } finally {
      setMergeSubmitting(false);
    }
  };

  const openRemoveForBank = (q: any) => {
    setRemoveFor(q);
    setRemoveReason('');
    setRemoveConfirmId('');
    setRemoveError(null);
  };

  const closeRemoveForBank = () => {
    setRemoveFor(null);
    setRemoveReason('');
    setRemoveConfirmId('');
    setRemoveError(null);
  };

  const submitRemoveForBank = async () => {
    if (!removeFor) return;
    if (removeConfirmId.trim() !== String(removeFor.id)) {
      setRemoveError(`Type Q${removeFor.id} exactly to confirm.`);
      return;
    }
    setRemoveSubmitting(true);
    try {
      await questionsAPI.removeFromBank(removeFor.id, { reason: removeReason });
      await fetchQuestions();
      closeRemoveForBank();
    } catch (e: any) {
      console.error('Failed to remove from bank', e);
      setRemoveError(
        e?.response?.data?.detail || 'Remove failed — check the server logs.'
      );
    } finally {
      setRemoveSubmitting(false);
    }
  };

  return (
    <div className="p-6 mx-auto space-y-6 text-gray-900 dark:text-slate-100">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Questions Editor</h1>
        <div className="text-sm text-gray-700 dark:text-slate-300">
          {examCounts[examType ?? ''] !== undefined && (
            <span>
              Showing <span className="font-semibold text-gray-900 dark:text-slate-100">{examCounts[examType ?? '']}</span>{' '}
              {examType ? examType.toUpperCase().replace('_', ' ') : 'total'} questions
              {activeFiltersCount > 0 && (
                <span className="ml-2 text-indigo-600 dark:text-indigo-400 font-medium">({activeFiltersCount} filter{activeFiltersCount > 1 ? 's' : ''} active)</span>
              )}
            </span>
          )}
        </div>
      </div>

      {/* PRIMARY FILTER: exam-type chips — the most visible thing on the page */}
      <div className="bg-white dark:bg-slate-900 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-slate-700 sticky top-0 z-10">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-gray-800 dark:text-slate-200 mr-2">Exam:</span>
          {examChips.map((chip) => {
            const count = examCounts[chip.key] ?? null;
            const isActive = examType === chip.key;
            return (
              <button
                key={chip.key}
                onClick={() => { setExamType(chip.key); resetPage(); }}
                className={
                  'inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border transition ' +
                  (isActive
                    ? `${chip.activeBg} ${chip.activeText} border-transparent shadow-sm`
                    : `bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-200 dark:border-slate-700 hover:border-gray-400 dark:hover:border-slate-500 hover:bg-gray-50 dark:hover:bg-slate-800`)
                }
                aria-pressed={isActive}
              >
                <span>{chip.label}</span>
                {count !== null && (
                  <span
                    className={
                      'inline-flex items-center justify-center min-w-7 px-1.5 py-0.5 rounded-full text-xs font-semibold ' +
                      (isActive ? 'bg-white/20 text-white' : 'bg-gray-200 dark:bg-slate-700 text-gray-800 dark:text-slate-200')
                    }
                  >
                    {count.toLocaleString()}
                  </span>
                )}
              </button>
            );
          })}
          {activeFiltersCount > 0 && (
            <button
              onClick={clearAllFilters}
              className="ml-auto text-xs text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 underline"
            >
              Clear all filters
            </button>
          )}
        </div>

        {/* SECONDARY FILTERS row — collapsed-ish so exam chips dominate visually */}
        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-gray-100 dark:border-slate-700 pt-3">
          <input
            type="text"
            placeholder="Search questions..."
            className="border border-gray-300 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 placeholder-gray-400 dark:placeholder-slate-500 p-2 rounded w-64"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (resetPage(), fetchQuestions())}
          />

          <select
            className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-2 rounded min-w-40"
            value={subjectId}
            onChange={(e) => { setSubjectId(e.target.value); setTopicId(''); resetPage(); }}
          >
            <option value="">All Subjects</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          <select
            className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-2 rounded min-w-40 disabled:bg-gray-100 dark:disabled:bg-slate-800 disabled:text-gray-500 dark:disabled:text-slate-500"
            value={topicId}
            onChange={(e) => { setTopicId(e.target.value); resetPage(); }}
            disabled={!subjectId}
          >
            <option value="">All Topics</option>
            {topics
              .filter((t) => !subjectId || String(t.subject) === String(subjectId))
              .map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
          </select>

          <select
            className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-2 rounded"
            value={year}
            onChange={(e) => { setYear(e.target.value); resetPage(); }}
          >
            <option value="">All Years</option>
            {Array.from({ length: 30 }, (_, i) => 2025 - i).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>

          <select
            className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-2 rounded"
            value={difficulty}
            onChange={(e) => { setDifficulty(e.target.value); resetPage(); }}
          >
            <option value="">Any Difficulty</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>

          <div className="flex flex-wrap items-center gap-3 ml-2">
            <label className="flex items-center gap-1 text-sm text-gray-900 dark:text-slate-100">
              <input
                type="checkbox"
                className="accent-indigo-600"
                checked={needsReview}
                onChange={(e) => { setNeedsReview(e.target.checked); resetPage(); }}
              />
              Needs Review
            </label>
            <label className="flex items-center gap-1 text-sm text-gray-900 dark:text-slate-100">
              <input
                type="checkbox"
                className="accent-indigo-600"
                checked={isDropped}
                onChange={(e) => { setIsDropped(e.target.checked); resetPage(); }}
              />
              Dropped
            </label>
            <label className="flex items-center gap-1 text-sm text-gray-900 dark:text-slate-100">
              <input
                type="checkbox"
                className="accent-indigo-600"
                checked={isControversial}
                onChange={(e) => { setIsControversial(e.target.checked); resetPage(); }}
              />
              Controversial
            </label>
            <label className="flex items-center gap-1 text-sm text-gray-900 dark:text-slate-100">
              <input
                type="checkbox"
                className="accent-indigo-600"
                checked={isImageBased}
                onChange={(e) => { setIsImageBased(e.target.checked); resetPage(); }}
              />
              Image-based
            </label>
          </div>

          <button
            onClick={() => { resetPage(); fetchQuestions(); }}
            className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
          >
            Search
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-sm border border-gray-200 dark:border-slate-700 overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 dark:bg-slate-800">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-slate-300 uppercase tracking-wider">ID / UUID</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-slate-300 uppercase tracking-wider">Disp # (Drag)</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-slate-300 uppercase tracking-wider">Subject & Topic</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-slate-300 uppercase tracking-wider">Text</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-slate-300 uppercase tracking-wider">Flags</th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-slate-300 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-slate-900 divide-y divide-gray-200 dark:divide-slate-700">
            {loading ? (
              <tr><td colSpan={6} className="text-center py-4 text-gray-900 dark:text-slate-100">Loading...</td></tr>
            ) : questions.map((q, idx) => (
              <tr
                key={q.id}
                draggable
                onDragStart={() => setDraggedIdx(idx)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => handleDrop(idx)}
                className={draggedIdx === idx ? "opacity-50 bg-gray-100 dark:bg-slate-700" : "hover:bg-gray-50 dark:hover:bg-slate-800 cursor-move transition-colors"}
              >
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100">
                  {q.id}<br/>
                  <span className="text-xs text-gray-500 dark:text-slate-400">{q.uuid ? q.uuid.substring(0,8)+'...' : 'N/A'}</span>
                  {q.duplicate_count > 1 && (
                    <div className="mt-1">
                      <button
                        onClick={() => openMergeDuplicates(q)}
                        className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-300 border border-orange-300 dark:border-orange-800 px-1.5 py-0.5 rounded hover:bg-orange-200 dark:hover:bg-orange-900/60 hover:border-orange-400"
                        title={`This question has ${q.duplicate_count} identical rows in the database. Click to review & merge.`}
                      >
                        ⚠ Duplicate ×{q.duplicate_count}
                      </button>
                    </div>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 dark:text-slate-400 cursor-grab">⣿</span>
                    <input
                      type="number"
                      className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-1 w-16 text-center rounded"
                      defaultValue={q.display_number || ''}
                      onBlur={(e) => {
                        if (e.target.value !== String(q.display_number)) {
                          handleUpdate(q.id, 'display_number', parseInt(e.target.value) || null);
                        }
                      }}
                    />
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-900 dark:text-slate-100 min-w-50">
                  <div className="space-y-2">
                    <select
                      className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-1 w-full rounded text-xs"
                      value={q.subject || ''}
                      onChange={(e) => handleUpdate(q.id, 'subject', parseInt(e.target.value))}
                    >
                      <option value="">No Subject</option>
                      {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                    <select
                      className="border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 p-1 w-full rounded text-xs"
                      value={q.topic || ''}
                      onChange={(e) => handleUpdate(q.id, 'topic', parseInt(e.target.value))}
                    >
                      <option value="">No Topic</option>
                      {topics.filter(t => t.subject === q.subject).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-900 dark:text-slate-100 min-w-75 whitespace-normal wrap-break-word max-h-32 overflow-hidden">
                  <div className="line-clamp-3">{q.question_text}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100 space-y-2">
                  <label className="flex items-center gap-2 text-xs text-gray-900 dark:text-slate-100">
                    <input type="checkbox" className="accent-emerald-600" checked={q.needs_review || false} onChange={(e) => handleUpdate(q.id, 'needs_review', e.target.checked)} />
                    Needs Review
                  </label>
                  <label className="flex items-center gap-2 text-xs text-gray-900 dark:text-slate-100">
                    <input type="checkbox" className="accent-emerald-600" checked={q.is_dropped || false} onChange={(e) => handleUpdate(q.id, 'is_dropped', e.target.checked)} />
                    Dropped
                  </label>
                  <div className="text-xs mt-1 text-gray-900 dark:text-slate-100">
                    Edited: {q.admin_edited ? <span className="text-green-700 dark:text-green-400 font-bold">Yes</span> : <span className="text-gray-500 dark:text-slate-400">No</span>}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                  <button
                    onClick={() => onEdit(q)}
                    className="text-emerald-700 hover:text-emerald-900 bg-emerald-50 dark:bg-emerald-900/30 dark:text-emerald-300 dark:hover:text-emerald-100 border border-emerald-200 dark:border-emerald-800 px-3 py-1 rounded"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => openRemoveForBank(q)}
                    className="text-red-700 hover:text-red-900 bg-red-50 dark:bg-red-900/30 dark:text-red-300 dark:hover:text-red-100 border border-red-200 dark:border-red-800 px-3 py-1 rounded font-semibold"
                    title="Remove from question bank (soft-delete; survives deploys via RemovedQuestion skip-list)"
                  >
                    Remove
                  </button>
                  {q.duplicate_count > 1 ? (
                    <button
                      onClick={() => openMergeDuplicates(q)}
                      className="text-orange-800 hover:text-orange-900 bg-orange-100 dark:bg-orange-900/30 dark:text-orange-300 dark:hover:text-orange-100 border border-orange-300 dark:border-orange-800 px-3 py-1 rounded font-semibold"
                      title={`${q.duplicate_count} identical copies detected — review & merge`}
                    >
                      Merge Duplicates
                    </button>
                  ) : (
                    <button
                      onClick={() => alert('Merge/Split feature coming soon!')}
                      className="text-indigo-700 hover:text-indigo-900 bg-indigo-50 dark:bg-indigo-900/30 dark:text-indigo-300 dark:hover:text-indigo-100 border border-indigo-200 dark:border-indigo-800 px-3 py-1 rounded"
                    >
                      Merge / Split
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center bg-white dark:bg-slate-900 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-slate-700">
        <button
          disabled={page === 1}
          onClick={() => setPage(p => Math.max(1, p - 1))}
          className="px-4 py-2 border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded disabled:opacity-50 disabled:text-gray-400 dark:disabled:text-slate-600"
        >
          Previous
        </button>
        <span className="text-gray-900 dark:text-slate-100">Page {page} of {totalPages}</span>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage(p => p + 1)}
          className="px-4 py-2 border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded disabled:opacity-50 disabled:text-gray-400 dark:disabled:text-slate-600"
        >
          Next
        </button>
      </div>

      {editing && (
        <QuestionEditModal
          question={editing}
          images={editing.images ?? []}
          onClose={() => setEditing(null)}
          onSaved={(updated: any) => {
            setQuestions(questions.map((q) => (q.id === updated.id ? updated : q)));
            setEditing(null);
          }}
        />
      )}

      {/* Merge Duplicates modal (Bug 4) — list sibling questions and confirm
          which ones to soft-drop (is_dropped=True, is_active=False). */}
      {mergeFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white dark:bg-slate-900 rounded-lg shadow-xl border border-gray-200 dark:border-slate-700 w-full max-w-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-slate-700">
              <h2 className="text-lg font-bold text-gray-900 dark:text-slate-100">
                Merge Duplicates — Q{mergeFor.id}
              </h2>
              <button
                onClick={closeMergeDuplicates}
                className="text-gray-500 hover:text-gray-900 dark:text-slate-400 dark:hover:text-slate-100 text-2xl leading-none"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-4 overflow-y-auto flex-1">
              {mergeLoading ? (
                <div className="text-gray-700 dark:text-slate-300 py-6 text-center">Loading cluster…</div>
              ) : mergeError ? (
                <div className="text-red-700 bg-red-50 border border-red-200 rounded p-3">
                  {mergeError}
                </div>
              ) : !mergeCluster || !(mergeCluster.members || []).length ? (
                <div className="text-gray-700 dark:text-slate-300 py-6 text-center">
                  Q{mergeFor.id} is not part of any duplicate cluster.
                </div>
              ) : (
                <>
                  <p className="text-sm text-gray-700 dark:text-slate-300 mb-3">
                    Canonical (will be kept):{' '}
                    <span className="font-semibold">
                      Q{mergeCluster.canonical_id ?? mergeFor.id}
                    </span>
                    . Other members below will be{' '}
                    <span className="font-semibold text-orange-800">
                      soft-dropped
                    </span>{' '}
                    (hidden from students, kept in DB for audit). Untick any you
                    want to keep.
                  </p>
                  <div className="space-y-2">
                    {(mergeCluster.members || []).map((m: any) => {
                      const qid: number = m.id;
                      const isCanonical: boolean =
                        m.is_canonical ?? (mergeCluster.canonical_id ?? mergeFor.id) === qid;
                      return (
                        <label
                          key={qid}
                          className={
                            'flex items-start gap-3 p-3 rounded border ' +
                            (isCanonical
                              ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/30'
                              : 'border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800 cursor-pointer')
                          }
                        >
                          <input
                            type="checkbox"
                            className="accent-orange-600 mt-1"
                            checked={isCanonical ? true : mergeDropIds.includes(qid)}
                            disabled={isCanonical}
                            onChange={() => toggleMergeDrop(qid)}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-sm font-semibold">
                                Q{qid}
                              </span>
                              {isCanonical && (
                                <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-200 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100 px-1.5 py-0.5 rounded">
                                  Canonical (keep)
                                </span>
                              )}
                              {m.subject_name && (
                                <span className="text-[10px] text-gray-600 dark:text-slate-300 bg-gray-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                                  {m.subject_name}
                                </span>
                              )}
                              {m.year && (
                                <span className="text-[10px] text-gray-600 dark:text-slate-300 bg-gray-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                                  {m.year}
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-gray-700 dark:text-slate-300 mt-1 line-clamp-2">
                              {m.question_text_preview ?? '(no preview)'}
                            </div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            <div className="px-6 py-4 border-t border-gray-200 dark:border-slate-700 flex items-center justify-between gap-3">
              <span className="text-sm text-gray-700 dark:text-slate-300">
                {mergeDropIds.length > 0 ? (
                  <>
                    Will soft-drop{' '}
                    <span className="font-semibold text-orange-800">
                      {mergeDropIds.length}
                    </span>{' '}
                    duplicate(s).
                  </>
                ) : (
                  'No duplicates selected.'
                )}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={closeMergeDuplicates}
                  className="px-4 py-2 border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded hover:bg-gray-50"
                  disabled={mergeSubmitting}
                >
                  Cancel
                </button>
                <button
                  onClick={submitMergeDuplicates}
                  disabled={
                    mergeSubmitting ||
                    mergeLoading ||
                    mergeDropIds.length === 0
                  }
                  className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50"
                >
                  {mergeSubmitting ? 'Merging…' : 'Soft-drop selected'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Remove from bank modal (durable soft-delete). Captures the row's
          stem hash in RemovedQuestion so the next import_neet_pg /
          load_exam_fixture deploy won't re-create it. */}
      {removeFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white dark:bg-slate-900 rounded-lg shadow-xl border border-red-200 dark:border-red-800 w-full max-w-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-red-200 dark:border-red-800">
              <h2 className="text-lg font-bold text-red-900 dark:text-red-300">
                Remove from bank — Q{removeFor.id}
              </h2>
              <button
                onClick={closeRemoveForBank}
                className="text-gray-500 hover:text-gray-900 dark:text-slate-400 dark:hover:text-slate-100 text-2xl leading-none"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-4 overflow-y-auto flex-1 space-y-4">
              <p className="text-sm text-gray-700 dark:text-slate-300">
                You are about to remove the following question from the bank.
                It will be hidden from the student app immediately, and the
                next <code>import_neet_pg</code> / <code>load_exam_fixture</code>
                {' '}deploy will skip re-creating it.
              </p>

              <div className="bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded p-3 text-sm text-gray-800 dark:text-slate-200 max-h-32 overflow-y-auto">
                {(removeFor.question_text || removeFor.text || '').slice(0, 320) || (
                  <span className="italic text-gray-500 dark:text-slate-400">
                    (no preview available)
                  </span>
                )}
              </div>

              <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded p-3 text-xs text-red-800 dark:text-red-200">
                <strong>Destructive.</strong> Existing user history
                (bookmarks, attempts, notes, discussions) keeps referencing
                this row, but the question will no longer appear in any
                practice or test view. Use the matching "Restore" endpoint
                if you change your mind.
              </div>

              {removeError && (
                <div className="text-red-700 bg-red-50 border border-red-200 rounded p-3 text-sm">
                  {removeError}
                </div>
              )}

              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-slate-300 mb-1">
                  Reason (optional)
                </label>
                <textarea
                  className="w-full border border-gray-300 dark:border-slate-700 rounded p-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100"
                  rows={2}
                  value={removeReason}
                  onChange={(e) => setRemoveReason(e.target.value)}
                  placeholder="e.g. duplicate of Q9713, wrong answer key"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-slate-300 mb-1">
                  Type <code className="bg-gray-100 dark:bg-slate-800 px-1 rounded text-gray-900 dark:text-slate-100">Q{removeFor.id}</code> to confirm
                </label>
                <input
                  type="text"
                  className="w-full border border-gray-300 dark:border-slate-700 rounded p-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-red-500 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100"
                  value={removeConfirmId}
                  onChange={(e) => setRemoveConfirmId(e.target.value)}
                  placeholder={`Q${removeFor.id}`}
                  autoFocus
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30">
              <button
                onClick={closeRemoveForBank}
                className="px-4 py-2 border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded hover:bg-gray-50"
                disabled={removeSubmitting}
              >
                Cancel
              </button>
              <button
                onClick={submitRemoveForBank}
                disabled={
                  removeSubmitting || removeConfirmId.trim() !== String(removeFor.id)
                }
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
              >
                {removeSubmitting ? 'Removing…' : 'Remove from bank'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
