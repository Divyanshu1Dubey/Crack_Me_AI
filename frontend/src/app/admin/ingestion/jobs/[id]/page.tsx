"use client";

// /admin/ingestion/jobs/[id] — job detail + stage timeline + logs.
//
// Client component: the ingestion API is admin-authenticated and the auth
// token only exists in the browser. As a server component this page could
// never load a job (every request was anonymous) and always showed
// "not found".

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ingestionAPI } from "@/lib/api";
import JobActions from "./JobActions";

export default function JobDetail() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);
  const [job, setJob] = useState<any>(null);
  const [stages, setStages] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!Number.isFinite(id)) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [jobRes, stagesRes, logsRes] = await Promise.all([
        ingestionAPI.getJob(id),
        ingestionAPI.listStages(id),
        ingestionAPI.listLogs(id, { page_size: 100 }),
      ]);
      setJob(jobRes.data);
      setStages(Array.isArray(stagesRes.data) ? stagesRes.data : (stagesRes.data?.results || []));
      setLogs(Array.isArray(logsRes.data) ? logsRes.data : (logsRes.data?.results || []));
    } catch {
      setJob(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading job…</div>;
  }

  if (!job) {
    return (
      <div className="p-6">
        <p>Job #{params?.id} not found.</p>
        <Link href="/admin/ingestion/jobs" className="underline">← back</Link>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-bold break-words">
          Job #{job.id} — {job.parent_exam} v{job.version}
        </h1>
        <p className="text-sm text-muted-foreground">
          status: <b>{job.status}</b> · stage: <b>{job.current_stage || "—"}</b> · progress: {job.progress_pct}%
        </p>
      </header>

      {job.waiting_for_worker && (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          This job has been queued for more than 5 minutes. Ingestion jobs run on the background worker
          (<code>python manage.py qcluster</code>); nothing will happen until a worker is running.
        </div>
      )}

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="PR" value={`${job.qa_v2_production_ready_pct ?? 0}%`} />
        <Stat label="NR" value={`${job.qa_v2_needs_review_pct ?? 0}%`} />
        <Stat label="EF" value={`${job.qa_v2_extraction_failure_pct ?? 0}%`} />
        <Stat label="Total Qs" value={job.qa_v2_total_questions ?? 0} />
        <Stat label="Imported" value={job.questions_imported ?? 0} />
        <Stat label="Staged NR" value={job.questions_staged_nr ?? 0} />
        <Stat label="Staged EF" value={job.questions_staged_ef ?? 0} />
        <Stat label="Pages" value={`${job.current_page}/${job.total_pages}`} />
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-2">Stage Timeline</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="p-2">Stage</th>
                <th className="p-2">Status</th>
                <th className="p-2">Pages</th>
                <th className="p-2">Artefacts</th>
                <th className="p-2">Started</th>
              </tr>
            </thead>
            <tbody>
              {stages.map((s) => (
                <tr key={s.id} className="border-b">
                  <td className="p-2 font-mono text-xs">{s.stage_name}</td>
                  <td className="p-2">{s.status}</td>
                  <td className="p-2">{s.pages_processed}/{s.pages_skipped}</td>
                  <td className="p-2">{s.artefacts_written}</td>
                  <td className="p-2 text-xs">{s.started_at ? new Date(s.started_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-2">Recent Logs</h2>
        <div className="space-y-1 text-xs font-mono break-words">
          {logs.slice(0, 50).map((l) => (
            <div key={l.id} className={l.level === "ERROR" ? "text-red-500" : l.level === "WARNING" ? "text-amber-500" : "text-muted-foreground"}>
              [{l.level}] {l.stage_name || ""} {l.message}
            </div>
          ))}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <JobActions id={id} onDone={load} />
        <Link href="/admin/ingestion/jobs" className="underline text-sm">← back to jobs</Link>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded border p-3">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
