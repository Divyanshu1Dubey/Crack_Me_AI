"use client";

// /admin/ingestion — landing page.
// Tiles for queue depth, today stats, last 10 jobs.
// Client component so the request carries the admin's auth token.

import { useEffect, useState } from "react";
import Link from "next/link";
import { ingestionAPI } from "@/lib/api";
import { examLabel } from "./labels";

const RECENT = 10;

export default function IngestionLanding() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    // The endpoint returns up to 200 jobs (it has no page size); the tiles
    // count all of them and the table shows the newest RECENT.
    ingestionAPI
      .listJobs()
      .then((r: any) => {
        const data = r?.data;
        if (alive) setJobs(Array.isArray(data) ? data : (data?.results || []));
      })
      .catch(() => {
        if (alive) setJobs([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const counts = jobs.reduce(
    (acc: Record<string, number>, j: any) => {
      acc[j.status] = (acc[j.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <header>
        <Link href="/admin" className="text-xs text-muted-foreground hover:text-foreground">
          ← Admin dashboard
        </Link>
        <h1 className="mt-1 text-3xl font-bold">Production Ingestion</h1>
        <p className="text-sm text-muted-foreground">
          NEET PG / INI-CET / FMGE / USMLE / PLAB — isolated from UPSC CMS
        </p>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Tile label="Queued" value={counts.queued || 0} />
        <Tile label="Processing" value={counts.processing || 0} />
        <Tile label="Completed" value={counts.completed || 0} />
        <Tile label="Failed / crashed" value={(counts.failed || 0) + (counts.crashed || 0)} />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <LinkTile href="/admin/ingestion/upload" title="Upload Material" desc="Upload a NEET PG / INI-CET PDF" />
        <LinkTile href="/admin/ingestion/jobs" title="Jobs" desc="Filter, retry, cancel" />
        <LinkTile href="/admin/ingestion/batches" title="Batches" desc="Multi-PDF rollouts" />
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-3">Last {RECENT} jobs</h2>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No jobs yet.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full whitespace-nowrap text-sm">
                <thead>
                  <tr className="text-left border-b">
                    <th className="p-2">ID</th>
                    <th className="p-2">Exam</th>
                    <th className="p-2">Status</th>
                    <th className="hidden p-2 sm:table-cell" title="Production-ready %">PR%</th>
                    <th className="hidden p-2 sm:table-cell" title="Needs-review %">NR%</th>
                    <th className="hidden p-2 sm:table-cell" title="Extraction-failure %">EF%</th>
                    <th className="p-2">Progress</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.slice(0, RECENT).map((j) => (
                    <tr key={j.id} className="border-b hover:bg-muted/40">
                      <td className="p-2"><Link href={`/admin/ingestion/jobs/${j.id}`} className="underline">#{j.id}</Link></td>
                      <td className="p-2">{examLabel(j)}</td>
                      <td className="p-2">{j.status}</td>
                      <td className="hidden p-2 sm:table-cell">{j.qa_v2_production_ready_pct ?? "—"}</td>
                      <td className="hidden p-2 sm:table-cell">{j.qa_v2_needs_review_pct ?? "—"}</td>
                      <td className="hidden p-2 sm:table-cell">{j.qa_v2_extraction_failure_pct ?? "—"}</td>
                      <td className="p-2">{j.progress_pct ?? 0}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Link href="/admin/ingestion/jobs" className="mt-2 inline-block text-sm underline">
              View all jobs →
            </Link>
          </>
        )}
      </section>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function LinkTile({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <Link
      href={href}
      className="block rounded-lg border bg-card p-5 hover:border-primary! transition-colors"
    >
      <div className="font-medium">{title}</div>
      <div className="text-xs text-muted-foreground mt-1">{desc}</div>
    </Link>
  );
}
