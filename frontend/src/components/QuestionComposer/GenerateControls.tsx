/**
 * GenerateControls — the composer card with subject, topic, difficulty,
 * count, cost preview, generate button, and progress bar.
 *
 * Stateless: the parent owns `selectedSubject`, `topic`, etc.
 */
'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Coins, ChevronDown, Loader2, Sparkles, Target } from 'lucide-react';
import {
  COUNT_OPTIONS,
  DIFFICULTY_OPTIONS,
} from './constants';
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
            <Select value={String(count)} onChange={(v) => onCountChange(Number(v))}>
              {COUNT_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Coins className="h-3.5 w-3.5 text-amber-500" />
            <span>
              Estimated cost:&nbsp;
              <span className="font-semibold text-foreground">{count}</span>
              &nbsp;token{count > 1 ? 's' : ''} (1 per question + 1 per AI explanation)
            </span>
          </div>
          <Button onClick={onGenerate} disabled={generating} size="lg" className="gap-2">
            {generating ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
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