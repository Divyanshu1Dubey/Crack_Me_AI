"use client";
/**
 * RecallSearchBox — Phase-3 chip-style search filter UI.
 *
 * Sends every active chip to /api/questions/recall_search/ and renders
 * facet counts so the user can drill down (subject × topic × year ×
 * difficulty × diagnosis × drug × …).
 *
 * Typing is debounced and a newer search aborts the in-flight one, so a
 * word costs one request instead of one per keystroke (the endpoint runs
 * an icontains scan over several text fields).
 */
import { useCallback, useEffect, useRef, useState } from "react";
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

/** Pause after the last keystroke before searching. */
const SEARCH_DEBOUNCE_MS = 350;

export default function RecallSearchBox({ initialQuery = "", onResults }: Props) {
  const [q, setQ] = useState(initialQuery);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [clinical, setClinical] = useState<Record<string, string>>({});
  const [facets, setFacets] = useState<Facets>({});
  const [count, setCount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  // In-flight search; aborted when a newer one starts or on unmount.
  const inFlight = useRef<AbortController | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const firstRun = useRef(true);
  // Latest callback without re-triggering searches when the parent re-renders.
  const onResultsRef = useRef(onResults);
  useEffect(() => { onResultsRef.current = onResults; }, [onResults]);

  const run = useCallback(async () => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setBusy(true);
    try {
      const params: Record<string, string> = { page_size: "30" };
      if (q.trim()) params.q = q.trim();
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      Object.entries(clinical).forEach(([k, v]) => { if (v) params[k] = v; });
      // The api.ts baseURL already ends in `/api`, so this path is
      // relative to the base (NOT absolute). The previous leading
      // `/api/` produced `/api/api/...` which 404'd on the backend.
      const r = await api.get("/questions/recall_search/", { params, signal: controller.signal });
      if (controller.signal.aborted) return;
      setFacets(r.data?.facets || {});
      setCount(r.data?.count ?? null);
      onResultsRef.current?.(r.data?.results || [], r.data?.facets || {});
    } catch {
      // A superseded search is not a failure; leave the UI to the newer one.
      if (controller.signal.aborted) return;
      setFacets({}); setCount(null); onResultsRef.current?.([], {});
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setBusy(false);
      }
    }
  }, [q, filters, clinical]);

  // Search when the query or a filter changes: right away on first load,
  // then after a short pause in typing.
  useEffect(() => {
    const delay = firstRun.current ? 0 : SEARCH_DEBOUNCE_MS;
    firstRun.current = false;
    debounceTimer.current = setTimeout(() => { void run(); }, delay);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [run]);

  // Cancel any in-flight search when the box unmounts.
  useEffect(() => () => { inFlight.current?.abort(); }, []);

  /** Search now (button / Enter) instead of waiting for the debounce. */
  const runNow = () => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    void run();
  };

  const toggle = (group: "filters" | "clinical", k: string, v: string) => {
    const set = group === "filters" ? filters : clinical;
    const setter = group === "filters" ? setFilters : setClinical;
    setter({ ...set, [k]: set[k] === v ? "" : v });
  };

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4 text-foreground">
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") runNow(); }}
          placeholder="Search by keyword, drug, diagnosis, etc…"
          aria-label="Search recall questions"
          className="flex-1 rounded border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
        />
        <button onClick={runNow} disabled={busy}
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
              <p className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">{f.label}</p>
              <div className="flex flex-wrap gap-1">
                {entries.map(([val, c]) => (
                  <button
                    key={val}
                    onClick={() => toggle("filters", f.param, val)}
                    aria-pressed={filters[f.param] === val}
                    className={`rounded-full border px-2 py-0.5 text-xs ${filters[f.param] === val ? "border-emerald-500 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200" : "border-border bg-muted text-foreground"}`}
                  >
                    {val} <span className="text-muted-foreground">({c})</span>
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
            onKeyDown={(e) => { if (e.key === "Enter") runNow(); }}
            placeholder={`Filter by ${dim}…`}
            aria-label={`Filter by ${dim}`}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground"
          />
        ))}
      </div>

      {count !== null ? (
        <p className="text-xs text-muted-foreground">{count} matching question(s).</p>
      ) : null}
    </div>
  );
}
