"use client";
/**
 * /analytics/heatmap — Phase-3 subject × day-of-week heatmap.
 * Loads /api/analytics/heatmap/subject/.
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";

interface HeatMapCell { n: number; correct: number }
interface HeatMap { [subjectId: string]: { [dow: string]: HeatMapCell } }

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function HeatmapPage() {
  const [data, setData] = useState<HeatMap | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.get("/api/analytics/heatmap/subject/");
        if (alive) setData(r.data || {});
      } catch (e: any) {
        if (alive) setErr(e?.message || "Heatmap failed to load");
      }
    })();
    return () => { alive = false; };
  }, []);

  if (err) return <p className="p-6 text-rose-300">{err}</p>;
  if (!data) return <p className="p-6 text-slate-400">Loading heatmap…</p>;
  const subjects = Object.keys(data);
  if (subjects.length === 0) {
    return (
      <main className="p-6 text-slate-100">
        <h1 className="mb-3 text-2xl font-semibold">Heatmap</h1>
        <p className="text-sm text-slate-500">Not enough practice data yet.</p>
      </main>
    );
  }
  return (
    <main className="p-6 text-slate-100">
      <h1 className="mb-3 text-2xl font-semibold">Subject × Day-of-week heatmap</h1>
      <table className="border-separate border-spacing-1">
        <thead>
          <tr>
            <th></th>
            {DAYS.map((d) => <th key={d} className="text-xs text-slate-400">{d}</th>)}
          </tr>
        </thead>
        <tbody>
          {subjects.map((sid) => (
            <tr key={sid}>
              <td className="pr-2 text-xs text-slate-300">{sid}</td>
              {DAYS.map((_, i) => {
                const cell = data[sid]?.[String(i)] || { n: 0, correct: 0 };
                const pct = cell.n ? Math.round((cell.correct / cell.n) * 100) : 0;
                const intensity = Math.min(100, pct);
                return (
                  <td key={i}
                    title={`n=${cell.n}, correct=${cell.correct}, ${pct}%`}
                    style={{ background: `rgba(16, 185, 129, ${intensity / 100})` }}
                    className="h-7 w-10 rounded text-center text-[10px] text-emerald-50">
                    {pct || ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
