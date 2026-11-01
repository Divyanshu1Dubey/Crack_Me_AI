'use client';

import { useState } from 'react';
import { CATEGORIES, TOTAL_VACANCIES, computeRankAnalysis, type Category } from './rankModel';

const EMPTY_RESULTS: Record<Category, ReturnType<typeof computeRankAnalysis> | null> = {
  general: null,
  ews: null,
  obc: null,
  sc: null,
  st: null,
  pwbd: null,
};

// Model (reservation shares, open pool, vacancies) lives in rankModel.ts.

function chanceColor(chance: string): string {
  switch (chance) {
    case 'Very High':
      return 'text-emerald-700 dark:text-emerald-300';
    case 'High':
      return 'text-green-700 dark:text-green-300';
    case 'Moderate':
      return 'text-amber-700 dark:text-amber-300';
    case 'Low':
      return 'text-orange-700 dark:text-orange-300';
    case 'Very Low':
      return 'text-red-700 dark:text-red-300';
    default:
      return 'text-foreground';
  }
}

export default function CategoryRankFilter() {
  const [rankInput, setRankInput] = useState('');
  const [sourceCategory, setSourceCategory] = useState<Category>('general');
  const [results, setResults] = useState<Record<Category, ReturnType<typeof computeRankAnalysis> | null>>(EMPTY_RESULTS);

  const analyze = () => {
    const rank = parseInt(rankInput, 10);
    if (isNaN(rank) || rank <= 0) return;

    const newResults: Record<Category, ReturnType<typeof computeRankAnalysis> | null> = { ...EMPTY_RESULTS };

    // First compute source category result
    const sourceResult = computeRankAnalysis(rank, sourceCategory, sourceCategory);
    newResults[sourceCategory] = sourceResult;

    // Then compute all other categories
    const others = CATEGORIES.filter(c => c.id !== sourceCategory);
    for (const cat of others) {
      newResults[cat.id] = computeRankAnalysis(rank, sourceCategory, cat.id);
    }

    setResults(newResults);
  };

  const reset = () => {
    setRankInput('');
    setResults(EMPTY_RESULTS);
  };

  const hasResults = Object.values(results).some(r => r !== null);

  return (
    <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
      <h3 className="text-xl font-bold">Category Rank Filter 2026</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Enter your category-wise rank and select your category to see how that rank maps across
        General, EWS, OBC, SC, ST, and PwBD categories. Estimate selection chances based on
        reservation shares and the {TOTAL_VACANCIES.toLocaleString('en-IN')} posts in the current UPSC CMS notice.
      </p>

      <div className="mt-6 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="crf-rank" className="block text-sm font-semibold mb-1">Category-wise Rank</label>
            <input
              id="crf-rank"
              aria-describedby="crf-rank-help"
              type="number"
              value={rankInput}
              onChange={(e) => setRankInput(e.target.value)}
              placeholder="e.g. 150"
              min="1"
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
            />
            <p id="crf-rank-help" className="mt-1 text-xs text-muted-foreground">
              Your rank in your respective category list.
            </p>
          </div>
          <div>
            <label htmlFor="crf-category" className="block text-sm font-semibold mb-1">Your Category</label>
            <select
              id="crf-category"
              value={sourceCategory}
              onChange={(e) => setSourceCategory(e.target.value as Category)}
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
            >
              {CATEGORIES.map(cat => (
                <option key={cat.id} value={cat.id}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={analyze}
            className="flex-1 rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90"
          >
            Compare Across Categories
          </button>
          {(rankInput || hasResults) && (
            <button
              onClick={reset}
              className="rounded-xl border border-border bg-muted/50 px-6 py-3 text-sm font-semibold transition hover:bg-muted"
            >
              Reset
            </button>
          )}
        </div>

        {hasResults && results[sourceCategory] && (
          <div className="rounded-xl border border-border bg-muted/50 p-5 sm:p-6">
            <p className="text-sm font-semibold text-foreground">
              Your input: Rank #{parseInt(rankInput, 10).toLocaleString('en-IN')} in{' '}
              {CATEGORIES.find(c => c.id === sourceCategory)?.label}
            </p>

            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {CATEGORIES.map(cat => {
                const r = results[cat.id];
                if (!r) return null;
                const info = CATEGORIES.find(c => c.id === cat.id)!;
                const isSource = cat.id === sourceCategory;

                return (
                  <div
                    key={cat.id}
                    className={`rounded-xl border p-4 ${
                      isSource
                        ? 'border-primary bg-primary/5'
                        : 'border-border bg-background'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-bold">{info.label}</p>
                        <p className="text-[10px] text-muted-foreground">{info.description}</p>
                      </div>
                      {isSource && (
                        <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold text-primary-foreground">
                          Your category
                        </span>
                      )}
                    </div>

                    <div className="mt-3 space-y-1.5">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Equivalent Rank</span>
                        <span className="font-bold">#{r.equivalentRank.toLocaleString('en-IN')}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Est. Vacancies</span>
                        <span className="font-bold">{r.vacancies}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Reservation</span>
                        <span className="font-bold">{info.reservationLabel}</span>
                      </div>
                      <div className="mt-2 rounded-lg bg-muted/50 p-2.5">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
                          Selection Chance
                        </p>
                        <p className={`mt-0.5 text-lg font-black ${chanceColor(r.selectionChance)}`}>
                          {r.selectionChance}
                        </p>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">{r.note}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="mt-4 text-xs text-muted-foreground">
              * Indicative estimates based on approximate reservation percentages and
              historical vacancy trends. Actual selection depends on UPSC's final merit list,
              number of candidates in each category, and seat availability. Always verify
              with the official notification at upsc.gov.in.
            </p>
          </div>
        )}

        <div className="rounded-xl border border-border bg-muted/30 p-5">
          <p className="text-sm font-semibold text-foreground">Reservation Overview</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {CATEGORIES.map(cat => (
              <div key={cat.id} className="flex items-center justify-between rounded-lg bg-background p-3">
                <div>
                  <p className="text-sm font-bold">{cat.label}</p>
                  <p className="text-xs text-muted-foreground">{cat.description}</p>
                </div>
                <span className="text-lg font-black text-primary">{cat.reservationLabel}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Reservation shares follow the central-government policy (OBC 27%, SC 15%, ST 7.5%, EWS 10%); the General list competes for the remaining open posts. PwBD reservation is horizontal, meaning it is filled from the respective category pool. Vacancies are estimated from the {TOTAL_VACANCIES.toLocaleString('en-IN')} posts in the current notice; the exact split is in the notification PDF.
          </p>
        </div>
      </div>
    </div>
  );
}
