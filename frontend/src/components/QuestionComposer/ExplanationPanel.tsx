/**
 * ExplanationPanel — renders the rich, structured AI explanation payload
 * that `/ai/explain-answer/` returns (why-correct, why-wrong, mnemonic,
 * textbook reference, high-yield points, clinical pearls, exam tips,
 * PYQ frequency, similar PYQs).
 *
 * Centralised here so future layouts (a "study mode" card, an Anki
 * exporter, a print view) can all reuse the same visual contract.
 */
'use client';

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Sparkles, BookMarked, Brain } from 'lucide-react';
import type { AIExplanation, AccentTone } from './types';
import { ACCENT_CLASSES } from './constants';

interface ExplanationPanelProps {
  explanation: AIExplanation;
}

export function ExplanationPanel({ explanation }: ExplanationPanelProps) {
  return (
    <div className="space-y-3 pt-2 border-t">
      <div className="flex items-center gap-2 pt-2">
        <Brain className="h-4 w-4 text-primary" />
        <span className="text-xs font-bold uppercase tracking-wide text-primary">
          AI Deep Explanation
        </span>
        {explanation.error && (
          <Badge variant="destructive" className="ml-auto">
            AI unavailable
          </Badge>
        )}
      </div>

      <Separator />

      {/* Tags row */}
      <div className="flex flex-wrap gap-1.5">
        {explanation.category && <Badge variant="secondary">{explanation.category}</Badge>}
        {explanation.question_type && (
          <Badge variant="outline">{explanation.question_type}</Badge>
        )}
        {explanation.core_concept && (
          <Badge variant="outline" className="border-primary/30 text-primary">
            {explanation.core_concept}
          </Badge>
        )}
      </div>

      {explanation.why_correct && (
        <ExplanationBlock title="Why the correct answer is right" accent="emerald">
          {explanation.why_correct}
        </ExplanationBlock>
      )}

      {explanation.why_wrong && Object.keys(explanation.why_wrong).length > 0 && (
        <ExplanationBlock title="Why the other options are wrong" accent="red">
          <div className="space-y-1">
            {Object.entries(explanation.why_wrong).map(([k, v]) => (
              <p key={k}>
                <span className="font-semibold">{k}:</span>{' '}
                <span className="text-muted-foreground">{String(v)}</span>
              </p>
            ))}
          </div>
        </ExplanationBlock>
      )}

      {explanation.mnemonic && (
        <ExplanationBlock
          title="Mnemonic"
          accent="amber"
          icon={<Sparkles className="h-3.5 w-3.5" />}
        >
          <span className="font-medium">{explanation.mnemonic}</span>
        </ExplanationBlock>
      )}

      {explanation.textbook_reference?.book && (
        <ExplanationBlock
          title="Textbook reference"
          accent="violet"
          icon={<BookMarked className="h-3.5 w-3.5" />}
        >
          <p className="font-semibold">{explanation.textbook_reference.book}</p>
          {explanation.textbook_reference.chapter && (
            <p className="text-xs text-muted-foreground">
              Chapter: {explanation.textbook_reference.chapter}
            </p>
          )}
          {explanation.textbook_reference.page && (
            <p className="text-xs text-muted-foreground">
              Page: {explanation.textbook_reference.page}
            </p>
          )}
        </ExplanationBlock>
      )}

      {explanation.high_yield_points && explanation.high_yield_points.length > 0 && (
        <ExplanationBlock title="High-yield points" accent="pink">
          <ul className="list-disc pl-5 space-y-0.5">
            {explanation.high_yield_points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </ExplanationBlock>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {explanation.clinical_pearl && (
          <ExplanationBlock title="Clinical pearl" accent="emerald">
            {explanation.clinical_pearl}
          </ExplanationBlock>
        )}
        {explanation.exam_tip && (
          <ExplanationBlock title="Exam tip" accent="amber">
            {explanation.exam_tip}
          </ExplanationBlock>
        )}
      </div>

      {(explanation.pyq_frequency || explanation.similar_pyq) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
          {explanation.pyq_frequency && (
            <div className="text-xs p-2.5 rounded-md bg-pink-500/10 border border-pink-500/20">
              <span className="font-semibold text-pink-600 dark:text-pink-400">
                PYQ frequency:{' '}
              </span>
              {explanation.pyq_frequency}
            </div>
          )}
          {explanation.similar_pyq && (
            <div className="text-xs p-2.5 rounded-md bg-indigo-500/10 border border-indigo-500/20">
              <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                Similar PYQs:{' '}
              </span>
              {explanation.similar_pyq}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ExplanationBlockProps {
  title: string;
  accent: AccentTone;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export function ExplanationBlock({ title, accent, icon, children }: ExplanationBlockProps) {
  return (
    <div className={`rounded-md border p-3 text-sm leading-relaxed ${ACCENT_CLASSES[accent]}`}>
      <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide mb-1.5">
        {icon}
        <span>{title}</span>
      </div>
      <div>{children}</div>
    </div>
  );
}