// /admin/ingestion/jobs — table of all jobs with filters.

import Link from "next/link";
import { ingestionAPI } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function JobsPage({
  searchParams,
}: {
  searchParams: { status?: string; exam?: string };
}) {
  let jobs: any[] = [];
  try {
    const r: any = await ingestionAPI.listJobs({
      status: searchParams.status,
      parent_exam: searchParams.exam,
      page_size: 100,
    });
    const data = r?.data;
    jobs = Array.isArray(data) ? data : (data?.results || []);
  } catch {
    jobs = [];
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Import Jobs</h1>
      <form className="flex gap-3 items-end">
        <label className="text-sm">
          Status
          <select
            name="status"
            defaultValue={searchParams.status || ""}
            className="block border rounded px-2 py-1 ml-1"
          >
            <option value="">all</option>
            <option value="queued">queued</option>
            <option value="processing">processing</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
        <label className="text-sm">
          Exam
          <select
            name="exam"
            defaultValue={searchParams.exam || ""}
            className="block border rounded px-2 py-1 ml-1"
          >
            <option value="">all</option>
            <option value="neet_pg">neet_pg</option>
            <option value="ini_cet">ini_cet</option>
            <option value="fmge">fmge</option>
            <option value="usmle">usmle</option>
            <option value="plab">plab</option>
          </select>
        </label>
        <button type="submit" className="rounded bg-primary text-primary-foreground px-3 py-1 text-sm">Filter</button>
      </form>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b">
            <th className="p-2">ID</th>
            <th className="p-2">Exam</th>
            <th className="p-2">Material</th>
            <th className="p-2">Status</th>
            <th className="p-2">Stage</th>
            <th className="p-2">PR / NR / EF</th>
            <th className="p-2">Progress</th>
            <th className="p-2">Created</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="border-b hover:bg-muted/40">
              <td className="p-2"><Link className="underline" href={`/admin/ingestion/jobs/${j.id}`}>#{j.id}</Link></td>
              <td className="p-2">{j.parent_exam}</td>
              <td className="p-2 font-mono text-xs">{j.material_asset}</td>
              <td className="p-2">{j.status}</td>
              <td className="p-2">{j.current_stage || "—"}</td>
              <td className="p-2">
                {j.qa_v2_production_ready_pct ?? 0} / {j.qa_v2_needs_review_pct ?? 0} / {j.qa_v2_extraction_failure_pct ?? 0}
              </td>
              <td className="p-2">{j.progress_pct ?? 0}%</td>
              <td className="p-2 text-xs">{new Date(j.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
