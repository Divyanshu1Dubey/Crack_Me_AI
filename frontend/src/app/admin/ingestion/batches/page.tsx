// /admin/ingestion/batches — batch list.

import Link from "next/link";
import { ingestionAPI } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function BatchesPage() {
  let batches: any[] = [];
  try {
    const r: any = await ingestionAPI.listBatches();
    const data = r?.data;
    batches = Array.isArray(data) ? data : (data?.results || []);
  } catch {
    batches = [];
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Batches</h1>
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
  );
}
