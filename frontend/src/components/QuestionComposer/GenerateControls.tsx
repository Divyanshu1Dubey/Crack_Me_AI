/**
 * GenerateControls — the composer card with subject, topic, difficulty,
 * count, cost preview, generate button, and progress bar.
 *
 * The parent owns `selectedSubject`, `topic`, etc. The batch limit comes from
 * `useGenerationLimit` (limits.ts): 15 and 20 questions per batch are for
 * unlimited-AI users (1-year plan, admins); for everyone else they are listed
 * as locked 1-year plan options that open the upgrade modal instead of being
 * picked, and the backend refuses them too (403 upgrade_required, no charge).
 */
'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Coins, ChevronDown, Infinity as InfinityIcon, Loader2, Lock, Sparkles, Target } from 'lucide-react';
import { usePaywall } from '@/lib/paywall/paywallContext';
import {
  DIFFICULTY_OPTIONS,
  EXPLANATION_TOKEN_COST,
  GENERATION_TOKEN_COST,
} from './constants';
import { LARGE_BATCH_FEATURE, PREMIUM_MAX_COUNT, countOptions, isCountLocked } from './limits';
import { useGenerationLimit } from './useGenerationLimit';
import type { Difficulty } from './types';

interface GenerateControlsProps {
  subjectOptions: string[];
  selectedSubject: string;
  onSubjectChange: (s: string) => void;
  topic: string;
  onTopicChange: (t: string) => void;
  difficulty: Difficulty;
  onDifficultyChange: (d: Difficulty) => void;
  count: number;
  onCountChange: (n: number) => void;
  generating: boolean;
  progress: number;
  onGenerate: () => void;
}

export function GenerateControls({
  subjectOptions,
  selectedSubject,
  onSubjectChange,
  topic,
  onTopicChange,
  difficulty,
  onDifficultyChange,
  count,
  onCountChange,
  generating,
  progress,
  onGenerate,
}: GenerateControlsProps) {
  const { unlimitedAi, maxCount } = useGenerationLimit();
  const { show: showPaywall } = usePaywall();
  // A count above the limit (e.g. the plan ended while the page was open)
  // opens the upgrade modal instead of a request the backend would refuse.
  const countLocked = isCountLocked(count, unlimitedAi);

  const handleCountChange = (value: string) => {
    const n = Number(value);
    if (isCountLocked(n, unlimitedAi)) {
      // The select is controlled, so it stays on the current count.
      showPaywall(LARGE_BATCH_FEATURE);
      return;
    }
    onCountChange(n);
  };

  const handleGenerate = () => {
    if (countLocked) {
      showPaywall(LARGE_BATCH_FEATURE);
      return;
    }
    onGenerate();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Target className="h-5 w-5 text-primary" />
          Configure your quiz
        </CardTitle>
        <CardDescription>
          Pick a subject and (optionally) a sub-topic. We&apos;ll generate {count}{' '}
          fresh MCQs calibrated to {difficulty} difficulty.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Field label="Subject">
            <Select value={selectedSubject} onChange={(v) => onSubjectChange(v)}>
              {subjectOptions.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </Select>
          </Field>

          <Field label="Topic (optional)">
            <Input
              type="text"
              value={topic}
              onChange={(e) => onTopicChange(e.target.value)}
              placeholder="e.g., Cardiology, Vaccines"
            />
          </Field>

          <Field label="Difficulty">
            <Select value={difficulty} onChange={(v) => onDifficultyChange(v as Difficulty)}>
              {DIFFICULTY_OPTIONS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </Select>
          </Field>

          <Field label="Questions">
            <Select value={String(count)} onChange={handleCountChange}>
              {countOptions(unlimitedAi).map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
            <p className="flex items-start gap-1 text-[11px] leading-snug text-muted-foreground">
              {unlimitedAi ? (
                <>
                  <InfinityIcon className="h-3 w-3 mt-0.5 shrink-0 text-primary" aria-hidden="true" />
                  <span>Up to {maxCount} per batch on your plan.</span>
                </>
              ) : (
                <>
                  <Lock className="h-3 w-3 mt-0.5 shrink-0 text-amber-500" aria-hidden="true" />
                  <span>
                    Up to {maxCount} per batch.{' '}
                    <button
                      type="button"
                      onClick={() => showPaywall(LARGE_BATCH_FEATURE)}
                      className="font-semibold text-primary hover:underline"
                    >
                      {PREMIUM_MAX_COUNT} at once with the 1-year plan
                    </button>
                  </span>
                </>
              )}
            </p>
          </Field>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            {unlimitedAi ? (
              <>
                <InfinityIcon className="h-3.5 w-3.5 mt-0.5 shrink-0 text-primary" aria-hidden="true" />
                <span>
                  Cost:&nbsp;
                  <span className="font-semibold text-foreground">no tokens</span>
                  &nbsp;— your plan has unlimited AI: up to {maxCount} questions per batch, and AI
                  deep explanations are included.
                </span>
              </>
            ) : (
              <>
                <Coins className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" aria-hidden="true" />
                <span>
                  Cost:&nbsp;
                  <span className="font-semibold text-foreground">{GENERATION_TOKEN_COST} tokens per batch</span>
                  &nbsp;of up to {maxCount} questions. AI deep explanations are optional:{' '}
                  {EXPLANATION_TOKEN_COST} tokens each, only when you ask. The 1-year plan generates up
                  to {PREMIUM_MAX_COUNT} per batch with no tokens.
                </span>
              </>
            )}
          </div>
          <Button onClick={handleGenerate} disabled={generating} size="lg" className="gap-2 shrink-0">
            {generating ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
            ) : countLocked ? (
              <><Lock className="h-4 w-4" /> Unlock {count} per batch</>
            ) : (
              <><Sparkles className="h-4 w-4" /> Generate Questions</>
            )}
          </Button>
        </div>

        {generating && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>AI is composing questions…</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ---------- private bits ---------- */

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

function Select({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded-md border bg-background text-sm appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        {children}
      </select>
      <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground" />
    </div>
  );
}
