"use client";
/**
 * /analytics/heatmap — Phase-3 subject × day-of-week heatmap.
 * Loads /api/analytics/heatmap/subject/ (keyed by subject id) and
 * resolves subject names from /api/questions/subjects/.
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { useRequireAuth } from "@/lib/hooks/useRequireAuth";

interface HeatMapCell { n: number; correct: number }
interface HeatMap { [subjectId: string]: { [dow: string]: HeatMapCell } }

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

async function loadSubjectNames(): Promise<Record<string, string>> {
  const names: Record<string, string> = {};
  let url: string | null = "/questions/subjects/";
  // The subject list is paginated; follow a few pages at most.
  for (let page = 0; url && page < 10; page++) {
    const r: any = await api.get(url);
    const body = r?.data;
    const rows: any[] = Array.isArray(body) ? body : (body?.results || []);
    rows.forEach((s) => { if (s?.id != null) names[String(s.id)] = s.name; });
    const next: string | null = Array.isArray(body) ? null : body?.next || null;
    // `next` is absolute; keep only the path + query relative to /api.
    url = next ? next.replace(/^.*?\/api(?=\/)/, "") : null;
  }
  return names;
}

export default function HeatmapPage() {
  // Member page: wait for auth (logged-out visitors go to /login?next=...).
  const { ready } = useRequireAuth();
  const [data, setData] = useState<HeatMap | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    let alive = true;
    (async () => {
      try {
        const r = await api.get("/analytics/heatmap/subject/");
        if (alive) setData(r.data || {});
      } catch {
        if (alive) setErr("Heatmap failed to load. Please try again.");
      }
    })();
    loadSubjectNames()
      .then((n) => { if (alive) setNames(n); })
      .catch(() => { /* fall back to ids */ });
    return () => { alive = false; };
  }, [ready]);

  if (err) return <p role="alert" className="p-6 text-destructive">{err}</p>;
  if (!data) return <p className="p-6 text-muted-foreground">Loading heatmap…</p>;
  const subjects = Object.keys(data);
  if (subjects.length === 0) {
    return (
      <main className="p-4 sm:p-6 text-foreground">
        <h1 className="mb-3 text-2xl font-semibold">Heatmap</h1>
        <p className="text-sm text-muted-foreground">Not enough practice data yet.</p>
      </main>
    );
  }
  return (
    <main className="p-4 sm:p-6 text-foreground">
      <h1 className="mb-3 text-2xl font-semibold">Subject × Day-of-week heatmap</h1>
      <p className="mb-4 text-sm text-muted-foreground">Accuracy (%) by subject and weekday. Darker = higher accuracy.</p>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-1">
          <thead>
            <tr>
              <th scope="col" className="sr-only">Subject</th>
              {DAYS.map((d) => <th key={d} scope="col" className="text-xs font-medium text-muted-foreground">{d}</th>)}
            </tr>
          </thead>
          <tbody>
            {subjects.map((sid) => (
              <tr key={sid}>
                <th scope="row" className="pr-2 text-left text-xs font-medium text-foreground/80 whitespace-nowrap">
                  {sid === "0" ? "Unassigned" : (names[sid] || `Subject ${sid}`)}
                </th>
                {DAYS.map((day, i) => {
                  const cell = data[sid]?.[String(i)] || { n: 0, correct: 0 };
                  const pct = cell.n ? Math.round((cell.correct / cell.n) * 100) : 0;
                  const intensity = Math.min(100, pct);
                  return (
                    <td key={i}
                      title={`${day}: ${cell.n} answered, ${cell.correct} correct (${pct}%)`}
                      style={{ background: cell.n ? `rgba(16, 185, 129, ${Math.max(0.12, intensity / 100)})` : undefined }}
                      className={`h-7 w-10 min-w-10 rounded text-center text-[10px] font-semibold ${cell.n ? (intensity > 55 ? "text-white" : "text-foreground") : "bg-muted text-muted-foreground"}`}>
                      {cell.n ? pct : ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
