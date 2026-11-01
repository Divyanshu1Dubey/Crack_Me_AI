"use client";

// /admin/ingestion/batches — batch list.
// Client component so the request carries the admin's auth token.
// Status and the job counts are computed by the API from the batch's jobs.

import { useEffect, useState } from "react";
import Link from "next/link";
import { ingestionAPI } from "@/lib/api";

export default function BatchesPage() {
  const [batches, setBatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    ingestionAPI
      .listBatches()
      .then((r: any) => {
        const data = r?.data;
        if (alive) setBatches(Array.isArray(data) ? data : (data?.results || []));
      })
      .catch(() => {
        if (alive) setBatches([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <Link href="/admin/ingestion" className="text-sm text-muted-foreground hover:text-foreground">
          ← Ingestion
        </Link>
        <h1 className="mt-1 text-2xl font-bold">Batches</h1>
      </div>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading batches…</p>
      ) : batches.length === 0 ? (
        <p className="text-sm text-muted-foreground">No batches yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="p-2">ID</th>
                <th className="p-2">Name</th>
                <th className="p-2">Status</th>
                <th className="p-2">Total</th>
                <th className="p-2">Completed</th>
                <th className="p-2">Failed</th>
                <th className="p-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id} className="border-b hover:bg-muted/40">
                  <td className="p-2">
                    <Link href={`/admin/ingestion/batches/${b.id}`} className="underline">
                      #{b.id}
                    </Link>
                  </td>
                  <td className="p-2">
                    <span className="block max-w-[18rem] truncate" title={b.name}>{b.name}</span>
                  </td>
                  <td className="p-2">{b.status}</td>
                  <td className="p-2">{b.total_jobs}</td>
                  <td className="p-2">{b.completed_jobs}</td>
                  <td className="p-2">{b.failed_jobs}</td>
                  <td className="p-2 text-muted-foreground">
                    {b.created_at ? new Date(b.created_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
