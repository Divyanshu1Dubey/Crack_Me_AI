/**
 * ExplanationPanel — renders the rich, structured AI explanation payload
 * that `/ai/explain-answer/` returns (why-correct, why-wrong, mnemonic,
 * textbook reference, high-yield points, clinical pearls, exam tips,
 * PYQ frequency, similar PYQs).
 *
 * The text fields are AI-written markdown (`**bold**`, line breaks in a
 * mnemonic), rendered by AiMarkdown; short labels (tags, the textbook
 * reference) are shown as plain text without markdown markers.
 *
 * Centralised here so future layouts (a "study mode" card, an Anki
 * exporter, a print view) can all reuse the same visual contract.
 */
'use client';

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Sparkles, BookMarked, Brain } from 'lucide-react';
import { AiMarkdown } from '@/components/ai/AiMarkdown';
import { plainInline } from '@/lib/aiMarkdown';
import type { AIExplanation, AccentTone } from './types';
import { ACCENT_CLASSES } from './constants';

interface ExplanationPanelProps {
  explanation: AIExplanation;
}

/** Wrapper class for markdown inside the explanation blocks. */
const BLOCK_TEXT = 'min-w-0 break-words';

export function ExplanationPanel({ explanation }: ExplanationPanelProps) {
  const book = plainInline(explanation.textbook_reference?.book);
  const chapter = plainInline(explanation.textbook_reference?.chapter);
  const page = plainInline(explanation.textbook_reference?.page);
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
        {!explanation.error && explanation.offline && (
          <Badge variant="outline" className="ml-auto border-amber-500/40 text-amber-700 dark:text-amber-300">
            Offline · no AI model · not charged
          </Badge>
        )}
      </div>

      {!explanation.error && explanation.offline && explanation.offline_notice && (
        <p className="text-xs text-muted-foreground">{explanation.offline_notice}</p>
      )}

      <Separator />

      {/* Tags row */}
      <div className="flex flex-wrap gap-1.5">
        {explanation.category && <Badge variant="secondary">{plainInline(explanation.category)}</Badge>}
        {explanation.question_type && (
          <Badge variant="outline">{plainInline(explanation.question_type)}</Badge>
        )}
        {explanation.core_concept && (
          <Badge variant="outline" className="border-primary/30 text-primary whitespace-normal text-left">
            {plainInline(explanation.core_concept)}
          </Badge>
        )}
      </div>

      {explanation.why_correct && (
        <ExplanationBlock title="Why the correct answer is right" accent="emerald">
          {explanation.error ? (
            <p>{explanation.why_correct}</p>
          ) : (
            <AiMarkdown text={explanation.why_correct} className={BLOCK_TEXT} />
          )}
        </ExplanationBlock>
      )}

      {explanation.why_wrong && Object.keys(explanation.why_wrong).length > 0 && (
        <ExplanationBlock title="Why the other options are wrong" accent="red">
          <div className="space-y-1.5">
            {Object.entries(explanation.why_wrong).map(([k, v]) => (
              <div key={k} className="flex gap-1.5">
                <span className="font-semibold shrink-0">{k}:</span>
                <AiMarkdown text={v} className={`${BLOCK_TEXT} flex-1 text-muted-foreground`} />
              </div>
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
          <AiMarkdown text={explanation.mnemonic} className={`${BLOCK_TEXT} font-medium`} />
        </ExplanationBlock>
      )}

      {book && (
        <ExplanationBlock
          title="Textbook reference"
          accent="violet"
          icon={<BookMarked className="h-3.5 w-3.5" />}
        >
          <p className="font-semibold">{book}</p>
          {chapter && (
            <p className="text-xs text-muted-foreground">
              Chapter: {chapter}
            </p>
          )}
          {page && (
            <p className="text-xs text-muted-foreground">
              Page: {page}
            </p>
          )}
        </ExplanationBlock>
      )}

      {explanation.high_yield_points && explanation.high_yield_points.length > 0 && (
        <ExplanationBlock title="High-yield points" accent="pink">
          <ul className="list-disc pl-5 space-y-0.5">
            {explanation.high_yield_points.map((p, i) => (
              <li key={i}>
                <AiMarkdown text={p} className={BLOCK_TEXT} />
              </li>
            ))}
          </ul>
        </ExplanationBlock>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {explanation.clinical_pearl && (
          <ExplanationBlock title="Clinical pearl" accent="emerald">
            <AiMarkdown text={explanation.clinical_pearl} className={BLOCK_TEXT} />
          </ExplanationBlock>
        )}
        {explanation.exam_tip && (
          <ExplanationBlock title="Exam tip" accent="amber">
            <AiMarkdown text={explanation.exam_tip} className={BLOCK_TEXT} />
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
              {plainInline(explanation.pyq_frequency)}
            </div>
          )}
          {explanation.similar_pyq && (
            <div className="text-xs p-2.5 rounded-md bg-indigo-500/10 border border-indigo-500/20">
              <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                Similar PYQs:{' '}
              </span>
              {plainInline(explanation.similar_pyq)}
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
      <div className="min-w-0">{children}</div>
    </div>
  );
}
