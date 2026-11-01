"use client";

// /admin/ingestion/jobs — table of all jobs with filters.
// Client component so requests carry the admin's auth token (see the job
// detail page for why the server-rendered version could never load data).

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ingestionAPI } from "@/lib/api";
import { EXAM_LABEL, examLabel, QA_TITLE, stageLabel } from "../labels";

const STATUSES = ["queued", "processing", "completed", "failed", "crashed", "cancelled"];

function JobsTable() {
  const sp = useSearchParams();
  const statusFilter = sp?.get("status") || "";
  const examFilter = sp?.get("exam") || "";
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    ingestionAPI
      .listJobs({
        ...(statusFilter ? { status: statusFilter } : {}),
        ...(examFilter ? { parent_exam: examFilter } : {}),
        page_size: 100,
      })
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
  }, [statusFilter, examFilter]);

  return (
    <div className="space-y-4">
      <div>
        <Link href="/admin/ingestion" className="text-sm text-muted-foreground hover:text-foreground">
          ← Ingestion
        </Link>
        <h1 className="mt-1 text-2xl font-bold">Import Jobs</h1>
      </div>
      <form className="flex flex-wrap gap-3 items-end">
        <label className="text-sm">
          Status
          <select
            name="status"
            defaultValue={statusFilter}
            className="block border rounded px-2 py-1 ml-1 bg-background"
          >
            <option value="">All</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Exam
          <select
            name="exam"
            defaultValue={examFilter}
            className="block border rounded px-2 py-1 ml-1 bg-background"
          >
            <option value="">All</option>
            {Object.entries(EXAM_LABEL).map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </label>
        <button type="submit" className="rounded bg-primary text-primary-foreground px-3 py-1 text-sm">Filter</button>
      </form>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading jobs…</p>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No jobs match these filters.</p>
      ) : (
        // whitespace-nowrap keeps rows one line tall; the low-value columns
        // are hidden below `sm` so ID / Status / Stage / Progress fit a phone.
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="p-2">ID</th>
                <th className="hidden p-2 sm:table-cell">Exam</th>
                <th className="hidden p-2 sm:table-cell">Material</th>
                <th className="p-2">Status</th>
                <th className="p-2">Stage</th>
                <th className="hidden p-2 sm:table-cell">
                  <abbr title={QA_TITLE} className="cursor-help">PR / NR / EF</abbr>
                </th>
                <th className="p-2">Progress</th>
                <th className="hidden p-2 sm:table-cell">Created</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} className="border-b hover:bg-muted/40">
                  <td className="p-2"><Link className="underline" href={`/admin/ingestion/jobs/${j.id}`}>#{j.id}</Link></td>
                  <td className="hidden p-2 sm:table-cell">{examLabel(j)}</td>
                  <td className="hidden p-2 sm:table-cell">
                    <span className="block max-w-[16rem] truncate" title={j.material_filename || undefined}>
                      {j.material_filename || `#${j.material_asset}`}
                    </span>
                  </td>
                  <td className="p-2">
                    {j.status}
                    {j.waiting_for_worker && (
                      <span className="ml-1 text-xs text-amber-600 dark:text-amber-400" title="Queued for over 5 minutes: is the qcluster worker running?">
                        (no worker?)
                      </span>
                    )}
                  </td>
                  <td className="p-2" title={j.current_stage || undefined}>{stageLabel(j.current_stage)}</td>
                  <td className="hidden p-2 sm:table-cell" title={QA_TITLE}>
                    {j.qa_v2_production_ready_pct ?? 0} / {j.qa_v2_needs_review_pct ?? 0} / {j.qa_v2_extraction_failure_pct ?? 0}
                  </td>
                  <td className="p-2">{j.progress_pct ?? 0}%</td>
                  <td className="hidden p-2 sm:table-cell">{j.created_at ? new Date(j.created_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted-foreground">Loading jobs…</div>}>
      <JobsTable />
    </Suspense>
  );
}
