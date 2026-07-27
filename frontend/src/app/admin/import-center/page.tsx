// /admin/import-center — landing page.
// Top-of-page analytics tiles + recent uploads + quick actions.

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { importCenterAPI } from '@/lib/api';

type Dashboard = {
  total_batches: number;
  total_questions_imported: number;
  total_questions_published: number;
  total_needs_review: number;
  duplicate_rate: number;
  image_questions: number;
  subjects_count: number;
  topics_count: number;
  pending_reviews: number;
  recent_uploads: Array<{
    batch_id: number;
    source_label: string;
    status: string;
    questions_extracted: number;
    created_at: string;
    created_by: string | null;
  }>;
};

const STATUS_COLORS: Record<string, string> = {
  queued: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  partial: 'bg-orange-100 text-orange-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

export default function ImportCenterHome() {
  const [stats, setStats] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const r = await importCenterAPI.dashboard();
        if (mounted) setStats(r.data);
      } catch (e: any) {
        if (mounted) setError(e?.response?.data?.error || e?.message || 'Failed to load dashboard');
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return <div className="text-muted-foreground">Loading dashboard…</div>;
  }
  if (error) {
    return (
      <div className="rounded border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        {error}
      </div>
    );
  }
  if (!stats) return null;

  return (
    <div className="space-y-8">
      <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Tile label="Total Batches" value={stats.total_batches} />
        <Tile label="Questions Imported" value={stats.total_questions_imported} accent="text-blue-600" />
        <Tile label="Published" value={stats.total_questions_published} accent="text-green-600" />
        <Tile label="Needs Review" value={stats.total_needs_review} accent="text-orange-600" />
        <Tile label="Duplicate Rate" value={`${(stats.duplicate_rate * 100).toFixed(1)}%`} accent="text-purple-600" />
        <Tile label="Image Questions" value={stats.image_questions} />
        <Tile label="Subjects" value={stats.subjects_count} />
        <Tile label="Pending Reviews" value={stats.pending_reviews} accent="text-rose-600" />
      </section>

      <section className="rounded border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Quick Actions</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/admin/import-center/upload"
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            📤 Upload Files
          </Link>
          <Link
            href="/admin/import-center/review"
            className="rounded border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            ✅ Review Queue ({stats.pending_reviews})
          </Link>
          <Link
            href="/admin/import-center/batches"
            className="rounded border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            📦 All Batches
          </Link>
          <Link
            href="/admin/import-center/search"
            className="rounded border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            🔍 Search
          </Link>
        </div>
      </section>

      <section className="rounded border border-border bg-card p-4">
        <h2 className="mb-3 text-lg font-semibold">Recent Uploads</h2>
        {stats.recent_uploads.length === 0 ? (
          <div className="text-sm text-muted-foreground">No uploads yet — start by uploading a DOCX file.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-2">Batch</th>
                  <th className="py-2">Source</th>
                  <th className="py-2">Status</th>
                  <th className="py-2 text-right">Questions</th>
                  <th className="py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_uploads.map((u) => (
                  <tr key={u.batch_id} className="border-b last:border-0">
                    <td className="py-2">
                      <Link href={`/admin/import-center/batches/${u.batch_id}`} className="text-primary hover:underline">
                        #{u.batch_id}
                      </Link>
                    </td>
                    <td className="py-2">{u.source_label}</td>
                    <td className="py-2">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[u.status] || STATUS_COLORS.queued}`}>
                        {u.status}
                      </span>
                    </td>
                    <td className="py-2 text-right">{u.questions_extracted}</td>
                    <td className="py-2 text-muted-foreground">{new Date(u.created_at).toLocaleString()}</td>
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

function Tile({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded border border-border bg-card p-4">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${accent || ''}`}>{value}</div>
    </div>
  );
}