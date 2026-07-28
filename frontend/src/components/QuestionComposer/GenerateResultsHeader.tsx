/**
 * GenerateResultsHeader — results counter + Regenerate button + score
 * card. Pure presentation; the parent computes the counts.
 */
'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Award, RefreshCw } from 'lucide-react';

interface GenerateResultsHeaderProps {
  total: number;
  answeredCount: number;
  regenerating: boolean;
  onRegenerate: () => void;
}

export function GenerateResultsHeader({
  total,
  answeredCount,
  regenerating,
  onRegenerate,
}: GenerateResultsHeaderProps) {
  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <div>
        <h2 className="text-lg font-bold flex items-center gap-2">
          <Award className="h-5 w-5 text-primary" />
          {total} Questions generated
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          {answeredCount === 0
            ? 'Pick an option on each card to reveal the AI explanation.'
            : `Answered ${answeredCount} of ${total}.`}
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onRegenerate}
        disabled={regenerating}
        className="gap-1"
      >
        <RefreshCw className="h-3.5 w-3.5" /> Regenerate
      </Button>
    </div>
  );
}

interface ScoreCardProps {
  correctCount: number;
  total: number;
}

export function ScoreCard({ correctCount, total }: ScoreCardProps) {
  const pct = Math.round((correctCount / total) * 100);
  const strong = correctCount >= Math.ceil(total * 0.7);
  return (
    <Card>
      <CardContent className="p-6 text-center">
        <div className="text-4xl font-bold text-primary">
          {correctCount} / {total}
        </div>
        <div className="text-sm text-muted-foreground mt-1">
          Score —{' '}
          <span className="font-semibold text-foreground">{pct}%</span>
          {' · '}
          {strong
            ? 'Strong performance on this topic'
            : 'Re-read the explanations and try Regenerate'}
        </div>
      </CardContent>
    </Card>
  );
}