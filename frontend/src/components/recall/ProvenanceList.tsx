"use client";
/**
 * ProvenanceList
 * --------------
 * Phase-3 component that renders every QuestionSource row attached to
 * a question (filename + sha16 + page + extraction confidence).  Lets
 * a learner trust the recall source.
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";

interface SourceRow {
  id: number;
  page_number: number;
  question_number_in_pdf?: number | null;
  recall_source_filename?: string;
  recall_source_sha16?: string;
  ocr_confidence?: number | null;
  extraction_confidence?: number | string | null;
  import_job_id?: string;
  imported_at?: string;
}

interface Props {
  questionId: number;
}

export default function ProvenanceList({ questionId }: Props) {
  const [rows, setRows] = useState<SourceRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.get(`/api/questions/${questionId}/sources/`);
        if (alive) setRows(r.data || []);
      } catch (e: any) {
        if (alive) setErr(e?.message || "Failed to load provenance");
      }
    })();
    return () => { alive = false; };
  }, [questionId]);

  if (err) return <p className="text-sm text-rose-300">Provenance unavailable: {err}</p>;
  if (!rows) return <p className="text-sm text-slate-400">Loading provenance…</p>;
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No recall source attached.</p>;
  }
  return (
    <ul className="divide-y divide-slate-700/40 rounded border border-slate-700/40 bg-slate-900/40">
      {rows.map((r) => (
        <li key={r.id} className="px-3 py-2 text-sm text-slate-200">
          <div className="flex items-center justify-between">
            <span className="font-mono">{r.recall_source_filename || `Source #${r.id}`}</span>
            <span className="text-xs text-slate-400">page {r.page_number}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-400">
            <span>sha16: <code>{r.recall_source_sha16}</code></span>
            {r.extraction_confidence != null ? (
              <span>extract conf: {Number(r.extraction_confidence).toFixed(2)}</span>
            ) : null}
            {r.ocr_confidence != null ? <span>OCR conf: {Number(r.ocr_confidence).toFixed(1)}</span> : null}
            {r.imported_at ? <span>imported {new Date(r.imported_at).toLocaleDateString()}</span> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
