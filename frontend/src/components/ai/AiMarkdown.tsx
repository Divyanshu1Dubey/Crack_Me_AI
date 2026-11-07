/**
 * AiMarkdown — AI-written markdown (study plans, high-yield lists, generated MCQs, AI explanations)
 * rendered by the shared `FormattedText` renderer: GFM tables in a horizontally scrolling box,
 * `<br>` inside table cells, bold / italics, lists, unsafe HTML removed (lib/markdownSanitize).
 * `prepareAiMarkdown` (lib/aiMarkdown) first unwraps ```markdown fences and repairs the table shapes
 * models write, as the AI Tutor page does.
 */
'use client';

import { FormattedText } from '@/components/FormattedText';
import { prepareAiMarkdown } from '@/lib/aiMarkdown';
import { coerceToText } from '@/lib/textCleanup';

interface AiMarkdownProps {
  /** Usually a string; anything else is shown as text instead of crashing the card. */
  text: unknown;
  className?: string;
}

export function AiMarkdown({ text, className = '' }: AiMarkdownProps) {
  const source = coerceToText(text);
  if (!source.trim()) return null;
  return <FormattedText text={prepareAiMarkdown(source)} className={className} />;
}

export default AiMarkdown;
