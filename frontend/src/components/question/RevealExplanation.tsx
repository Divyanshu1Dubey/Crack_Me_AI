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
 * When the hourly AI generation budget is spent a tier answers
 * `{<field>: null, rate_limited: true}`: the panel says so instead of
 * silently leaving the AI sections out.
 *
 * The GETs never generate text themselves. A generated section (why correct,
 * clinical pearl, memory trick, concept) with nothing stored yet answers
 * HTTP 202 `{<field>: null, pending: true}` while one background job writes
 * the question's missing sections. Those sections show "Generating…" and only
 * they are fetched again, after each of PENDING_RETRY_DELAYS_MS, while the
 * panel stays open; closing it, moving to another question or unmounting
 * stops the retries. A section still pending after the last retry is dropped
 * with a short note, so nothing spins forever. `{<field>: null}` (nothing
 * stored, e.g. AI offline) and `{<field>: null, locked: true}` hide the
 * section.
 */
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import api from "@/lib/api";
import { FormattedText } from "@/components/FormattedText";
import { aiRateLimited, readAiField } from "@/components/question/practiceData";

interface Props {
  questionId: number;
  fallbackExplanation?: string;
  open: boolean;
  images?: Array<{ id: number; url?: string | null; file?: string | null; caption?: string | null }>;
}

/** Sections the background job generates: response field -> `ai/<path>/`. */
const SECTION_PATHS = {
  why_correct: "why_correct",
  clinical_significance: "clinical",
  memory_trick: "mnemonic",
  concept: "concept",
} as const;
type GeneratedField = keyof typeof SECTION_PATHS;
type SectionTexts = Record<GeneratedField, string>;
const NO_SECTION_TEXT: SectionTexts = { why_correct: "", clinical_significance: "", memory_trick: "", concept: "" };

/** Wait before each re-fetch of the pending sections: five tries, about 110 s
 *  in all, so one background generation (90 s provider deadline) can finish. */
const PENDING_RETRY_DELAYS_MS = [5000, 10000, 20000, 30000, 45000];

type AiResponse = { status?: number; data?: unknown };

interface SectionUpdate {
  /** Text that arrived, by field. */
  texts: Partial<SectionTexts>;
  /** Fields a background job is still writing. */
  pending: GeneratedField[];
  /** A response said the hourly generation budget is spent. */
  rateLimited: boolean;
  /** Sections were still pending after the last retry. */
  stalled: boolean;
}

/**
 * Reads the settled GETs of `fields` (same order). HTTP 202 or
 * `pending: true` means "still generating". A failed request counts as
 * pending while retrying (the next try may get through) and as an empty
 * section on the first load.
 */
function readSections(
  fields: GeneratedField[],
  results: PromiseSettledResult<AiResponse>[],
  retrying: boolean,
): SectionUpdate {
  const update: SectionUpdate = { texts: {}, pending: [], rateLimited: false, stalled: false };
  fields.forEach((field, i) => {
    const result = results[i];
    if (!result || result.status !== "fulfilled") {
      if (retrying) update.pending.push(field);
      return;
    }
    const value: AiResponse = result.value ?? {};
    const { status, data } = value;
    const text = readAiField(data, field);
    const flags = (data && typeof data === "object" ? data : {}) as { pending?: unknown; rate_limited?: unknown };
    if (text) update.texts[field] = text;
    else if (flags.pending === true || status === 202) update.pending.push(field);
    else if (flags.rate_limited === true) update.rateLimited = true;
  });
  return update;
}

/**
 * Fetches the pending sections again after each PENDING_RETRY_DELAYS_MS wait
 * until none is pending, reporting every try through `onUpdate`, plus a final
 * `stalled` update when some are still pending after the last try. Returns
 * as soon as `active()` is false (the caller cancels `sleep` at the same time).
 */
async function pollPendingSections(
  pending: GeneratedField[],
  fetchSection: (field: GeneratedField) => Promise<AiResponse>,
  sleep: (ms: number) => Promise<void>,
  active: () => boolean,
  onUpdate: (update: SectionUpdate) => void,
): Promise<void> {
  let left = pending;
  for (const delay of PENDING_RETRY_DELAYS_MS) {
    if (!left.length) return;
    await sleep(delay);
    if (!active()) return;
    const results = await Promise.allSettled(left.map((field) => fetchSection(field)));
    if (!active()) return;
    const update = readSections(left, results, true);
    left = update.pending;
    onUpdate(update);
  }
  if (left.length && active()) onUpdate({ texts: {}, pending: [], rateLimited: false, stalled: true });
}

export default function RevealExplanation({ questionId, fallbackExplanation, open, images }: Props) {
  const [sections, setSections] = useState<SectionTexts>(NO_SECTION_TEXT);
  const [importance, setImportance] = useState<number | null>(null);
  const [whyNot, setWhyNot] = useState<string>("");
  const [rateLimited, setRateLimited] = useState(false);
  const [pending, setPending] = useState<GeneratedField[]>([]);
  const [stalled, setStalled] = useState(false);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    // Clear the previous question's tiers while this one loads.
    setSections(NO_SECTION_TEXT); setImportance(null); setWhyNot("");
    setRateLimited(false); setPending([]); setStalled(false);

    const fetchSection = (field: GeneratedField) => api.get(`/questions/${questionId}/ai/${SECTION_PATHS[field]}/`);
    const sleep = (ms: number) => new Promise<void>((resolve) => { retryTimer = setTimeout(resolve, ms); });
    const apply = (update: SectionUpdate) => {
      if (Object.keys(update.texts).length) setSections((prev) => ({ ...prev, ...update.texts }));
      setPending(update.pending);
      if (update.rateLimited) setRateLimited(true);
      if (update.stalled) setStalled(true);
    };

    (async () => {
      // Each tier settles on its own so one failing endpoint doesn't
      // blank the others.
      const [a, c, m, e, w, wn] = await Promise.allSettled([
        fetchSection("why_correct"),
        fetchSection("clinical_significance"),
        fetchSection("memory_trick"),
        api.get(`/questions/${questionId}/ai/exam_importance/`),
        fetchSection("concept"),
        api.get(`/questions/${questionId}/ai/why_incorrect/`),
      ]);
      if (!alive) return;
      const body = (r: PromiseSettledResult<{ data?: unknown }>) => (r.status === "fulfilled" ? r.value?.data : null);
      const score = (body(e) as { exam_importance?: unknown } | null)?.exam_importance;
      setImportance(typeof score === "number" && Number.isFinite(score) ? score : null);
      // `w` is the concept response and `wn` the why_incorrect one (they
      // were swapped, so both sections always rendered empty).
      setWhyNot(readAiField(body(wn), "why_incorrect"));
      setRateLimited(aiRateLimited([a, c, m, e, w, wn].map(body)));
      const first = readSections(["why_correct", "clinical_significance", "memory_trick", "concept"], [a, c, m, w], false);
      apply(first);
      if (first.pending.length) await pollPendingSections(first.pending, fetchSection, sleep, () => alive, apply);
    })();
    return () => {
      alive = false;
      if (retryTimer !== undefined) clearTimeout(retryTimer);
    };
  }, [open, questionId]);

  if (!open) return null;

  const { concept, why_correct: ai, clinical_significance: clinical, memory_trick: memory } = sections;
  const generating = (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
      Generating…
    </p>
  );

  return (
    <div
      aria-busy={pending.length > 0}
      className="mt-3 space-y-3 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4 text-sm text-foreground"
    >
      {fallbackExplanation ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Explanation</p>
          <FormattedText text={fallbackExplanation} images={images} />
        </div>
      ) : null}

      {concept || pending.includes("concept") ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Concept</p>
          {concept ? <p>{concept}</p> : generating}
        </div>
      ) : null}
      {ai || pending.includes("why_correct") ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Why this is correct</p>
          {ai ? <p className="whitespace-pre-wrap">{ai}</p> : generating}
        </div>
      ) : null}
      {whyNot ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Why the distractors fail</p>
          <pre className="whitespace-pre-wrap font-sans text-sm">{whyNot}</pre>
        </div>
      ) : null}
      {clinical || pending.includes("clinical_significance") ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Clinical pearl</p>
          {clinical ? <p>{clinical}</p> : generating}
        </div>
      ) : null}
      {memory || pending.includes("memory_trick") ? (
        <div>
          <p className="mb-1 font-semibold text-emerald-700 dark:text-emerald-300">Memory trick</p>
          {memory ? <p>{memory}</p> : generating}
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
      {stalled ? (
        <p role="status" className="rounded border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          Some AI sections are taking longer than usual. Check back on this question later to see them.
        </p>
      ) : null}
      {rateLimited ? (
        <p role="status" className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-100">
          AI limit reached for this hour. The missing AI sections can be generated again later.
        </p>
      ) : null}
    </div>
  );
}
