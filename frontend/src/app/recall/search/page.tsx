"use client";
/**
 * /recall/search — Phase-3 advanced search results page.
 * Pure client component: drives `RecallSearchBox` and shows results
 * inline.
 */
import Link from "next/link";
import { useState } from "react";
import RecallSearchBox from "@/components/recall/RecallSearchBox";
import RecallBadge from "@/components/recall/RecallBadge";

interface Row {
  id: number;
  question_text?: string;
  year?: number | null;
  session?: string;
  recall_status?: string;
  subject_name?: string;
  topic_name?: string;
  difficulty?: string;
}

export default function RecallSearchPage() {
  const [rows, setRows] = useState<Row[]>([]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-6 text-slate-100">
      <h1 className="mb-4 text-2xl font-semibold">Recall bank search</h1>
      <RecallSearchBox onResults={(r) => setRows(r)} />

      <section className="mt-6 space-y-3">
        {rows.map((r) => (
          <article key={r.id} className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
              <RecallBadge status={r.recall_status} />
              {r.year ? <span className="rounded bg-slate-700/60 px-2 py-0.5">{r.year}</span> : null}
              {r.subject_name ? <span className="rounded bg-slate-700/60 px-2 py-0.5">{r.subject_name}</span> : null}
              {r.topic_name ? <span className="rounded bg-slate-700/40 px-2 py-0.5">{r.topic_name}</span> : null}
              {r.difficulty ? <span className="rounded bg-amber-500/60 px-2 py-0.5 text-black">{r.difficulty}</span> : null}
              <span className="ml-auto">
                <Link href={`/practice?id=${r.id}`} className="text-emerald-300 underline">
                  Practice →
                </Link>
              </span>
            </div>
            <p className="line-clamp-2 text-sm">{(r.question_text || "").slice(0, 220)}…</p>
          </article>
        ))}
        {rows.length === 0 ? (
          <p className="text-sm text-slate-500">No matches yet. Try a broader keyword.</p>
        ) : null}
      </section>
    </main>
  );
}
