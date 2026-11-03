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
import { normaliseRelatedTopics, type RelatedTopic } from "@/components/question/practiceData";

interface Item {
  id: number;
  year?: number | null;
  session?: string;
  question_text?: string;
}

interface Props {
  questionId: number;
  kind: "related_pyqs" | "related_topics";
  limit?: number;
}

export default function RelatedPanel({ questionId, kind, limit = 8 }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [topics, setTopics] = useState<RelatedTopic[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const path = kind === "related_pyqs"
      ? `/questions/${questionId}/ai/related_pyqs/?limit=${limit}`
      : `/questions/${questionId}/ai/related_topics/?limit=${limit}`;
    (async () => {
      try {
        const r = await api.get(path);
        if (alive) {
          if (kind === "related_pyqs") {
            setItems(Array.isArray(r.data?.related_pyqs) ? r.data.related_pyqs : []);
          } else {
            // Rows are `values('topic_id', 'topic__name')` + a count.
            setTopics(normaliseRelatedTopics(r.data?.related_topics));
          }
        }
      } catch {
        if (alive) { setItems([]); setTopics([]); }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [questionId, kind, limit]);

  if (loading) {
    return <p className="text-xs text-muted-foreground">Loading {kind === "related_pyqs" ? "related PYQs" : "related topics"}…</p>;
  }
  const empty = kind === "related_pyqs" ? items.length === 0 : topics.length === 0;
  if (empty) {
    return <p className="text-xs text-muted-foreground">No {kind === "related_pyqs" ? "related PYQs" : "related topics"} found.</p>;
  }
  if (kind === "related_topics") {
    return (
      <ul className="space-y-2">
        {topics.map((t) => (
          <li key={t.id} className="rounded border border-border bg-card p-2 text-sm">
            <span className="text-xs text-muted-foreground">topic{t.count != null ? ` · ${t.count} questions` : ""}</span>
            <p className="text-foreground">{t.name}</p>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((it) => (
        <li key={it.id} className="rounded border border-border bg-card p-2 text-sm">
          {/* /practice opens the requested id directly; /questions/practice
              needs a ?year= and bounced these links to /questions. */}
          <Link href={`/practice?id=${it.id}`} className="block hover:text-primary">
            <span className="text-xs text-muted-foreground">{it.year ?? "—"} · #{it.id}</span>
            <p className="line-clamp-2 text-foreground">{(it.question_text || "").slice(0, 160)}…</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
