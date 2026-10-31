"use client";

// /admin/ingestion/batches — batch list.
// Client component so the request carries the admin's auth token.

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
    <div className="p-4 sm:p-6 space-y-4">
      <h1 className="text-2xl font-bold">Batches</h1>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading batches…</p>
      ) : batches.length === 0 ? (
        <p className="text-sm text-muted-foreground">No batches yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="p-2">ID</th>
                <th className="p-2">Name</th>
                <th className="p-2">Status</th>
                <th className="p-2">Total</th>
                <th className="p-2">Completed</th>
                <th className="p-2">Failed</th>
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
                  <td className="p-2">{b.name}</td>
                  <td className="p-2">{b.status}</td>
                  <td className="p-2">{b.total_jobs}</td>
                  <td className="p-2">{b.completed_jobs}</td>
                  <td className="p-2">{b.failed_jobs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
