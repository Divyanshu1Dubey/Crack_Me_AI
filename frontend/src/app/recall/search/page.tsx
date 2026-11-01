"use client";
/**
 * /recall/search — Phase-3 advanced search results page.
 * Pure client component: drives `RecallSearchBox` and shows results
 * inline. Uses the theme tokens so it reads in light and dark themes.
 */
import Link from "next/link";
import { useCallback, useState } from "react";
import RecallSearchBox from "@/components/recall/RecallSearchBox";
import RecallBadge from "@/components/recall/RecallBadge";
import { stripMarkdown } from "@/components/FormattedText";
import { sanitizeQuestionText } from "@/lib/textCleanup";

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

/** One-paragraph preview: no markdown markers or image tokens (line-clamp adds the ellipsis). */
function previewText(text: string | undefined): string {
  return stripMarkdown(sanitizeQuestionText(text))
    .replace(/\[\[img:\d+\]\]/g, " ")
    .replace(/__/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export default function RecallSearchPage() {
  const [rows, setRows] = useState<Row[]>([]);
  // 'loading' until the first search settles; 'error' after a failed one
  // (the search box shows the message and a Retry button).
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const onResults = useCallback((r: Row[]) => { setRows(r); setStatus("ok"); }, []);
  const onError = useCallback(() => { setRows([]); setStatus("error"); }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 text-foreground">
      <h1 className="mb-4 text-2xl font-semibold">Recall bank search</h1>
      <RecallSearchBox onResults={onResults} onError={onError} />

      <section className="mt-6 space-y-3" aria-live="polite">
        {rows.map((r) => (
          <article key={r.id} className="rounded-lg border border-border bg-card p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
              <RecallBadge status={r.recall_status} />
              {r.year ? <span className="rounded bg-muted px-2 py-0.5">{r.year}</span> : null}
              {r.subject_name ? <span className="rounded bg-muted px-2 py-0.5">{r.subject_name}</span> : null}
              {r.topic_name ? <span className="rounded bg-muted/60 px-2 py-0.5 text-muted-foreground">{r.topic_name}</span> : null}
              {r.difficulty ? <span className="rounded bg-amber-500/20 px-2 py-0.5 capitalize text-amber-900 dark:text-amber-200">{r.difficulty}</span> : null}
              <span className="ml-auto">
                <Link href={`/practice?id=${r.id}`} className="text-emerald-700 underline dark:text-emerald-300">
                  Practice →
                </Link>
              </span>
            </div>
            <p className="line-clamp-2 text-sm">{previewText(r.question_text)}</p>
          </article>
        ))}
        {status === "loading" && rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Searching…</p>
        ) : null}
        {status === "ok" && rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No matches. Try a broader keyword or clear a filter.</p>
        ) : null}
      </section>
    </div>
  );
}
