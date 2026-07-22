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
 */
import { useEffect, useState } from "react";
import api from "@/lib/api";

interface Props {
  questionId: number;
  fallbackExplanation?: string;
  open: boolean;
}

export default function RevealExplanation({ questionId, fallbackExplanation, open }: Props) {
  const [ai, setAi] = useState<string>("");
  const [clinical, setClinical] = useState<string>("");
  const [memory, setMemory] = useState<string>("");
  const [importance, setImportance] = useState<number | null>(null);
  const [why, setWhy] = useState<string>("");
  const [whyNot, setWhyNot] = useState<string>("");

  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      try {
        const [a, c, m, e, w, wn] = await Promise.all([
          api.get(`/api/questions/${questionId}/ai/why_correct/`),
          api.get(`/api/questions/${questionId}/ai/clinical/`),
          api.get(`/api/questions/${questionId}/ai/mnemonic/`),
          api.get(`/api/questions/${questionId}/ai/exam_importance/`),
          api.get(`/api/questions/${questionId}/ai/concept/`),
          api.get(`/api/questions/${questionId}/ai/why_incorrect/`),
        ]);
        if (!alive) return;
        setAi(a.data?.why_correct || "");
        setClinical(c.data?.clinical_significance || "");
        setMemory(m.data?.memory_trick || "");
        setImportance(e.data?.exam_importance ?? null);
        setWhy(wn.data?.concept || "");
        setWhyNot(w.data?.why_incorrect || "");
      } catch {
        // ignore — panel still works with fallback
      }
    })();
    return () => { alive = false; };
  }, [open, questionId]);

  if (!open) return null;

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-emerald-700/40 bg-emerald-900/10 p-4 text-sm text-emerald-100">
      {fallbackExplanation ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-300">Explanation</p>
          <p className="whitespace-pre-wrap leading-relaxed">{fallbackExplanation}</p>
        </div>
      ) : null}

      {why ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-300">Concept</p>
          <p>{why}</p>
        </div>
      ) : null}
      {ai ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-300">Why this is correct</p>
          <p className="whitespace-pre-wrap">{ai}</p>
        </div>
      ) : null}
      {whyNot ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-300">Why the distractors fail</p>
          <pre className="whitespace-pre-wrap font-sans text-sm">{whyNot}</pre>
        </div>
      ) : null}
      {clinical ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-300">Clinical pearl</p>
          <p>{clinical}</p>
        </div>
      ) : null}
      {memory ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-300">Memory trick</p>
          <p>{memory}</p>
        </div>
      ) : null}
      {importance != null ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-300">Exam importance</p>
          <div className="h-2 w-full rounded bg-emerald-900/60">
            <div className="h-full rounded bg-emerald-400" style={{ width: `${Math.min(100, importance)}%` }} />
          </div>
          <p className="mt-1 text-xs text-emerald-200/80">{importance}/100</p>
        </div>
      ) : null}
    </div>
  );
}
