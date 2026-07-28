/**
 * GenerateEmptyState — shown when no questions are loaded and nothing is
 * generating. Encourages the user to click the generate button.
 */
'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Sparkles } from 'lucide-react';
import type { TrackMeta } from './constants';

interface GenerateEmptyStateProps {
  count: number;
  trackMeta: TrackMeta;
}

export function GenerateEmptyState({ count, trackMeta }: GenerateEmptyStateProps) {
  return (
    <Card>
      <CardContent className="p-12 text-center">
        <div className="mx-auto mb-4 rounded-full bg-primary/10 p-4 w-fit">
          <Sparkles className="h-10 w-10 text-primary" />
        </div>
        <h3 className="text-lg font-bold mb-2">No questions yet</h3>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          Pick a subject above and click{' '}
          <span className="font-medium text-foreground">Generate Questions</span>{' '}
          to create {count} AI-powered practice MCQs for{' '}
          <span className="font-medium text-foreground">{trackMeta.label}</span>.
        </p>
      </CardContent>
    </Card>
  );
}