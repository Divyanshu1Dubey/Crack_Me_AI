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

  const fetchQuestions = async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 20 };
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
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Disp #</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Text</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Review?</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Dropped?</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Admin Edited</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr><td colSpan={6} className="text-center py-4">Loading...</td></tr>
            ) : questions.map((q) => (
              <tr key={q.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {q.id}<br/>
                  <span className="text-xs text-gray-400">{q.uuid ? q.uuid.substring(0,8)+'...' : 'N/A'}</span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  <input 
                    type="number" 
                    className="border p-1 w-16" 
                    defaultValue={q.display_number || ''}
                    onBlur={(e) => {
                      if (e.target.value !== String(q.display_number)) {
                        handleUpdate(q.id, 'display_number', e.target.value || null);
                      }
                    }}
                  />
                </td>
                <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                  {q.question_text}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  <input 
                    type="checkbox" 
                    checked={q.needs_review || false}
                    onChange={(e) => handleUpdate(q.id, 'needs_review', e.target.checked)}
                  />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  <input 
                    type="checkbox" 
                    checked={q.is_dropped || false}
                    onChange={(e) => handleUpdate(q.id, 'is_dropped', e.target.checked)}
                  />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {q.admin_edited ? <span className="text-green-600 font-bold">Yes</span> : <span className="text-gray-400">No</span>}
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
