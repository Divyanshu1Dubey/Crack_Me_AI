"use client";
/**
 * QuestionTimer
 * -------------
 * Auto-pause-aware per-question timer.  Emits cumulative time to the
 * backend on every unmount / question change.
 */
import { useEffect, useRef } from "react";
import api from "@/lib/api";

interface Props {
  questionId: number;
}

export default function QuestionTimer({ questionId }: Props) {
  // Initialise the ref lazily so the impure Date.now() call only runs
  // once per mount, not on every render. This satisfies the
  // react-hooks/purity rule without changing behaviour.
  const start = useRef<number | null>(null);

  useEffect(() => {
    start.current = Date.now();
    const flush = () => {
      if (start.current === null) return;
      const elapsed = Math.max(0, Date.now() - start.current);
      start.current = Date.now();
      const ms = Math.min(60_000, elapsed); // 60s cap per flush
      api.post(`/api/questions/${questionId}/practice/time/`, { seconds: Math.round(ms / 1000) })
        .catch(() => {/* swallow */});
    };
    const onVisibility = () => { if (document.hidden) flush(); };
    document.addEventListener("visibilitychange", onVisibility);
    const interval = setInterval(flush, 30_000);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
      flush();
    };
  }, [questionId]);

  return null;
}
