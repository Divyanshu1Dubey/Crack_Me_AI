// /admin/ingestion/jobs/[id] — job detail + stage timeline + logs.

import Link from "next/link";
import { ingestionAPI } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function JobDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id: idStr } = await params;
  const id = Number(idStr);
  let job: any = null;
  let stages: any[] = [];
  let logs: any[] = [];
  try {
    const jobRes = await ingestionAPI.getJob(id);
    job = jobRes.data;
    const stagesRes = await ingestionAPI.listStages(id);
    stages = Array.isArray(stagesRes.data) ? stagesRes.data : (stagesRes.data?.results || []);
    const logsRes = await ingestionAPI.listLogs(id, { page_size: 100 });
    logs = Array.isArray(logsRes.data) ? logsRes.data : (logsRes.data?.results || []);
  } catch {
    job = null;
  }

  if (!job) {
    return (
      <div className="p-6">
        <p>Job #{id} not found.</p>
        <Link href="/admin/ingestion/jobs" className="underline">← back</Link>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">
          Job #{job.id} — {job.parent_exam} v{job.version}
        </h1>
        <p className="text-sm text-muted-foreground">
          status: <b>{job.status}</b> · stage: <b>{job.current_stage || "—"}</b> · progress: {job.progress_pct}%
        </p>
      </header>

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
                <td className="p-2 text-xs">{new Date(s.started_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-2">Recent Logs</h2>
        <div className="space-y-1 text-xs font-mono">
          {logs.slice(0, 50).map((l) => (
            <div key={l.id} className={l.level === "ERROR" ? "text-red-500" : l.level === "WARNING" ? "text-amber-500" : "text-muted-foreground"}>
              [{l.level}] {l.stage_name || ""} {l.message}
            </div>
          ))}
        </div>
      </section>

      <Actions id={id} />
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

function Actions({ id }: { id: number }) {
  return (
    <div className="flex gap-2">
      <form action={`/api/ingestion/jobs/${id}/retry/`} method="post">
        <button className="rounded border px-3 py-1 text-sm">Retry</button>
      </form>
      <form action={`/api/ingestion/jobs/${id}/cancel/`} method="post">
        <button className="rounded border px-3 py-1 text-sm">Cancel</button>
      </form>
      <Link href="/admin/ingestion/jobs" className="underline text-sm ml-3">← back to jobs</Link>
    </div>
  );
}
