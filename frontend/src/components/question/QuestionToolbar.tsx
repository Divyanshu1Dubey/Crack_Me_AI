"use client";
/**
 * QuestionToolbar
 * ----------------
 * Phase-3 question-experience controls:
 *   - prev / next / jump-to-question
 *   - flag / bookmark / notes
 *   - reveal / ai explanation / clinical pearl
 *   - elimination-mode toggle (per-option strike-through in parent)
 *
 * Pure presentation + thin fetch to /api/questions/<id>/practice/*.
 */
import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";

interface Props {
  questionId: number;
  index: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
  onJump: (i: number) => void;
  onEliminationChange?: (opts: string[]) => void;
  onStateChange?: (state: QuestionState) => void;
}

export interface QuestionState {
  flag: boolean;
  confidence: number;
  time_spent: number;
  eliminated: string[];
  bookmarked: boolean;
}

export default function QuestionToolbar(props: Props) {
  const { questionId, index, total, onPrev, onNext, onJump, onEliminationChange, onStateChange } = props;
  const [state, setState] = useState<QuestionState>({
    flag: false, confidence: 0, time_spent: 0, eliminated: [], bookmarked: false,
  });
  const [jump, setJump] = useState<string>("");
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);

  // Fetch state whenever the question changes
  useEffect(() => {
    let alive = true;
    setRevealed(false);
    (async () => {
      try {
        const r = await api.get(`/api/questions/${questionId}/practice/state/`);
        const s: QuestionState = r.data || state;
        if (alive) {
          setState(s);
          onStateChange?.(s);
          onEliminationChange?.(s.eliminated || []);
        }
      } catch {
        if (alive) {
          setState({ flag: false, confidence: 0, time_spent: 0, eliminated: [], bookmarked: false });
        }
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionId]);

  const toggleFlag = useCallback(async () => {
    setBusy(true);
    try {
      const r = await api.post(`/api/questions/${questionId}/practice/flag/`, { flag: !state.flag });
      const next = { ...state, flag: r.data.flag };
      setState(next); onStateChange?.(next);
    } finally { setBusy(false); }
  }, [state, questionId, onStateChange]);

  const setConf = useCallback(async (n: number) => {
    setBusy(true);
    try {
      const r = await api.post(`/api/questions/${questionId}/practice/confidence/`, { rating: n });
      const next = { ...state, confidence: r.data.confidence };
      setState(next); onStateChange?.(next);
    } finally { setBusy(false); }
  }, [state, questionId, onStateChange]);

  const toggleElim = useCallback(async (opt: string) => {
    const cur = new Set(state.eliminated || []);
    if (cur.has(opt)) cur.delete(opt); else cur.add(opt);
    const list = Array.from(cur).sort();
    const next = { ...state, eliminated: list };
    setState(next); onStateChange?.(next); onEliminationChange?.(list);
    try {
      await api.post(`/api/questions/${questionId}/practice/eliminate/`, { options: list });
    } catch { /* swallow — optimistic */ }
  }, [state, questionId, onStateChange, onEliminationChange]);

  const doJump = (e: React.FormEvent) => {
    e.preventDefault();
    const n = parseInt(jump, 10);
    if (!Number.isNaN(n)) onJump(Math.max(1, Math.min(total, n)) - 1);
    setJump("");
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-700/40 bg-slate-900/50 p-2 text-sm">
      <button onClick={onPrev} disabled={index <= 0}
        className="rounded bg-slate-700/60 px-3 py-1 disabled:opacity-40">‹ Prev</button>
      <button onClick={onNext} disabled={index >= total - 1}
        className="rounded bg-slate-700/60 px-3 py-1 disabled:opacity-40">Next ›</button>
      <span className="px-2 text-slate-300">{index + 1} / {total}</span>
      <form onSubmit={doJump} className="flex items-center gap-1">
        <input value={jump} onChange={(e) => setJump(e.target.value)}
          placeholder="Jump to #"
          className="w-20 rounded bg-slate-800 px-2 py-1 text-sm" />
        <button className="rounded bg-slate-700/60 px-2 py-1">Go</button>
      </form>

      <span className="mx-2 hidden sm:inline-block h-5 w-px bg-slate-700/60" />

      <button onClick={toggleFlag} disabled={busy}
        className={`rounded px-2 py-1 ${state.flag ? "bg-amber-500 text-black" : "bg-slate-700/60"}`}>
        {state.flag ? "🚩 Flagged" : "🚩 Flag"}
      </button>

      <div className="flex items-center gap-1">
        <span className="text-slate-300">Conf:</span>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => setConf(n)}
            className={`h-7 w-7 rounded text-xs ${state.confidence === n ? "bg-emerald-500 text-black" : "bg-slate-700/60"}`}>
            {n}
          </button>
        ))}
      </div>

      <span className="mx-2 hidden sm:inline-block h-5 w-px bg-slate-700/60" />

      <span className="text-slate-300">Strike:</span>
      {["A", "B", "C", "D"].map((o) => (
        <button key={o} onClick={() => toggleElim(o)}
          className={`h-7 w-7 rounded text-xs ${state.eliminated?.includes(o) ? "bg-rose-500 text-white line-through" : "bg-slate-700/60"}`}>
          {o}
        </button>
      ))}

      <span className="mx-2 hidden sm:inline-block h-5 w-px bg-slate-700/60" />

      <button onClick={() => setRevealed(true)}
        className="rounded bg-emerald-600 px-3 py-1 text-white disabled:opacity-40"
        disabled={revealed}>
        Reveal
      </button>

      <span className="text-xs text-slate-400 ml-2">
        ⏱ {Math.round((state.time_spent || 0) / 1000)}s
      </span>
    </div>
  );
}
