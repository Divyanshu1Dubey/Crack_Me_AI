/**
 * types.ts — Shared types for the AI Question Generator composer.
 *
 * Kept in its own file so future features (presets, history, modes) can
 * import the same shapes without going through `page.tsx`.
 */
export interface AIExplanation {
  category?: string;
  sub_category?: string;
  question_type?: string;
  core_concept?: string;
  why_correct?: string;
  why_wrong?: Record<string, string>;
  textbook_reference?: { book?: string; chapter?: string; page?: string; section?: string };
  mnemonic?: string;
  high_yield_points?: string[];
  around_concepts?: string[];
  clinical_pearl?: string;
  exam_tip?: string;
  pyq_frequency?: string;
  similar_pyq?: string;
  error?: boolean;
}

export interface GeneratedQuestion {
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_answer: string;
  explanation: string;
  difficulty: string;
  subject: string;
  topic: string;
  error?: string;
}

export interface ComposerSubject {
  id: number;
  name: string;
  code: string;
  exam_type?: string;
}

export type Difficulty = 'easy' | 'medium' | 'hard';
export type AccentTone = 'emerald' | 'red' | 'amber' | 'violet' | 'pink';

export type ExamTrack =
  | 'cms'
  | 'neet_pg'
  | 'ini_cet'
  | 'usmle'
  | 'fmge';

export interface GeneratePayload {
  subject: string;
  topic?: string;
  difficulty: Difficulty;
  count: number;
}

/** A snapshot persisted to localStorage for the user's recent runs. */
export interface GenerationHistoryEntry {
  id: string;
  track: ExamTrack | string;
  subject: string;
  topic?: string;
  difficulty: Difficulty;
  count: number;
  createdAt: number;
  /** First question text; lets the user recognise the run without re-opening. */
  preview: string;
}
