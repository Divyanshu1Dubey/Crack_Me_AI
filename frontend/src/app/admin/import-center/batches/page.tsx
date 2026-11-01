// /admin/import-center/batches — paginated list of every import batch.
// The API pages by 20 (DRF PageNumberPagination: count / next / results).

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { importCenterAPI } from '@/lib/api';

type Batch = {
  id: number;
  status: string;
  source_label: string;
  total_files: number;
  files_processed: number;
  files_failed: number;
  questions_extracted: number;
  questions_found: number;
  questions_rejected: number;
  duplicates_skipped: number;
  images_extracted: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  materials_count: number;
  needs_review_count: number;
};

const STATUS_COLORS: Record<string, string> = {
  queued: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-300',
  processing: 'bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300',
  completed: 'bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300',
  partial: 'bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300',
  failed: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-500/20 dark:text-gray-300',
};

const PAGE_SIZE = 20;

export default function BatchesListPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string>('');
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = { page, page_size: PAGE_SIZE };
        if (status) params.status = status;
        const r = await importCenterAPI.listBatches(params);
        const data = r.data;
        const list = Array.isArray(data) ? data : data.results || [];
        if (mounted) {
          setBatches(list);
          setCount(Array.isArray(data) ? list.length : data.count ?? list.length);
        }
      } catch {
        if (mounted) {
          setBatches([]);
          setCount(0);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [status, page]);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-bold">Import Batches</h2>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by status"
          className="rounded border border-border bg-background px-3 py-1.5 text-sm"
        >
          <option value="">All statuses</option>
          <option value="queued">Queued</option>
          <option value="processing">Processing</option>
          <option value="completed">Completed</option>
          <option value="partial">Partial</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </header>

      <section className="rounded border border-border bg-card p-4">
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : batches.length === 0 ? (
          <div className="text-sm text-muted-foreground">No batches match this filter.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm [&_td]:px-3 [&_th]:px-3">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-2">ID</th>
                  <th className="py-2">Source</th>
                  <th className="py-2">Status</th>
                  <th className="py-2 text-right">Files</th>
                  <th className="py-2 text-right">Found</th>
                  <th className="py-2 text-right">Imported</th>
                  <th className="py-2 text-right">Dupes</th>
                  <th className="py-2 text-right">Review</th>
                  <th className="py-2 text-right">Images</th>
                  <th className="py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id} className="border-b last:border-0">
                    <td className="py-2">
                      <Link href={`/admin/import-center/batches/${b.id}`} className="text-primary hover:underline">
                        #{b.id}
                      </Link>
                    </td>
                    <td className="py-2 max-w-xs truncate">{b.source_label}</td>
                    <td className="py-2">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[b.status] || STATUS_COLORS.queued}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      {b.files_processed}/{b.total_files}
                    </td>
                    <td className="py-2 text-right">{b.questions_found}</td>
                    <td className="py-2 text-right">{b.questions_extracted}</td>
                    <td className="py-2 text-right">{b.duplicates_skipped}</td>
                    <td className="py-2 text-right">{b.needs_review_count}</td>
                    <td className="py-2 text-right">{b.images_extracted}</td>
                    <td className="py-2 text-xs text-muted-foreground">{new Date(b.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {count > PAGE_SIZE && (
          <div className="mt-3 flex items-center justify-between text-xs">
            <span>
              {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, count)} of {count}
            </span>
            <div className="flex gap-1">
              <button
                type="button"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => p - 1)}
                className="rounded border border-border px-2 py-1 disabled:opacity-50"
              >
                ‹ Prev
              </button>
              <button
                type="button"
                disabled={page * PAGE_SIZE >= count || loading}
                onClick={() => setPage((p) => p + 1)}
                className="rounded border border-border px-2 py-1 disabled:opacity-50"
              >
                Next ›
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}