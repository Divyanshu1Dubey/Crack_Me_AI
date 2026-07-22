"use client";
/**
 * RecallBadge
 * -----------
 * Small pill that surfaces Question.recall_status so a learner can
 * spot recall / coaching-compiled / official questions at a glance.
 */
import type { ReactNode } from "react";

const LABELS: Record<string, { label: string; tone: string }> = {
  recall: { label: "Recall", tone: "bg-amber-500/80 text-black" },
  coaching_compiled: { label: "Coaching Compiled", tone: "bg-violet-500/80 text-white" },
  official_compiled: { label: "Official", tone: "bg-emerald-500/80 text-black" },
};

export default function RecallBadge({ status }: { status?: string | null }) {
  if (!status) return null;
  const meta = LABELS[status] || { label: status, tone: "bg-slate-500/80 text-white" };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${meta.tone}`}
      title={`Source provenance: ${meta.label}`}
      aria-label={`Recall status: ${meta.label}`}
    >
      {meta.label as ReactNode}
    </span>
  );
}
