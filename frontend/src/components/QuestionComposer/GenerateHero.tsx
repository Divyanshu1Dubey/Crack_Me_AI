/**
 * GenerateHero — top-of-page brand card with track badge + tagline.
 * Pure presentation; no state.
 */
'use client';

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Sparkles, Zap } from 'lucide-react';
import type { TrackMeta } from './constants';

interface GenerateHeroProps {
  trackMeta: TrackMeta;
}

export function GenerateHero({ trackMeta }: GenerateHeroProps) {
  return (
    <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-card via-card to-primary/5 p-6 md:p-8">
      <div className="absolute -right-12 -top-12 h-48 w-48 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
      <div className="relative flex items-start gap-4">
        <div className="rounded-xl bg-primary/15 p-3 text-primary shrink-0">
          <Sparkles className="h-7 w-7" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
              AI Question Generator
            </h1>
            <Badge variant="secondary" className="gap-1">
              <Zap className="h-3 w-3" /> AI
            </Badge>
            <Badge variant="outline" className="gap-1 text-xs">
              {trackMeta.label}
            </Badge>
          </div>
          <p className="text-sm md:text-base text-muted-foreground">
            {trackMeta.tagline}. Every question costs 1 token — first 10 are free every day.
          </p>
        </div>
      </div>
    </div>
  );
}