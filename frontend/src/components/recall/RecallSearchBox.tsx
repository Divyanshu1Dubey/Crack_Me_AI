"use client";
/**
 * RecallSearchBox — Phase-3 chip-style search filter UI.
 *
 * Sends every active chip to /api/questions/recall_search/ and renders
 * facet counts so the user can drill down (subject × topic × year ×
 * difficulty × diagnosis × drug × …).
 */
import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";

interface Facets {
  exam_type?: Record<string, number>;
  year?: Record<string, number>;
  clinical_category?: Record<string, number>;
  question_type?: Record<string, number>;
  difficulty?: Record<string, number>;
  modality?: Record<string, number>;
}

interface Props {
  initialQuery?: string;
  onResults?: (results: any[], facets: Facets) => void;
}

const FACET_DEFS: { key: keyof Facets; param: string; label: string }[] = [
  { key: "exam_type", param: "exam_type", label: "Exam" },
  { key: "year", param: "year", label: "Year" },
  { key: "clinical_category", param: "clinical_category", label: "Category" },
  { key: "question_type", param: "question_type", label: "Type" },
  { key: "difficulty", param: "difficulty", label: "Difficulty" },
  { key: "modality", param: "modality", label: "Modality" },
];

export default function RecallSearchBox({ initialQuery = "", onResults }: Props) {
  const [q, setQ] = useState(initialQuery);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [clinical, setClinical] = useState<Record<string, string>>({});
  const [facets, setFacets] = useState<Facets>({});
  const [count, setCount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const run = useMemo(() => async () => {
    setBusy(true);
    try {
      const params: Record<string, string> = { page_size: "30" };
      if (q.trim()) params.q = q.trim();
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      Object.entries(clinical).forEach(([k, v]) => { if (v) params[k] = v; });
      const r = await api.get("/api/questions/recall_search/", { params });
      setFacets(r.data?.facets || {});
      setCount(r.data?.count ?? null);
      onResults?.(r.data?.results || [], r.data?.facets || {});
    } catch {
      setFacets({}); setCount(null); onResults?.([], {});
    } finally {
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, filters, clinical]);

  useEffect(() => { void run(); }, [run]);

  const toggle = (group: "filters" | "clinical", k: string, v: string) => {
    const set = group === "filters" ? filters : clinical;
    const setter = group === "filters" ? setFilters : setClinical;
    setter({ ...set, [k]: set[k] === v ? "" : v });
  };

  return (
    <div className="space-y-4 rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by keyword, drug, diagnosis, etc…"
          className="flex-1 rounded bg-slate-800 px-3 py-2 text-sm"
        />
        <button onClick={run} disabled={busy}
          className="rounded bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "…" : "Search"}
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {FACET_DEFS.map((f) => {
          const map = facets[f.key] || {};
          const entries = Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 8);
          if (entries.length === 0) return null;
          return (
            <div key={f.key}>
              <p className="mb-1 text-xs uppercase tracking-wider text-slate-400">{f.label}</p>
              <div className="flex flex-wrap gap-1">
                {entries.map(([val, c]) => (
                  <button
                    key={val}
                    onClick={() => toggle("filters", f.param, val)}
                    className={`rounded-full border px-2 py-0.5 text-xs ${filters[f.param] === val ? "border-emerald-500 bg-emerald-500/20 text-emerald-100" : "border-slate-700/60 bg-slate-800/60 text-slate-200"}`}
                  >
                    {val} <span className="text-slate-400">({c})</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {(["diagnosis", "drug", "disease", "investigation", "clinical_system", "subtopic"] as const).map((dim) => (
          <input
            key={dim}
            value={clinical[dim] || ""}
            onChange={(e) => setClinical({ ...clinical, [dim]: e.target.value })}
            placeholder={`Filter by ${dim}…`}
            className="rounded bg-slate-800 px-2 py-1 text-xs"
          />
        ))}
      </div>

      {count !== null ? (
        <p className="text-xs text-slate-400">{count} matching question(s).</p>
      ) : null}
    </div>
  );
}
