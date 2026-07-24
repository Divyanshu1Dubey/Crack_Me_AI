// /admin/ingestion — landing page.
// Tiles for queue depth, today stats, last 10 jobs.

import Link from "next/link";
import { ingestionAPI } from "@/lib/api";

export const dynamic = "force-dynamic";

async function loadOverview() {
  try {
    const r: any = await ingestionAPI.listJobs({ page_size: 10 });
    const data = r?.data;
    return Array.isArray(data) ? data : (data?.results || []);
  } catch {
    return [];
  }
}

export default async function IngestionLanding() {
  const jobs = await loadOverview();
  const counts = jobs.reduce(
    (acc: any, j: any) => {
      acc[j.status] = (acc[j.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-3xl font-bold">Production Ingestion</h1>
        <p className="text-sm text-muted-foreground">
          NEET PG / INI-CET / FMGE / USMLE / PLAB — isolated from UPSC CMS
        </p>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Tile label="Queued" value={counts.queued || 0} />
        <Tile label="Processing" value={counts.processing || 0} />
        <Tile label="Completed" value={counts.completed || 0} />
        <Tile label="Failed" value={counts.failed || 0} />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <LinkTile href="/admin/ingestion/upload" title="Upload Material" desc="Drop a NEET PG / INI-CET PDF" />
        <LinkTile href="/admin/ingestion/jobs" title="Jobs" desc="Filter, retry, cancel" />
        <LinkTile href="/admin/ingestion/batches" title="Batches" desc="Multi-PDF rollouts" />
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-3">Last 10 jobs</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="p-2">ID</th>
                <th className="p-2">Exam</th>
                <th className="p-2">Status</th>
                <th className="p-2">PR%</th>
                <th className="p-2">NR%</th>
                <th className="p-2">EF%</th>
                <th className="p-2">Progress</th>
              </tr>
            </thead>
            <tbody>
              {(jobs as any[]).map((j) => (
                <tr key={j.id} className="border-b hover:bg-muted/40">
                  <td className="p-2"><Link href={`/admin/ingestion/jobs/${j.id}`} className="underline">#{j.id}</Link></td>
                  <td className="p-2">{j.parent_exam}</td>
                  <td className="p-2">{j.status}</td>
                  <td className="p-2">{j.qa_v2_production_ready_pct ?? "—"}</td>
                  <td className="p-2">{j.qa_v2_needs_review_pct ?? "—"}</td>
                  <td className="p-2">{j.qa_v2_extraction_failure_pct ?? "—"}</td>
                  <td className="p-2">{j.progress_pct ?? 0}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function LinkTile({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <Link
      href={href}
      className="block rounded-lg border p-5 hover:border-primary transition-colors"
    >
      <div className="font-medium">{title}</div>
      <div className="text-xs text-muted-foreground mt-1">{desc}</div>
    </Link>
  );
}
