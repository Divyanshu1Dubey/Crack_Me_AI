'use client';

/**
 * Figures from past questions that relate to an AI Tutor question (backend: ai_engine/related_figures.py).
 * Stem figures only (never an explanation figure), each linked to its question; free users only get
 * questions they may open. Loads by itself for the newest answer; older answers show a button.
 */
import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ImageIcon, Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { figureSrc } from '@/lib/figureSrc';
import FigureImage from '@/components/question/FigureImage';

interface Figure {
  question_id: number;
  exam_type: string;
  year: number | null;
  subject: string;
  stem: string;
  image: { id: number; url: string; alt_text: string; modality: string };
}

export function practiceHref(examType: string, questionId: number): string {
  if (examType === 'neet_pg') return `/questions/neet-pg/practice?q=${questionId}`;
  if (examType === 'ini_cet') return `/questions/inicet/practice?q=${questionId}`;
  return `/questions?q=${questionId}`;
}

const EXAM_LABEL: Record<string, string> = { cms: 'UPSC CMS', neet_pg: 'NEET PG', ini_cet: 'INI-CET' };

export default function RelatedFigures({ query, auto }: { query: string; auto: boolean }) {
  const [figures, setFigures] = useState<Figure[] | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await api.get('/ai/related-figures/', { params: { q: query.slice(0, 2000) } });
      setFigures(Array.isArray(res.data?.figures) ? res.data.figures : []);
    } catch {
      setFigures([]);   // figures are extra: a failure shows nothing
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    if (auto && figures === null) load();
  }, [auto, figures, load]);

  if (figures === null) {
    if (auto || loading) {
      return loading ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> Looking for related figures…
        </p>
      ) : null;
    }
    return (
      <button type="button" onClick={load}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-accent">
        <ImageIcon className="h-3 w-3" aria-hidden="true" /> Show related figures from past questions
      </button>
    );
  }
  if (!figures.length) return null;

  return (
    <section aria-label="Related figures from past questions" className="mt-3">
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">Related figures from past questions</p>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {figures.map((fig) => (
          <li key={fig.image.id} className="overflow-hidden rounded-lg border border-border bg-card">
            <Link href={practiceHref(fig.exam_type, fig.question_id)} className="block hover:opacity-90">
              {/* A proxied bank figure of unknown size: a plain img (retried once, then a placeholder). */}
              <FigureImage src={figureSrc(fig.image)} alt={fig.image.alt_text || 'Figure from a past question'}
                loading="lazy" className="h-28 w-full bg-white object-contain" placeholderClassName="m-2" />
              <span className="block p-1.5 text-[11px] leading-snug text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {EXAM_LABEL[fig.exam_type] ?? fig.exam_type}{fig.year ? ` ${fig.year}` : ''}
                </span>
                {fig.subject ? ` · ${fig.subject}` : ''}
                <span className="mt-0.5 line-clamp-2 block">{fig.stem}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
