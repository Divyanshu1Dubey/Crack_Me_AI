"use client";
/**
 * RelatedPYQs + SimilarQuestions panel.
 * ------------------------------------
 * Two side panels that show related / similar questions from the
 * existing Question.concept_id + topic similarity logic.  Both share
 * one component (different prop) so the visual style matches.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";

interface Item {
  id: number;
  year?: number | null;
  session?: string;
  question_text?: string;
  topic?: string;
}

interface Props {
  questionId: number;
  kind: "related_pyqs" | "related_topics";
  limit?: number;
}

export default function RelatedPanel({ questionId, kind, limit = 8 }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const path = kind === "related_pyqs"
      ? `/api/questions/${questionId}/ai/related_pyqs/?limit=${limit}`
      : `/api/questions/${questionId}/ai/related_topics/?limit=${limit}`;
    (async () => {
      try {
        const r = await api.get(path);
        if (alive) {
          setItems(kind === "related_pyqs" ? r.data?.related_pyqs || [] : r.data?.related_topics || []);
        }
      } catch {
        if (alive) setItems([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [questionId, kind, limit]);

  if (loading) {
    return <p className="text-xs text-slate-400">Loading {kind === "related_pyqs" ? "related PYQs" : "related topics"}…</p>;
  }
  if (items.length === 0) {
    return <p className="text-xs text-slate-500">No {kind === "related_pyqs" ? "related PYQs" : "related topics"} found.</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((it) => (
        <li key={it.id} className="rounded border border-slate-700/40 bg-slate-900/40 p-2 text-sm">
          {kind === "related_pyqs" ? (
            <Link href={`/questions/practice?id=${it.id}`} className="block">
              <span className="text-xs text-slate-400">{it.year ?? "—"} · #{it.id}</span>
              <p className="line-clamp-2 text-slate-100">{(it.question_text || "").slice(0, 160)}…</p>
            </Link>
          ) : (
            <span>
              <span className="text-xs text-slate-400">topic</span>
              <p className="text-slate-100">{(it as any).topic || `Topic #${it.id}`}</p>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
