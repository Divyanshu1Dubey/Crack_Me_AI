"use client";
/**
 * RevealExplanation
 * -----------------
 * Phase-3 multi-tier reveal panel:
 *   tier 1 — question's own `explanation` field
 *   tier 2 — AI explanation
 *   tier 3 — clinical pearl + memory trick + exam importance
 *
 * All three tiers cache on the backend per the ai_per_question module.
 * When no AI output exists the backend returns canned template strings
 * (generic study tips); those are hidden rather than shown as analysis.
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { FormattedText } from "@/components/FormattedText";
import { readAiField } from "@/components/question/practiceData";

interface Props {
  questionId: number;
  fallbackExplanation?: string;
  open: boolean;
  images?: Array<{ id: number; url?: string | null; file?: string | null; caption?: string | null }>;
}

export default function RevealExplanation({ questionId, fallbackExplanation, open, images }: Props) {
  const [ai, setAi] = useState<string>("");
  const [clinical, setClinical] = useState<string>("");
  const [memory, setMemory] = useState<string>("");
  const [importance, setImportance] = useState<number | null>(null);
  const [concept, setConcept] = useState<string>("");
  const [whyNot, setWhyNot] = useState<string>("");

  useEffect(() => {
    if (!open) return;
    let alive = true;
    // Clear the previous question's tiers while this one loads.
    setAi(""); setClinical(""); setMemory(""); setImportance(null); setConcept(""); setWhyNot("");
    (async () => {
      // Each tier settles on its own so one failing endpoint doesn't
      // blank the others.
      const [a, c, m, e, w, wn] = await Promise.allSettled([
        api.get(`/questions/${questionId}/ai/why_correct/`),
        api.get(`/questions/${questionId}/ai/clinical/`),
        api.get(`/questions/${questionId}/ai/mnemonic/`),
        api.get(`/questions/${questionId}/ai/exam_importance/`),
        api.get(`/questions/${questionId}/ai/concept/`),
        api.get(`/questions/${questionId}/ai/why_incorrect/`),
      ]);
      if (!alive) return;
      const body = (r: PromiseSettledResult<{ data?: unknown }>) => (r.status === "fulfilled" ? r.value?.data : null);
      setAi(readAiField(body(a), "why_correct"));
      setClinical(readAiField(body(c), "clinical_significance"));
      setMemory(readAiField(body(m), "memory_trick"));
      const score = (body(e) as { exam_importance?: unknown } | null)?.exam_importance;
      setImportance(typeof score === "number" && Number.isFinite(score) ? score : null);
      // `w` is the concept response and `wn` the why_incorrect one (they
      // were swapped, so both sections always rendered empty).
      setConcept(readAiField(body(w), "concept"));
      setWhyNot(readAiField(body(wn), "why_incorrect"));
    })();
    return () => { alive = false; };
  }, [open, questionId]);

  if (!open) return null;

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4 text-sm text-foreground">
      {fallbackExplanation ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Explanation</p>
          <FormattedText text={fallbackExplanation} images={images} />
        </div>
      ) : null}

      {concept ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Concept</p>
          <p>{concept}</p>
        </div>
      ) : null}
      {ai ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Why this is correct</p>
          <p className="whitespace-pre-wrap">{ai}</p>
        </div>
      ) : null}
      {whyNot ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Why the distractors fail</p>
          <pre className="whitespace-pre-wrap font-sans text-sm">{whyNot}</pre>
        </div>
      ) : null}
      {clinical ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Clinical pearl</p>
          <p>{clinical}</p>
        </div>
      ) : null}
      {memory ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Memory trick</p>
          <p>{memory}</p>
        </div>
      ) : null}
      {importance != null ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Exam importance</p>
          <div className="h-2 w-full rounded bg-emerald-500/15">
            <div className="h-full rounded bg-emerald-500" style={{ width: `${Math.min(100, Math.max(0, importance))}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{importance}/100</p>
        </div>
      ) : null}
    </div>
  );
}
