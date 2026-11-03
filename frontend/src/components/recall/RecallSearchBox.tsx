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
 *
 * A failed search is reported as an error with a Retry button (and via
 * `onError`), not as an empty result list.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { facetEntries, facetLabel, humaniseKey } from "@/components/recall/recallFacets";

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
  /** A search succeeded (`count` = total matches reported by the API). */
  onResults?: (results: any[], facets: Facets, count: number | null) => void;
  /** A search failed (network / server error); the box shows a Retry button. */
  onError?: () => void;
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

export default function RecallSearchBox({ initialQuery = "", onResults, onError }: Props) {
  const [q, setQ] = useState(initialQuery);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [clinical, setClinical] = useState<Record<string, string>>({});
  const [facets, setFacets] = useState<Facets>({});
  const [count, setCount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  // In-flight search; aborted when a newer one starts or on unmount.
  const inFlight = useRef<AbortController | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const firstRun = useRef(true);
  // Latest callbacks without re-triggering searches when the parent re-renders.
  const onResultsRef = useRef(onResults);
  const onErrorRef = useRef(onError);
  useEffect(() => { onResultsRef.current = onResults; }, [onResults]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

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
      const total = typeof r.data?.count === "number" ? r.data.count : null;
      setFailed(false);
      setFacets(r.data?.facets || {});
      setCount(total);
      onResultsRef.current?.(r.data?.results || [], r.data?.facets || {}, total);
    } catch {
      // A superseded search is not a failure; leave the UI to the newer one.
      if (controller.signal.aborted) return;
      // Keep the facet chips so the filters can still be changed; report
      // the failure instead of an empty result list ("No matches").
      setFailed(true);
      setCount(null);
      onErrorRef.current?.();
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
          const entries = facetEntries(f.key, facets[f.key], filters[f.param]);
          if (entries.length === 0) return null;
          return (
            <div key={f.key}>
              <p className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">{f.label}</p>
              <div className="flex flex-wrap gap-1">
                {entries.map(([val, c]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => toggle("filters", f.param, val)}
                    aria-pressed={filters[f.param] === val}
                    className={`rounded-full border px-2 py-0.5 text-xs ${filters[f.param] === val ? "border-emerald-500 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200" : "border-border bg-muted text-foreground"}`}
                  >
                    {facetLabel(f.key, val)} <span className="text-muted-foreground">({c.toLocaleString("en-IN")})</span>
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
            placeholder={`Filter by ${humaniseKey(dim).toLowerCase()}…`}
            aria-label={`Filter by ${humaniseKey(dim).toLowerCase()}`}
            className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground"
          />
        ))}
      </div>

      {failed ? (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-xs text-red-700 dark:text-red-300">
          <span>Search is unavailable right now.</span>
          <button
            type="button"
            onClick={runNow}
            disabled={busy}
            className="rounded border border-border bg-muted px-2 py-0.5 font-medium text-foreground hover:bg-muted/70 disabled:opacity-40"
          >
            Retry
          </button>
        </div>
      ) : count !== null ? (
        <p className="text-xs text-muted-foreground">
          {count.toLocaleString("en-IN")} matching {count === 1 ? "question" : "questions"}
        </p>
      ) : null}
    </div>
  );
}
