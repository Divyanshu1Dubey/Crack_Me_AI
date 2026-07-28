/**
 * useGenerate — single source of truth for the AI question generator.
 *
 * State machine:
 *   idle ──generate()──► generating ──success──► done
 *                       └─error──► error ──clearError()──► idle
 *                       └─abort()──────────────────────► idle
 *
 * Holds:
 *   - the generated question bank
 *   - per-question selected answers
 *   - per-question show-explanation toggles
 *   - per-question AI deep-explanations + which one is currently loading
 *   - a top-level error banner for 429 / network failures
 *   - a progress percentage that animates 0 → 92 while generating, then
 *     snaps to 100 when the request resolves
 *
 * The page component only renders; it doesn't own state. This lets us
 * unit-test the state machine (when we add tests) and keeps each render
 * tree stable across re-renders.
 */
'use client';

import { useCallback, useEffect, useReducer, useRef } from 'react';
import { aiAPI } from '@/lib/api';
import type {
  AIExplanation,
  Difficulty,
  GeneratedQuestion,
} from './types';

type Status = 'idle' | 'generating' | 'done' | 'error';

interface State {
  status: Status;
  progress: number;
  questions: GeneratedQuestion[];
  selectedAnswers: Record<number, string>;
  showExplanations: Record<number, boolean>;
  aiExplanations: Record<number, AIExplanation>;
  aiLoadingIdx: number | null;
  errorBanner: string | null;
}

type Action =
  | { type: 'GENERATE_START' }
  | { type: 'GENERATE_PROGRESS'; progress: number }
  | { type: 'GENERATE_SUCCESS'; questions: GeneratedQuestion[] }
  | { type: 'GENERATE_FAIL'; banner: string }
  | { type: 'SELECT_ANSWER'; qIdx: number; option: string }
  | { type: 'SET_AI_LOADING'; idx: number | null }
  | { type: 'SET_AI_EXPLANATION'; idx: number; explanation: AIExplanation }
  | { type: 'CLEAR_ERROR' }
  | { type: 'RESET' };

const INITIAL: State = {
  status: 'idle',
  progress: 0,
  questions: [],
  selectedAnswers: {},
  showExplanations: {},
  aiExplanations: {},
  aiLoadingIdx: null,
  errorBanner: null,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'GENERATE_START':
      return {
        ...state,
        status: 'generating',
        progress: 0,
        questions: [],
        selectedAnswers: {},
        showExplanations: {},
        aiExplanations: {},
        aiLoadingIdx: null,
        errorBanner: null,
      };
    case 'GENERATE_PROGRESS':
      return { ...state, progress: action.progress };
    case 'GENERATE_SUCCESS':
      return { ...state, status: 'done', progress: 100, questions: action.questions };
    case 'GENERATE_FAIL':
      return { ...state, status: 'error', progress: 0, errorBanner: action.banner };
    case 'SELECT_ANSWER':
      return {
        ...state,
        selectedAnswers: { ...state.selectedAnswers, [action.qIdx]: action.option },
        showExplanations: { ...state.showExplanations, [action.qIdx]: true },
      };
    case 'SET_AI_LOADING':
      return { ...state, aiLoadingIdx: action.idx };
    case 'SET_AI_EXPLANATION':
      return {
        ...state,
        aiExplanations: { ...state.aiExplanations, [action.idx]: action.explanation },
      };
    case 'CLEAR_ERROR':
      return { ...state, status: 'idle', errorBanner: null };
    case 'RESET':
      return INITIAL;
  }
}

export interface UseGenerateApi {
  /** True only while the AI request is in flight. */
  generating: boolean;
  /** 0-100, animated while generating then snaps to 100 on success. */
  progress: number;
  /** Successful bank (already filtered to drop `error`-tagged rows). */
  questions: GeneratedQuestion[];
  /** idx → option letter picked (or undefined). Locks further picks. */
  selectedAnswers: Record<number, string>;
  /** idx → true once picked. */
  showExplanations: Record<number, boolean>;
  /** idx → structured AI explanation payload. */
  aiExplanations: Record<number, AIExplanation>;
  /** idx currently fetching an explanation, or null. */
  aiLoadingIdx: number | null;
  /** Top-of-page error message. */
  errorBanner: string | null;
  /** Run a new generation; resets prior answers + explanations. */
  generate: (payload: { subject: string; topic?: string; difficulty: Difficulty; count: number }) => Promise<void>;
  /** Lock an answer (no-op if already locked) and fire the AI explanation fetch. */
  pickAnswer: (qIdx: number, option: string) => void;
  /** Drop the error banner and return to the idle composer. */
  clearError: () => void;
  /** Wipe everything back to a clean slate. */
  reset: () => void;
}

export function useGenerate(): UseGenerateApi {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const progressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  /** Animated progress ticker — 0 → 92 while generating, gives up at 92. */
  useEffect(() => {
    if (state.status !== 'generating') {
      if (progressTimerRef.current) {
        clearTimeout(progressTimerRef.current);
        progressTimerRef.current = null;
      }
      return;
    }
    let pct = state.progress;
    const tick = () => {
      pct = Math.min(pct + Math.random() * 7 + 3, 92);
      dispatch({ type: 'GENERATE_PROGRESS', progress: pct });
      if (pct < 92) {
        progressTimerRef.current = setTimeout(tick, 350);
      }
    };
    progressTimerRef.current = setTimeout(tick, 200);
    return () => {
      if (progressTimerRef.current) clearTimeout(progressTimerRef.current);
    };
    // We intentionally don't re-run on `progress` change — the timer
    // owns its own reading of the latest value via the closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status]);

  const generate = useCallback<UseGenerateApi['generate']>(async (payload) => {
    dispatch({ type: 'GENERATE_START' });
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await aiAPI.generateQuestions(payload);
      const rows = (res.data?.questions ?? []) as GeneratedQuestion[];
      const clean = rows.filter((q) => !q.error);
      dispatch({ type: 'GENERATE_SUCCESS', questions: clean });
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const e = err as { response?: { status?: number; data?: { error?: string } }; message?: string };
      let banner: string;
      if (e?.response?.status === 429) {
        banner =
          'AI tokens exhausted — your daily/weekly free quota is used up. ' +
          'Visit /subscription or /tokens to top up.';
      } else {
        const msg = e?.response?.data?.error || e?.message || 'AI service unavailable';
        banner = `${msg}. Please try again.`;
      }
      dispatch({ type: 'GENERATE_FAIL', banner });
    } finally {
      abortRef.current = null;
    }
  }, []);

  // We need fresh state in pickAnswer without re-binding the consumer
  // callback every render. Use a ref:
  const stateRef = useRef(state);
  stateRef.current = state;
  const pickAnswerImpl = useCallback<UseGenerateApi['pickAnswer']>((qIdx, option) => {
    if (stateRef.current.selectedAnswers[qIdx]) return;
    dispatch({ type: 'SELECT_ANSWER', qIdx, option });
    const q = stateRef.current.questions[qIdx];
    if (!q) return;
    dispatch({ type: 'SET_AI_LOADING', idx: qIdx });
    aiAPI
      .explainAfterAnswer({
        question_text: q.question_text,
        options: { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d },
        correct_answer: q.correct_answer,
        selected_answer: option,
        subject: q.subject || '',
        topic: q.topic || '',
      })
      .then((res) =>
        dispatch({ type: 'SET_AI_EXPLANATION', idx: qIdx, explanation: res.data as AIExplanation }),
      )
      .catch((err) =>
        dispatch({
          type: 'SET_AI_EXPLANATION',
          idx: qIdx,
          explanation: {
            why_correct: err?.response?.data?.error || 'AI unavailable',
            error: true,
          },
        }),
      )
      .finally(() => dispatch({ type: 'SET_AI_LOADING', idx: null }));
  }, []);

  const clearError = useCallback(() => dispatch({ type: 'CLEAR_ERROR' }), []);
  const reset = useCallback(() => dispatch({ type: 'RESET' }), []);

  return {
    generating: state.status === 'generating',
    progress: state.progress,
    questions: state.questions,
    selectedAnswers: state.selectedAnswers,
    showExplanations: state.showExplanations,
    aiExplanations: state.aiExplanations,
    aiLoadingIdx: state.aiLoadingIdx,
    errorBanner: state.errorBanner,
    generate,
    pickAnswer: pickAnswerImpl,
    clearError,
    reset,
  };
}

// Re-export so unit tests can poke the reducer directly.
export const __test = { INITIAL, reducer };
