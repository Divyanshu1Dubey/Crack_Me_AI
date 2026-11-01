"use client";

// /admin/ingestion/batches/[id] — batch detail with per-job grid.
// Client component so the request carries the admin's auth token.

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ingestionAPI } from "@/lib/api";

export default function BatchDetail() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);
  const [batch, setBatch] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    if (!Number.isFinite(id)) {
      setLoading(false);
      return;
    }
    ingestionAPI
      .getBatch(id)
      .then((r: any) => {
        if (alive) setBatch(r?.data ?? null);
      })
      .catch(() => {
        if (alive) setBatch(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [id]);

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading batch…</div>;
  }
  if (!batch) {
    return (
      <div className="p-6">
        <p>Batch #{params?.id} not found.</p>
        <Link href="/admin/ingestion/batches" className="underline">← back</Link>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <Link href="/admin/ingestion/batches" className="text-sm text-muted-foreground hover:text-foreground">
        ← Batches
      </Link>
      <h1 className="text-2xl font-bold break-words">
        Batch #{batch.id} — {batch.name}
      </h1>
      <p className="text-sm text-muted-foreground">
        {batch.total_jobs} jobs · {batch.completed_jobs} completed · {batch.failed_jobs} failed
      </p>
      <div className="overflow-x-auto">
        <table className="w-full whitespace-nowrap text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="p-2">Job</th>
              <th className="p-2">Material</th>
              <th className="p-2">Status</th>
              <th className="p-2">PR / NR / EF</th>
            </tr>
          </thead>
          <tbody>
            {(batch.jobs || []).map((j: any) => (
              <tr key={j.id} className="border-b hover:bg-muted/40">
                <td className="p-2">
                  <Link href={`/admin/ingestion/jobs/${j.id}`} className="underline">
                    #{j.id}
                  </Link>
                </td>
                <td className="p-2">
                  <span className="block max-w-[18rem] truncate" title={j.material_filename || undefined}>
                    {j.material_filename || `#${j.material_asset}`}
                  </span>
                </td>
                <td className="p-2">{j.status}</td>
                <td className="p-2">
                  {j.qa_v2_production_ready_pct ?? 0} / {j.qa_v2_needs_review_pct ?? 0} / {j.qa_v2_extraction_failure_pct ?? 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
