"use client";
/**
 * /admin/recall/search-analytics — Phase-3 admin placeholder.
 * Pulls the /api/analytics/search_analytics/ stub.  When Phase 4
 * instruments the front-end search box, this becomes a real
 * dashboard.
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";

interface Row {
  top_queries: { query: string; count: number }[];
  daily: { date: string; n: number }[];
}

export default function SearchAnalyticsPage() {
  const [d, setD] = useState<Row | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.get("/analytics/search_analytics/");
        if (alive) setD(r.data);
      } catch (e: any) {
        if (alive) setErr(e?.message || "Failed");
      }
    })();
    return () => { alive = false; };
  }, []);

  if (err) return <p className="p-6 text-rose-300">{err}</p>;
  if (!d) return <p className="p-6 text-slate-400">Loading…</p>;

  return (
    <main className="mx-auto max-w-4xl space-y-4 px-4 py-6 text-slate-100">
      <h1 className="text-2xl font-semibold">Search analytics</h1>
      <p className="text-sm text-slate-500">
        Phase-3 placeholder. Wire client search box → <code>/api/analytics/search_log/</code> in Phase 4.
      </p>
      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-3 text-sm">
        <h2 className="mb-1 text-xs uppercase tracking-wider text-slate-400">Top queries</h2>
        {d.top_queries.length === 0 ? (
          <p className="text-slate-500">No data.</p>
        ) : (
          <ul>{d.top_queries.map((q) => <li key={q.query}>{q.query} — {q.count}</li>)}</ul>
        )}
      </section>
      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-3 text-sm">
        <h2 className="mb-1 text-xs uppercase tracking-wider text-slate-400">Daily volume</h2>
        {d.daily.length === 0 ? (
          <p className="text-slate-500">No data.</p>
        ) : (
          <ul>{d.daily.map((d) => <li key={d.date}>{d.date}: {d.n}</li>)}</ul>
        )}
      </section>
    </main>
  );
}
