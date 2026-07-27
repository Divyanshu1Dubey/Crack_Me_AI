// /admin/import-center/batches — paginated list of every import batch.

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
  queued: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  partial: 'bg-orange-100 text-orange-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

export default function BatchesListPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string>('');

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const params: Record<string, string> = {};
        if (status) params.status = status;
        const r = await importCenterAPI.listBatches(params);
        const data = r.data;
        const list = Array.isArray(data) ? data : data.results || [];
        if (mounted) setBatches(list);
      } catch {
        if (mounted) setBatches([]);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [status]);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Import Batches</h2>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
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
            <table className="w-full text-sm">
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
      </section>
    </div>
  );
}