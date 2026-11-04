'use client';
/**
 * StudentCitations
 * ----------------
 * The accepted references of a question, shown after the answer is revealed: title, edition, chapter,
 * page and a short excerpt (at most 240 characters) checked against the cited page by an editor.
 * Never a full page. Loads `GET /api/evidence/questions/<id>/citations/` only once `revealed` is true
 * (a citation names the option it supports). Renders nothing at all while loading, on an error, for a
 * locked question or when there are no references: references are an extra, never a placeholder.
 */
import { useEffect, useState } from 'react';
import { BookOpen } from 'lucide-react';
import { fetchStudentCitations } from '@/lib/evidenceAPI';
import { normalizeCitations, sourceLine, type StudentCitationView } from './citationRules';

const CACHE_LIMIT = 100;
// Successful answers per question for this page session (a reveal toggled twice loads once; the
// endpoint has a per-hour budget).
const cache = new Map<number, StudentCitationView[]>();

function remember(questionId: number, items: StudentCitationView[]) {
  if (cache.size >= CACHE_LIMIT) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) cache.delete(oldest);
  }
  cache.set(questionId, items);
}

interface Props {
  questionId: number;
  /** True once the student has answered / the answer is shown. */
  revealed: boolean;
  className?: string;
  headingClassName?: string;
}

export default function StudentCitations({
  questionId,
  revealed,
  className = 'mt-3 rounded-lg border border-border bg-card p-3',
  headingClassName = 'mb-2 text-sm font-semibold text-foreground',
}: Props) {
  const [loaded, setLoaded] = useState<{ id: number; items: StudentCitationView[] } | null>(null);

  useEffect(() => {
    if (!revealed || !questionId) return;
    const cached = cache.get(questionId);
    if (cached) {
      setLoaded({ id: questionId, items: cached });
      return;
    }
    let alive = true;
    fetchStudentCitations(questionId)
      .then((data) => {
        const items = normalizeCitations(data);
        remember(questionId, items);
        if (alive) setLoaded({ id: questionId, items });
      })
      .catch(() => {
        // Quiet on purpose: a failed or throttled request just shows no references.
        if (alive) setLoaded({ id: questionId, items: [] });
      });
    return () => {
      alive = false;
    };
  }, [questionId, revealed]);

  const items = revealed && loaded?.id === questionId ? loaded.items : [];
  if (items.length === 0) return null;

  const headingId = `student-citations-${questionId}`;
  return (
    <section aria-labelledby={headingId} className={`min-w-0 text-sm text-foreground ${className}`}>
      <h4 id={headingId} className={`flex items-center gap-1.5 ${headingClassName}`}>
        <BookOpen className="h-4 w-4 shrink-0" aria-hidden="true" />
        {items.length === 1 ? 'Reference' : 'References'}
      </h4>
      <ul className="space-y-2.5">
        {items.map((item) => {
          const details = [item.chapter, item.page].filter(Boolean).join(' · ');
          return (
            <li key={item.id} className="min-w-0">
              <p className="break-words font-medium">{sourceLine(item)}</p>
              {(details || item.stance) && (
                <p className="break-words text-xs text-muted-foreground">
                  {details}
                  {details && item.stance ? ' · ' : ''}
                  {item.stance}
                </p>
              )}
              {item.snippet && (
                <blockquote className="mt-1 break-words border-l-2 border-border pl-2 text-xs italic text-muted-foreground">
                  &ldquo;{item.snippet}&rdquo;
                </blockquote>
              )}
              {item.figureUrl && (
                <img
                  src={item.figureUrl}
                  alt={`Figure from ${item.title}${item.page ? `, ${item.page}` : ''}`}
                  loading="lazy"
                  className="mt-1.5 h-auto max-h-56 w-auto max-w-full rounded border border-border bg-white"
                />
              )}
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
        Short excerpts, checked against the cited page by our editors.
      </p>
    </section>
  );
}
