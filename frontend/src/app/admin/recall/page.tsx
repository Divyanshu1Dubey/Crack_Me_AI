"use client";
/**
 * /admin/recall — Phase-3 admin status overview.
 * Aggregates QuestionImportJob + QuestionImage + DuplicateCluster.
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";

interface ImportJob {
  id: number;
  status: string;
  source_filename?: string;
  created_at?: string;
  updated_at?: string;
  summary?: any;
}

interface Cluster { id: number; canonical_question_id: number; detection_method: string; member_count?: number; created_at?: string }

export default function AdminRecallPage() {
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [images, setImages] = useState<any[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [j, im, cl] = await Promise.all([
          api.get("/imports/neetpg/jobs/"),
          api.get("/questions/recall_sources/"),
          api.get("/questions/duplicate_clusters/"),
        ]);
        if (!alive) return;
        setJobs(j.data?.results || j.data || []);
        setImages(im.data?.results || im.data || []);
        setClusters(cl.data?.results || cl.data || []);
      } catch (e: any) {
        if (alive) setErr(e?.message || "Failed to load admin data");
      }
    })();
    return () => { alive = false; };
  }, []);

  if (err) return <p className="p-6 text-rose-300">{err}</p>;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 text-slate-100">
      <h1 className="text-2xl font-semibold">Recall admin</h1>

      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
        <h2 className="mb-2 text-sm uppercase tracking-wider text-slate-400">Import status</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-400">
            <tr><th>id</th><th>status</th><th>source</th><th>created</th><th>summary</th></tr>
          </thead>
          <tbody>
            {jobs.slice(0, 20).map((j) => (
              <tr key={j.id} className="border-t border-slate-700/40">
                <td className="py-1">{j.id}</td>
                <td>{j.status}</td>
                <td>{j.source_filename || ""}</td>
                <td>{j.created_at?.slice(0, 16) || ""}</td>
                <td className="truncate text-xs text-slate-400">
                  {j.summary ? JSON.stringify(j.summary) : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
        <h2 className="mb-2 text-sm uppercase tracking-wider text-slate-400">Recall sources (recent)</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-400">
            <tr><th>id</th><th>filename</th><th>sha16</th><th>scan_type</th><th>recall_status</th><th>created</th></tr>
          </thead>
          <tbody>
            {images.slice(0, 20).map((s) => (
              <tr key={s.id} className="border-t border-slate-700/40">
                <td>{s.id}</td>
                <td className="font-mono text-xs">{s.pdf_filename}</td>
                <td className="font-mono text-xs">{s.pdf_sha256_short}</td>
                <td>{s.scan_type}</td>
                <td>{s.recall_status}</td>
                <td>{s.created_at?.slice(0, 16)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
        <h2 className="mb-2 text-sm uppercase tracking-wider text-slate-400">Duplicate clusters</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-400">
            <tr><th>id</th><th>canonical</th><th>method</th><th>members</th><th>created</th></tr>
          </thead>
          <tbody>
            {clusters.slice(0, 20).map((c) => (
              <tr key={c.id} className="border-t border-slate-700/40">
                <td>{c.id}</td>
                <td>{c.canonical_question_id}</td>
                <td>{c.detection_method}</td>
                <td>{c.member_count ?? "—"}</td>
                <td>{c.created_at?.slice(0, 16)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
