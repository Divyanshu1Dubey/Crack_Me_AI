'use client';

import { useState } from 'react';

type Category = 'general' | 'obc' | 'sc' | 'st' | 'pwbd';

interface CategoryInfo {
  id: Category;
  label: string;
  reservationPct: number;
  description: string;
}

const CATEGORIES: CategoryInfo[] = [
  { id: 'general', label: 'General', reservationPct: 0, description: 'Unreserved category — open competition' },
  { id: 'obc', label: 'OBC (NCL)', reservationPct: 27, description: 'Non-Creamy Layer — 27% reservation' },
  { id: 'sc', label: 'SC', reservationPct: 15, description: 'Scheduled Caste — 15% reservation' },
  { id: 'st', label: 'ST', reservationPct: 7.5, description: 'Scheduled Tribe — 7.5% reservation' },
  { id: 'pwbd', label: 'PwBD', reservationPct: 4, description: 'Persons with Benchmark Disability — 4% reservation (horizontal)' },
];

// Approximate applicant pool sizes for UPSC CMS (indicative only)
const POOL_SIZES: Record<Category, number> = {
  general: 45000,
  obc: 35000,
  sc: 15000,
  st: 10000,
  pwbd: 5000,
};

// Approximate vacancy numbers for UPSC CMS 2026 (indicative only)
const TOTAL_VACANCIES = 600;

function poolForCategory(category: Category): number {
  if (category === 'pwbd') {
    return POOL_SIZES.general + POOL_SIZES.obc + POOL_SIZES.sc + POOL_SIZES.st;
  }
  return POOL_SIZES[category];
}

function categoryVacancies(category: Category): number {
  if (category === 'pwbd') {
    return Math.round(TOTAL_VACANCIES * 0.04);
  }
  return Math.round(TOTAL_VACANCIES * (CATEGORIES.find(c => c.id === category)!.reservationPct / 100));
}

function computeRankAnalysis(
  rankInput: number,
  sourceCategory: Category,
  targetCategory: Category,
): { equivalentRank: number; categoryRank: number; vacancies: number; selectionChance: string; note: string } {
  const sourcePool = poolForCategory(sourceCategory);
  const targetPool = poolForCategory(targetCategory);

  // Convert absolute rank to percentile in source category
  const sourcePercentile = Math.max(0, Math.min(100, (1 - rankInput / sourcePool) * 100));

  // Convert percentile to equivalent rank in target category
  const equivalentRank = Math.round(targetPool * (1 - sourcePercentile / 100));

  // Compute category rank for target category
  const categoryVacancy = categoryVacancies(targetCategory);
  const categoryRank = Math.max(1, equivalentRank);

  // Selection chance based on how the rank compares to vacancies
  const ratio = categoryRank / categoryVacancy;
  let selectionChance = '';
  let note = '';
  if (ratio <= 0.5) {
    selectionChance = 'Very High';
    note = 'Your rank is well within the likely selection zone for this category.';
  } else if (ratio <= 1.0) {
    selectionChance = 'High';
    note = 'Your rank is within the estimated vacancy range for this category.';
  } else if (ratio <= 1.5) {
    selectionChance = 'Moderate';
    note = 'Your rank is near the edge of the estimated vacancy range. Position may shift based on final merit.';
  } else if (ratio <= 2.5) {
    selectionChance = 'Low';
    note = 'Your rank exceeds the estimated vacancy count for this category. Consider backup plans.';
  } else {
    selectionChance = 'Very Low';
    note = 'Your rank is significantly above the estimated vacancy range for this category.';
  }

  return { equivalentRank, categoryRank, vacancies: categoryVacancy, selectionChance, note };
}

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
  const [results, setResults] = useState<Record<Category, ReturnType<typeof computeRankAnalysis> | null>>({
    general: null,
    obc: null,
    sc: null,
    st: null,
    pwbd: null,
  });

  const analyze = () => {
    const rank = parseInt(rankInput, 10);
    if (isNaN(rank) || rank <= 0) return;

    const newResults: Record<Category, ReturnType<typeof computeRankAnalysis> | null> = {
      general: null,
      obc: null,
      sc: null,
      st: null,
      pwbd: null,
    };

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
    setResults({ general: null, obc: null, sc: null, st: null, pwbd: null });
  };

  const hasResults = Object.values(results).some(r => r !== null);

  return (
    <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
      <h3 className="text-xl font-bold">Category Rank Filter 2026</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Enter your category-wise rank and select your category to see how that rank maps across
        General, OBC, SC, ST, and PwBD categories. Estimate selection chances based on
        approximate reservation quotas and vacancy data.
      </p>

      <div className="mt-6 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-semibold mb-1">Category-wise Rank</label>
            <input
              type="number"
              value={rankInput}
              onChange={(e) => setRankInput(e.target.value)}
              placeholder="e.g. 150"
              min="1"
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Your rank in your respective category list.
            </p>
          </div>
          <div>
            <label className="block text-sm font-semibold mb-1">Your Category</label>
            <select
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
                        <span className="font-bold">{info.reservationPct}%</span>
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
                <span className="text-lg font-black text-primary">{cat.reservationPct}%</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Reservation percentages are based on the UPSC CMS reservation policy. PwBD reservation is horizontal, meaning it is filled from the respective category pool. Total vacancies shown are approximate and vary each year.
          </p>
        </div>
      </div>
    </div>
  );
}
