// /admin/ingestion/batches/[id] — batch detail with per-job grid.

import Link from "next/link";
import { ingestionAPI } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function BatchDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id: idStr } = await params;
  const id = Number(idStr);
  let batch: any = null;
  try {
    const r: any = await ingestionAPI.getBatch(id);
    batch = r?.data;
  } catch {
    batch = null;
  }
  if (!batch) {
    return <div className="p-6">Batch #{id} not found.</div>;
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">
        Batch #{batch.id} — {batch.name}
      </h1>
      <p className="text-sm text-muted-foreground">
        {batch.total_jobs} jobs · {batch.completed_jobs} completed · {batch.failed_jobs} failed
      </p>
      <table className="w-full text-sm">
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
              <td className="p-2 font-mono text-xs">{j.material_asset}</td>
              <td className="p-2">{j.status}</td>
              <td className="p-2">
                {j.qa_v2_production_ready_pct ?? 0} / {j.qa_v2_needs_review_pct ?? 0} / {j.qa_v2_extraction_failure_pct ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
