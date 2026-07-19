'use client';

import React, { useState, useEffect } from 'react';
import { questionsAPI } from '@/lib/api';

export default function AdminQuestionsEditorPage() {
  const [questions, setQuestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // Filters
  const [needsReview, setNeedsReview] = useState(false);
  const [isDropped, setIsDropped] = useState(false);
  const [search, setSearch] = useState('');
  
  // Drag and drop state
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);

  // Subjects and Topics for inline editing
  const [subjects, setSubjects] = useState<any[]>([]);
  const [topics, setTopics] = useState<any[]>([]);

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

  useEffect(() => {
    fetchTaxonomy();
  }, []);

  const fetchQuestions = async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 20, ordering: 'display_number' };
      if (needsReview) params.needs_review = true;
      if (isDropped) params.is_dropped = true;
      if (search) params.search = search;
      
      const res = await questionsAPI.list(params);
      setQuestions(res.data.results || res.data); // Handle both paginated and non-paginated responses
      if (res.data.count) {
        setTotalPages(Math.ceil(res.data.count / 20));
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuestions();
  }, [page, needsReview, isDropped]);

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

  return (
    <div className="p-6 mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Questions Editor</h1>
      </div>
      
      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 flex gap-4 items-center">
        <input 
          type="text" 
          placeholder="Search questions..." 
          className="border p-2 rounded w-64"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetchQuestions()}
        />
        <label className="flex items-center gap-2">
          <input 
            type="checkbox" 
            checked={needsReview}
            onChange={(e) => { setNeedsReview(e.target.checked); setPage(1); }}
          />
          Needs Review
        </label>
        <label className="flex items-center gap-2">
          <input 
            type="checkbox" 
            checked={isDropped}
            onChange={(e) => { setIsDropped(e.target.checked); setPage(1); }}
          />
          Is Dropped
        </label>
        <button onClick={fetchQuestions} className="bg-indigo-600 text-white px-4 py-2 rounded">
          Search
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID / UUID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Disp # (Drag)</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subject & Topic</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Text</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Flags</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr><td colSpan={6} className="text-center py-4">Loading...</td></tr>
            ) : questions.map((q, idx) => (
              <tr 
                key={q.id}
                draggable
                onDragStart={() => setDraggedIdx(idx)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => handleDrop(idx)}
                className={draggedIdx === idx ? "opacity-50 bg-gray-100" : "hover:bg-gray-50 cursor-move transition-colors"}
              >
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {q.id}<br/>
                  <span className="text-xs text-gray-400">{q.uuid ? q.uuid.substring(0,8)+'...' : 'N/A'}</span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 cursor-grab">⣿</span>
                    <input 
                      type="number" 
                      className="border p-1 w-16 text-center rounded bg-white" 
                      defaultValue={q.display_number || ''}
                      onBlur={(e) => {
                        if (e.target.value !== String(q.display_number)) {
                          handleUpdate(q.id, 'display_number', parseInt(e.target.value) || null);
                        }
                      }}
                    />
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-900 min-w-[200px]">
                  <div className="space-y-2">
                    <select 
                      className="border p-1 w-full rounded text-xs"
                      value={q.subject || ''}
                      onChange={(e) => handleUpdate(q.id, 'subject', parseInt(e.target.value))}
                    >
                      <option value="">No Subject</option>
                      {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                    <select 
                      className="border p-1 w-full rounded text-xs"
                      value={q.topic || ''}
                      onChange={(e) => handleUpdate(q.id, 'topic', parseInt(e.target.value))}
                    >
                      <option value="">No Topic</option>
                      {topics.filter(t => t.subject === q.subject).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-900 min-w-[300px] whitespace-normal break-words max-h-32 overflow-hidden">
                  <div className="line-clamp-3">{q.question_text}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 space-y-2">
                  <label className="flex items-center gap-2 text-xs">
                    <input type="checkbox" checked={q.needs_review || false} onChange={(e) => handleUpdate(q.id, 'needs_review', e.target.checked)} />
                    Needs Review
                  </label>
                  <label className="flex items-center gap-2 text-xs">
                    <input type="checkbox" checked={q.is_dropped || false} onChange={(e) => handleUpdate(q.id, 'is_dropped', e.target.checked)} />
                    Dropped
                  </label>
                  <div className="text-xs mt-1">
                    Edited: {q.admin_edited ? <span className="text-green-600 font-bold">Yes</span> : <span className="text-gray-400">No</span>}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <button onClick={() => alert('Merge/Split feature coming soon!')} className="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded">
                    Merge / Split
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <button 
          disabled={page === 1} 
          onClick={() => setPage(p => Math.max(1, p - 1))}
          className="px-4 py-2 border rounded disabled:opacity-50"
        >
          Previous
        </button>
        <span>Page {page} of {totalPages}</span>
        <button 
          disabled={page >= totalPages} 
          onClick={() => setPage(p => p + 1)}
          className="px-4 py-2 border rounded disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
