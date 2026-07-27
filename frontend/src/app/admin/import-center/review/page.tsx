// /admin/import-center/review — review queue for extracted questions.
// Bulk approve / reject + per-row decisions + inline preview drawer.

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { importCenterAPI } from '@/lib/api';

type Question = {
  id: number;
  material: number;
  material_filename: string;
  position_index: number;
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_answer: string;
  status: string;
  inferred_subject: string;
  inferred_topic: string;
  inferred_difficulty: string;
  classification_confidence: number;
  needs_review_marker: boolean;
  image_count: number;
  created_at: string;
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  published: 'bg-blue-100 text-blue-800',
  duplicate: 'bg-gray-100 text-gray-800',
  needs_review: 'bg-orange-100 text-orange-800',
};

export default function ReviewQueuePage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('needs_review');
  const [batchFilter, setBatchFilter] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkPending, setBulkPending] = useState(false);
  const [previewId, setPreviewId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [total, setTotal] = useState(0);

  const load = async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: pageSize };
      if (statusFilter) params.status = statusFilter;
      if (batchFilter) params.batch = batchFilter;
      const r = await importCenterAPI.listQuestions(params);
      const data = r.data;
      const list = Array.isArray(data) ? data : data.results || [];
      const count = Array.isArray(data) ? data.length : data.count || list.length;
      setQuestions(list);
      setTotal(count);
    } catch {
      setQuestions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, batchFilter, page]);

  const toggleSelect = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selectAll = () => {
    if (selected.size === questions.length) setSelected(new Set());
    else setSelected(new Set(questions.map((q) => q.id)));
  };

  const bulk = async (decision: 'approve' | 'reject' | 'reset') => {
    if (!selected.size) return;
    setBulkPending(true);
    try {
      await importCenterAPI.bulkDecide(Array.from(selected), decision);
      setSelected(new Set());
      load();
    } finally {
      setBulkPending(false);
    }
  };

  const decideOne = async (id: number, decision: 'approve' | 'reject' | 'reset') => {
    await importCenterAPI.decideQuestion(id, decision);
    load();
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-xl font-bold">Review Queue</h2>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="rounded border border-border bg-background px-3 py-1.5 text-sm">
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="needs_review">Needs Review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="published">Published</option>
          <option value="duplicate">Duplicate</option>
        </select>
        <input
          type="number"
          value={batchFilter}
          onChange={(e) => { setBatchFilter(e.target.value); setPage(1); }}
          placeholder="Batch #"
          className="w-28 rounded border border-border bg-background px-3 py-1.5 text-sm"
        />
      </header>

      {selected.size > 0 && (
        <div className="flex items-center gap-2 rounded border border-primary bg-primary/10 p-3">
          <span className="text-sm font-medium">{selected.size} selected</span>
          <button type="button" onClick={() => bulk('approve')} disabled={bulkPending} className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white disabled:opacity-50">
            Approve
          </button>
          <button type="button" onClick={() => bulk('reject')} disabled={bulkPending} className="rounded bg-red-600 px-3 py-1 text-xs font-medium text-white disabled:opacity-50">
            Reject
          </button>
          <button type="button" onClick={() => bulk('reset')} disabled={bulkPending} className="rounded border border-border px-3 py-1 text-xs">
            Reset
          </button>
          <button type="button" onClick={() => setSelected(new Set())} className="ml-auto text-xs text-muted-foreground hover:text-foreground">
            Clear
          </button>
        </div>
      )}

      <section className="rounded border border-border bg-card p-4">
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : questions.length === 0 ? (
          <div className="text-sm text-muted-foreground">No questions match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-2 w-8">
                    <input type="checkbox" checked={selected.size === questions.length && questions.length > 0} onChange={selectAll} />
                  </th>
                  <th className="py-2">Q</th>
                  <th className="py-2">Source</th>
                  <th className="py-2">Subject → Topic</th>
                  <th className="py-2 text-center">Answer</th>
                  <th className="py-2 text-center">Conf.</th>
                  <th className="py-2">Status</th>
                  <th className="py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.id} className="border-b last:border-0 hover:bg-accent/40">
                    <td className="py-2">
                      <input type="checkbox" checked={selected.has(q.id)} onChange={() => toggleSelect(q.id)} />
                    </td>
                    <td className="py-2 max-w-md">
                      <button type="button" onClick={() => setPreviewId(q.id)} className="line-clamp-2 text-left hover:text-primary">
                        {q.question_text.slice(0, 140)}{q.question_text.length > 140 ? '…' : ''}
                      </button>
                      {q.image_count > 0 && <span className="ml-1 text-xs">🖼️ {q.image_count}</span>}
                    </td>
                    <td className="py-2 text-xs">
                      <Link href={`/admin/import-center/batches/${q.material}`} className="hover:underline">
                        #{q.material}
                      </Link>
                      <div className="truncate text-muted-foreground" title={q.material_filename}>{q.material_filename}</div>
                    </td>
                    <td className="py-2 text-xs">
                      <div>{q.inferred_subject || '—'}</div>
                      <div className="text-muted-foreground">{q.inferred_topic || '—'}</div>
                    </td>
                    <td className="py-2 text-center font-bold">{q.correct_answer || '?'}</td>
                    <td className="py-2 text-center text-xs">{(q.classification_confidence * 100).toFixed(0)}%</td>
                    <td className="py-2">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[q.status]}`}>{q.status}</span>
                    </td>
                    <td className="py-2 text-right">
                      <div className="flex justify-end gap-1">
                        <button type="button" title="Approve" onClick={() => decideOne(q.id, 'approve')} className="rounded border border-green-300 px-2 py-0.5 text-xs text-green-700 hover:bg-green-50">✓</button>
                        <button type="button" title="Reject" onClick={() => decideOne(q.id, 'reject')} className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-700 hover:bg-red-50">✕</button>
                        <button type="button" title="Reset" onClick={() => decideOne(q.id, 'reset')} className="rounded border border-border px-2 py-0.5 text-xs">↺</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > pageSize && (
          <div className="mt-3 flex items-center justify-between text-xs">
            <span>{(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}</span>
            <div className="flex gap-1">
              <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded border border-border px-2 py-1 disabled:opacity-50">‹ Prev</button>
              <button type="button" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)} className="rounded border border-border px-2 py-1 disabled:opacity-50">Next ›</button>
            </div>
          </div>
        )}
      </section>

      {previewId && <PreviewDrawer id={previewId} onClose={() => setPreviewId(null)} onDecide={decideOne} />}
    </div>
  );
}

function PreviewDrawer({ id, onClose, onDecide }: { id: number; onClose: () => void; onDecide: (id: number, d: 'approve' | 'reject' | 'reset') => void }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    let mounted = true;
    importCenterAPI.getQuestion(id).then((r) => { if (mounted) setData(r.data); }).catch(() => { if (mounted) setData(null); });
    return () => { mounted = false; };
  }, [id]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-2xl overflow-y-auto bg-card p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        {!data ? (
          <div className="text-muted-foreground">Loading…</div>
        ) : (
          <div className="space-y-4">
            <header className="flex items-start justify-between gap-2">
              <h3 className="text-lg font-semibold">Question #{data.id}</h3>
              <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">✕</button>
            </header>
            <div>
              <h4 className="text-xs uppercase text-muted-foreground">Question</h4>
              <p className="mt-1 whitespace-pre-wrap text-sm">{data.question_text}</p>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {(['a', 'b', 'c', 'd'] as const).map((opt) => {
                const text = (data as any)[`option_${opt}`];
                if (!text) return null;
                const isCorrect = data.correct_answer?.toUpperCase() === opt.toUpperCase();
                return (
                  <div key={opt} className={`rounded border p-2 text-sm ${isCorrect ? 'border-green-500 bg-green-50' : 'border-border'}`}>
                    <span className="font-bold uppercase">{opt}.</span> {text}
                    {isCorrect && <span className="ml-1 text-xs text-green-700">✓ correct</span>}
                  </div>
                );
              })}
            </div>
            {data.explanation && (
              <div>
                <h4 className="text-xs uppercase text-muted-foreground">Explanation</h4>
                <p className="mt-1 whitespace-pre-wrap text-sm">{data.explanation}</p>
              </div>
            )}
            <div className="flex gap-2">
              <button type="button" onClick={() => { onDecide(id, 'approve'); onClose(); }} className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white">Approve</button>
              <button type="button" onClick={() => { onDecide(id, 'reject'); onClose(); }} className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white">Reject</button>
              <button type="button" onClick={() => { onDecide(id, 'reset'); onClose(); }} className="rounded border border-border px-3 py-1.5 text-sm">Reset</button>
              <button type="button" onClick={() => importCenterAPI.classifyQuestion(id).then(() => importCenterAPI.getQuestion(id)).then((r) => setData(r.data))} className="ml-auto rounded border border-border px-3 py-1.5 text-sm">
                🧠 Re-classify
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}