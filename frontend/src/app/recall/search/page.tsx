"use client";
/**
 * /recall/search — Phase-3 advanced search results page.
 * Pure client component: drives `RecallSearchBox` and shows results
 * inline. Uses the theme tokens so it reads in light and dark themes.
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
    <div className="mx-auto max-w-5xl px-4 py-6 text-foreground">
      <h1 className="mb-4 text-2xl font-semibold">Recall bank search</h1>
      <RecallSearchBox onResults={(r) => setRows(r)} />

      <section className="mt-6 space-y-3">
        {rows.map((r) => (
          <article key={r.id} className="rounded-lg border border-border bg-card p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
              <RecallBadge status={r.recall_status} />
              {r.year ? <span className="rounded bg-muted px-2 py-0.5">{r.year}</span> : null}
              {r.subject_name ? <span className="rounded bg-muted px-2 py-0.5">{r.subject_name}</span> : null}
              {r.topic_name ? <span className="rounded bg-muted/60 px-2 py-0.5 text-muted-foreground">{r.topic_name}</span> : null}
              {r.difficulty ? <span className="rounded bg-amber-500/20 px-2 py-0.5 text-amber-900 dark:text-amber-200">{r.difficulty}</span> : null}
              <span className="ml-auto">
                <Link href={`/practice?id=${r.id}`} className="text-emerald-700 underline dark:text-emerald-300">
                  Practice →
                </Link>
              </span>
            </div>
            <p className="line-clamp-2 text-sm">{(r.question_text || "").slice(0, 220)}…</p>
          </article>
        ))}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No matches yet. Try a broader keyword.</p>
        ) : null}
      </section>
    </div>
  );
}
