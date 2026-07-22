"use client";
/**
 * Practice page — Phase-3 question experience.
 * Wires:
 *  - QuestionToolbar (prev/next/jump/flag/confidence/eliminate/reveal)
 *  - QuestionTimer (auto-pause aware)
 *  - RevealExplanation (3-tier AI reveal)
 *  - ImageGallery (lazy + zoom + captions)
 *  - ProvenanceList
 *  - RecallBadge
 *  - RelatedPanel (related_pyqs + related_topics)
 *
 * Uses existing /api/questions/{id}/practice/* endpoints and the new
 * /api/questions/practice_queue/ dispatcher (?mode=...).
 */
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { FormattedText } from "@/components/FormattedText";
import RecallBadge from "@/components/recall/RecallBadge";
import ImageGallery from "@/components/recall/ImageGallery";
import ProvenanceList from "@/components/recall/ProvenanceList";
import QuestionToolbar, { type QuestionState } from "@/components/question/QuestionToolbar";
import QuestionTimer from "@/components/question/QuestionTimer";
import RevealExplanation from "@/components/question/RevealExplanation";
import RelatedPanel from "@/components/question/RelatedPYQs";
import api from "@/lib/api";

interface QRow {
  id: number;
  question_text?: string;
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  correct_answer?: string;
  explanation?: string;
  page_screenshot?: string | null;
  recall_status?: string;
  year?: number;
  session?: string;
  subject_name?: string;
  topic_name?: string;
  is_image_based?: boolean;
  ai_explanation?: string;
  ai_mnemonic?: string;
  ai_clinical_pearl?: string;
}

const MODES: { k: string; label: string }[] = [
  { k: "random", label: "Random" },
  { k: "year_wise", label: "Year-wise" },
  { k: "subject_wise", label: "Subject-wise" },
  { k: "topic_wise", label: "Topic-wise" },
  { k: "weak_topics", label: "Weak topics" },
  { k: "bookmarked", label: "Bookmarked" },
  { k: "wrong", label: "Wrong" },
  { k: "image_only", label: "Image-only" },
  { k: "rapid_revision", label: "Rapid revision" },
  { k: "high_yield", label: "High yield" },
  { k: "clinical_cases", label: "Clinical cases" },
];

function PracticeInner() {
  const router = useRouter();
  const params = useSearchParams();
  const initialMode = params.get("mode") || "random";
  const initialId = Number(params.get("id")) || null;

  const [mode, setMode] = useState(initialMode);
  const [queue, setQueue] = useState<number[]>([]);
  const [idx, setIdx] = useState(0);
  const [q, setQ] = useState<QRow | null>(null);
  const [eliminated, setEliminated] = useState<string[]>([]);
  const [revealed, setRevealed] = useState(false);
  const [picked, setPicked] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const r = await api.get(`/api/questions/practice_queue/`, {
          params: { mode, count: 30 },
        });
        if (!alive) return;
        const ids: number[] = r.data?.question_ids || [];
        setQueue(ids);
        setIdx(initialId ? Math.max(0, ids.indexOf(initialId)) : 0);
      } catch {
        if (alive) setQueue([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const qid = queue[idx];

  useEffect(() => {
    if (!qid) { setQ(null); return; }
    let alive = true;
    (async () => {
      try {
        const r = await api.get(`/api/questions/${qid}/`);
        if (alive) setQ(r.data);
      } catch {
        if (alive) setQ(null);
      }
    })();
    setRevealed(false); setPicked(""); setEliminated([]);
    const u = new URL(window.location.href);
    u.searchParams.set("id", String(qid));
    u.searchParams.set("mode", mode);
    window.history.replaceState({}, "", u.toString());
    return () => { alive = false; };
  }, [qid, mode]);

  const submit = useCallback(async (answer: string) => {
    if (!q) return;
    setPicked(answer);
    setBusy(true);
    try {
      await api.post(`/api/questions/${q.id}/practice/attempt/`, { answer });
      setRevealed(true);
    } catch {/* swallow */} finally { setBusy(false); }
  }, [q]);

  const onState = useCallback((s: QuestionState) => {
    setEliminated(s.eliminated || []);
  }, []);

  const opts = useMemo(() => {
    if (!q) return [];
    return [
      { k: "A", v: q.option_a || "" },
      { k: "B", v: q.option_b || "" },
      { k: "C", v: q.option_c || "" },
      { k: "D", v: q.option_d || "" },
    ];
  }, [q]);

  const total = queue.length;

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 text-slate-100">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Practice</h1>
        <select value={mode} onChange={(e) => setMode(e.target.value)}
          className="rounded bg-slate-800 px-2 py-1 text-sm">
          {MODES.map((m) => <option key={m.k} value={m.k}>{m.label}</option>)}
        </select>
        <span className="text-xs text-slate-400">{total} questions</span>
      </header>

      {qid ? <QuestionTimer questionId={qid} /> : null}

      {q ? (
        <article className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <RecallBadge status={q.recall_status} />
            {q.year ? <span className="rounded bg-slate-700/60 px-2 py-0.5 text-xs">NEET PG {q.year}</span> : null}
            {q.session ? <span className="rounded bg-slate-700/60 px-2 py-0.5 text-xs">{q.session}</span> : null}
            {q.subject_name ? <span className="rounded bg-slate-700/60 px-2 py-0.5 text-xs">{q.subject_name}</span> : null}
            {q.topic_name ? <span className="rounded bg-slate-700/40 px-2 py-0.5 text-xs">{q.topic_name}</span> : null}
            {q.is_image_based ? <span className="rounded bg-sky-500/70 px-2 py-0.5 text-xs text-white">Image</span> : null}
          </div>

          <div className="my-3">
            <FormattedText text={q.question_text || ""} />
          </div>

          {q.id ? (
            <ImageGallery questionId={q.id} fallbackImage={q.page_screenshot} />
          ) : null}

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {opts.map((o) => {
              const isCorrect = (q.correct_answer || "").toUpperCase() === o.k;
              const isElim = eliminated.includes(o.k);
              const wasPicked = picked === o.k;
              return (
                <button
                  key={o.k}
                  onClick={() => submit(o.k)}
                  disabled={busy || !!picked}
                  className={`flex w-full items-start gap-3 rounded border p-3 text-left
                              ${isElim ? "opacity-40 line-through" : ""}
                              ${picked ? (isCorrect ? "border-emerald-500 bg-emerald-900/20" :
                                          wasPicked ? "border-rose-500 bg-rose-900/20" : "border-slate-700/40") : "border-slate-700/40 hover:bg-slate-800/60"}`}
                >
                  <span className="rounded bg-slate-700/60 px-2 py-0.5 text-sm font-bold">{o.k}</span>
                  <FormattedText text={o.v} />
                </button>
              );
            })}
          </div>

          <RevealExplanation
            questionId={q.id}
            fallbackExplanation={q.explanation}
            open={revealed}
          />

          <div className="mt-4">
            <QuestionToolbar
              questionId={q.id}
              index={idx}
              total={total}
              onPrev={() => setIdx(Math.max(0, idx - 1))}
              onNext={() => setIdx(Math.min(total - 1, idx + 1))}
              onJump={(i) => setIdx(i)}
              onEliminationChange={setEliminated}
              onStateChange={onState}
            />
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-300">Provenance</h3>
              <ProvenanceList questionId={q.id} />
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-300">Related PYQs</h3>
              <RelatedPanel questionId={q.id} kind="related_pyqs" />
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-300">Related topics</h3>
              <RelatedPanel questionId={q.id} kind="related_topics" />
            </section>
          </div>
        </article>
      ) : loading ? (
        <p className="text-slate-400">Building queue…</p>
      ) : (
        <p className="text-slate-400">No questions for this mode yet. Try another mode.</p>
      )}

      <p className="mt-6 text-center text-xs text-slate-500">
        Press <kbd className="rounded bg-slate-800 px-1">Esc</kbd> to clear reveals.
      </p>
    </main>
  );
}

export default function PracticePage() {
  return (
    <Suspense fallback={<p className="p-6 text-slate-400">Loading…</p>}>
      <PracticeInner />
    </Suspense>
  );
}
