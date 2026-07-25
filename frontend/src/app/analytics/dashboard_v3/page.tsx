"use client";
/**
 * /analytics/dashboard_v3 — Phase-3 combined dashboard.
 * Renders the /api/analytics/dashboard_v3/ aggregate.  Cheaper than
 * seven round-trips.
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";

interface Dashboard {
  accuracy?: { total: number; correct: number; accuracy_pct: number };
  average_time?: { average_seconds: number };
  weak_subjects?: { subject_id: number; subject: string; attempts: number; mistakes: number; mistake_rate_pct: number }[];
  weak_topics?: { topic_id: number; topic: string; subject: string; attempts: number; mistakes: number; mistake_rate_pct: number }[];
  performance_trend?: { date: string; attempts: number; correct: number; accuracy_pct: number }[];
  revision_progress?: { topics: { topic_id: number; topic: string; total: number; by_confidence: Record<string, number> }[] };
  pyq_coverage?: Record<string, { attempted: number; total: number; coverage_pct: number; years: Record<string, { a: number; t: number }> }>;
}

export default function DashboardV3Page() {
  const [d, setD] = useState<Dashboard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.get("/analytics/dashboard_v3/");
        if (alive) setD(r.data);
      } catch (e: any) {
        if (alive) setErr(e?.message || "Failed to load dashboard");
      }
    })();
    return () => { alive = false; };
  }, []);

  if (err) return <p className="p-6 text-rose-300">Dashboard error: {err}</p>;
  if (!d) return <p className="p-6 text-slate-400">Loading dashboard…</p>;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 text-slate-100">
      <h1 className="text-2xl font-semibold">Analytics — Phase 3</h1>

      <section className="grid gap-4 md:grid-cols-3">
        <Card title="Accuracy"
          value={`${d.accuracy?.accuracy_pct ?? 0}%`}
          sub={`${d.accuracy?.correct ?? 0} / ${d.accuracy?.total ?? 0} correct`}
        />
        <Card title="Average time / question"
          value={`${Math.round((d.average_time?.average_seconds ?? 0))}s`}
          sub="last 90 days"
        />
        <Card title="Weak subjects"
          value={String(d.weak_subjects?.length ?? 0)}
          sub={`${d.weak_topics?.length ?? 0} weak topics`}
        />
      </section>

      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
        <h2 className="mb-2 text-sm uppercase tracking-wider text-slate-400">Performance trend (60d)</h2>
        <div className="flex h-32 items-end gap-1">
          {(d.performance_trend || []).map((p, i) => (
            <div key={i}
              title={`${p.date}: ${p.accuracy_pct}%`}
              style={{ height: `${Math.max(2, p.accuracy_pct)}%` }}
              className="w-2 rounded-t bg-emerald-500/70" />
          ))}
          {(d.performance_trend || []).length === 0 ? (
            <p className="text-xs text-slate-500">No attempts yet.</p>
          ) : null}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <List title="Weak subjects" rows={(d.weak_subjects || []).map((s) => ({
          label: s.subject, value: `${s.mistake_rate_pct}% mistakes` }))} />
        <List title="Weak topics" rows={(d.weak_topics || []).map((t) => ({
          label: `${t.topic} · ${t.subject}`, value: `${t.mistake_rate_pct}%` }))} />
      </section>

      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
        <h2 className="mb-2 text-sm uppercase tracking-wider text-slate-400">PYQ coverage</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-400">
            <tr><th>Exam</th><th>Attempted</th><th>Total</th><th>Coverage %</th></tr>
          </thead>
          <tbody>
            {Object.entries(d.pyq_coverage || {}).map(([k, v]) => (
              <tr key={k} className="border-t border-slate-700/40">
                <td className="py-1">{k}</td>
                <td>{v.attempted}</td>
                <td>{v.total}</td>
                <td>{v.coverage_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
        <h2 className="mb-2 text-sm uppercase tracking-wider text-slate-400">Revision progress</h2>
        <ul className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
          {(d.revision_progress?.topics || []).slice(0, 12).map((t) => (
            <li key={t.topic_id} className="rounded border border-slate-700/40 bg-slate-900/30 p-2 text-sm">
              <p className="text-slate-200">{t.topic}</p>
              <p className="text-xs text-slate-400">{t.total} attempts · conf {Object.entries(t.by_confidence).map(([k, v]) => `${k}:${v}`).join(", ")}</p>
            </li>
          ))}
          {(d.revision_progress?.topics || []).length === 0 ? (
            <p className="text-slate-500 text-xs">No revision data yet.</p>
          ) : null}
        </ul>
      </section>
    </main>
  );
}

function Card({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-400">{title}</p>
      <p className="text-3xl font-semibold">{value}</p>
      {sub ? <p className="mt-1 text-xs text-slate-400">{sub}</p> : null}
    </div>
  );
}

function List({ title, rows }: { title: string; rows: { label: string; value: string }[] }) {
  return (
    <div className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
      <h2 className="mb-2 text-sm uppercase tracking-wider text-slate-400">{title}</h2>
      <ul className="divide-y divide-slate-700/40">
        {rows.slice(0, 6).map((r, i) => (
          <li key={i} className="flex items-center justify-between py-1 text-sm">
            <span className="truncate">{r.label}</span>
            <span className="text-slate-300">{r.value}</span>
          </li>
        ))}
        {rows.length === 0 ? <li className="py-1 text-xs text-slate-500">None.</li> : null}
      </ul>
    </div>
  );
}
