/**
 * QuestionCard — single MCQ card with options, inline explanation, and
 * the deep AI explanation loader. Owns no state; the parent
 * `useGenerate` hook drives every interaction.
 */
'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import type { GeneratedQuestion, AIExplanation } from './types';
import { ExplanationPanel } from './ExplanationPanel';

interface QuestionCardProps {
  index: number;
  question: GeneratedQuestion;
  selectedAnswer?: string;
  showExplanation: boolean;
  aiExplanation?: AIExplanation;
  aiLoading: boolean;
  onPickAnswer: (qIdx: number, option: string) => void;
}

const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const;

export function QuestionCard({
  index,
  question,
  selectedAnswer,
  showExplanation,
  aiExplanation,
  aiLoading,
  onPickAnswer,
}: QuestionCardProps) {
  const correct = question.correct_answer;

  const optionClass = (optKey: string): string => {
    if (!selectedAnswer) {
      return 'border-border bg-card hover:bg-accent/40 hover:border-primary/40 cursor-pointer transition-all';
    }
    if (optKey === correct) {
      return 'border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/30';
    }
    if (optKey === selectedAnswer) {
      return 'border-red-500 bg-red-500/10 ring-1 ring-red-500/30';
    }
    return 'border-border bg-card/40 opacity-50';
  };

  return (
    <Card>
      <CardContent className="p-5 md:p-6 space-y-4">
        <div className="flex items-start gap-3">
          <span className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold bg-primary text-primary-foreground">
            {index + 1}
          </span>
          <div className="flex-1 min-w-0">
            <p className="font-medium leading-relaxed">{question.question_text}</p>
            <div className="flex gap-1.5 mt-2 flex-wrap">
              <Badge variant="secondary">{question.subject}</Badge>
              {question.topic && <Badge variant="outline">{question.topic}</Badge>}
              <Badge variant="outline" className="text-[10px] uppercase">
                {question.difficulty}
              </Badge>
            </div>
          </div>
        </div>

        <div className="space-y-2 ml-0 md:ml-12">
          {OPTION_KEYS.map((opt) => {
            const optValue = question[`option_${opt.toLowerCase()}` as keyof GeneratedQuestion] as string;
            if (!optValue) return null;
            return (
              <div
                key={opt}
                onClick={() => onPickAnswer(index, opt)}
                className={`p-3 rounded-lg border flex items-center gap-3 ${optionClass(opt)}`}
                role="button"
                tabIndex={selectedAnswer ? -1 : 0}
                aria-pressed={selectedAnswer === opt}
                aria-label={`Option ${opt}: ${optValue}`}
              >
                <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border shrink-0">
                  {opt}
                </span>
                <span className="text-sm flex-1">{optValue}</span>
                {selectedAnswer && opt === correct && (
                  <CheckCircle className="h-5 w-5 text-emerald-500 shrink-0" />
                )}
                {selectedAnswer === opt && opt !== correct && (
                  <XCircle className="h-5 w-5 text-red-500 shrink-0" />
                )}
              </div>
            );
          })}
        </div>

        {showExplanation && question.explanation && (
          <div className="ml-0 md:ml-12 rounded-lg border bg-muted/40 p-4">
            <div className="text-xs font-bold uppercase tracking-wide text-primary mb-1">
              Why this answer
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {question.explanation}
            </p>
          </div>
        )}

        {aiLoading && (
          <div className="ml-0 md:ml-12 flex items-center gap-2 text-xs text-primary animate-pulse">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            AI is preparing a deep analysis…
          </div>
        )}

        {aiExplanation && (
          <div className="ml-0 md:ml-12">
            <ExplanationPanel explanation={aiExplanation} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}