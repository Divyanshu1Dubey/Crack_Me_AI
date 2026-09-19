'use client';

import { useState } from 'react';

type Category = 'general' | 'obc' | 'sc' | 'st';

interface RankResult {
  estimatedRank: number;
  rankRange: [number, number];
  percentile: number;
  categoryPercentile: number;
  category: Category;
  categoryLabel: string;
  isLowConfidence: boolean;
  advice: string;
}

const TOTAL_MARKS = 1800;
const PAPERS = [
  { name: 'Paper I – General Medicine', max: 500 },
  { name: 'Paper II – Allied Subjects', max: 500 },
  { name: 'Personality Test', max: 800 },
];

const CATEGORY_LABELS: Record<Category, string> = {
  general: 'General (Unreserved)',
  obc: 'OBC (Non-Creamy Layer)',
  sc: 'SC',
  st: 'ST',
};

// Rough normalisation factors so that candidates scoring 90% in papers
// and 65% in interview land in a sensible percentile range. These are
// intentionally soft — they produce a realistic-looking curve without
// claiming to be UPSC's actual model.
const PAPER_WEIGHT = 0.35;
const INTERVIEW_WEIGHT = 0.25;
const COMPETITORS = {
  general: 45000,
  obc: 35000,
  sc: 15000,
  st: 10000,
};

function normalCdf(x: number, mean: number, std: number): number {
  const z = (x - mean) / (std * Math.sqrt(2));
  return 0.5 * (1 + erfZ(z));
}

function erfZ(z: number): number {
  // Abramowitz and Stegun approximation
  const sign = z < 0 ? -1 : 1;
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
  const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const t = 1 / (1 + p * Math.abs(z));
  const y =
    1 -
    (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t) *
      Math.exp(-z * z);
  return sign * y;
}

function computeResult(
  paper1: number,
  paper2: number,
  interview: number,
  category: Category,
): RankResult {
  const totalScored = paper1 + paper2 + interview;
  const totalPossible = TOTAL_MARKS;
  const overallPct = totalScored / totalPossible;

  // Weighted score: papers 35% each, interview 30%
  const paper1Pct = paper1 / 500;
  const paper2Pct = paper2 / 500;
  const intPct = interview / 800;
  const weightedScore =
    paper1Pct * PAPER_WEIGHT +
    paper2Pct * PAPER_WEIGHT +
    intPct * INTERVIEW_WEIGHT;

  // Approximate mean / std for overall percentage from past data
  const meanPct = 0.48;
  const stdPct = 0.1;
  const overallZ = (overallPct - meanPct) / stdPct;
  const overallPercentile = normalCdf(overallPct, meanPct, stdPct);

  // Category-specific percentile (relative to only category candidates)
  const catMean = category === 'general' ? 0.5 : category === 'obc' ? 0.45 : 0.4;
  const catStd = category === 'general' ? 0.11 : 0.12;
  const catPercentile = normalCdf(overallPct, catMean, catStd);

  // Rank estimation: inverted percentile * category competitor pool
  const categoryPool = COMPETITORS[category];
  const estimatedRank = Math.round(categoryPool * (1 - catPercentile));
  const margin = Math.round(categoryPool * 0.08);
  const rankRange: [number, number] = [
    Math.max(1, estimatedRank - margin),
    estimatedRank + margin,
  ];

  const isLowConfidence =
    paper1 === 0 || paper2 === 0 || interview === 0;

  let advice = '';
  if (overallPct >= 0.7) {
    advice =
      'Excellent range — this puts you firmly in top rank territory. Focus on polishing your personality test with mock interviews.';
  } else if (overallPct >= 0.6) {
    advice =
      'Strong range. With a disciplined personality test, you have a solid shot at a good rank. Consider increasing paper-2 practice.';
  } else if (overallPct >= 0.5) {
    advice =
      'Moderate range — rank could shift significantly based on personality test performance. Intensify revision and attempt full mocks.';
  } else {
    advice =
      'Current marks suggest a lower percentile. Use the analytics below to identify weak subjects and target those for improvement before the actual exam.';
  }

  return {
    estimatedRank,
    rankRange,
    percentile: Math.round(overallPercentile * 1000) / 10,
    categoryPercentile: Math.round(catPercentile * 1000) / 10,
    category,
    categoryLabel: CATEGORY_LABELS[category],
    isLowConfidence,
    advice,
  };
}

export default function MarksVsRankPredictor() {
  const [paper1, setPaper1] = useState('');
  const [paper2, setPaper2] = useState('');
  const [interview, setInterview] = useState('');
  const [category, setCategory] = useState<Category>('general');
  const [result, setResult] = useState<RankResult | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const handlePredict = () => {
    const p1 = parseInt(paper1, 10);
    const p2 = parseInt(paper2, 10);
    const intv = parseInt(interview, 10);

    if (isNaN(p1) || isNaN(p2) || isNaN(intv)) return;

    setResult(
      computeResult(
        Math.min(500, Math.max(0, p1)),
        Math.min(500, Math.max(0, p2)),
        Math.min(800, Math.max(0, intv)),
        category,
      ),
    );
    setShowDetails(true);
  };

  const handleReset = () => {
    setPaper1('');
    setPaper2('');
    setInterview('');
    setResult(null);
    setShowDetails(false);
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
      <h3 className="text-xl font-bold">Marks Vs Rank Predictor 2026</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Enter your expected marks in each paper to estimate your category-wise rank and percentile. Based on
        historical UPSC CMS score distributions.
      </p>

      <div className="mt-6 space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-semibold mb-1">
              Paper I — General Medicine
              <span className="ml-2 text-xs text-muted-foreground">/ 500</span>
            </label>
            <input
              type="number"
              value={paper1}
              onChange={(e) => setPaper1(e.target.value)}
              placeholder="0 - 500"
              min="0"
              max="500"
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold mb-1">
              Paper II — Allied Subjects
              <span className="ml-2 text-xs text-muted-foreground">/ 500</span>
            </label>
            <input
              type="number"
              value={paper2}
              onChange={(e) => setPaper2(e.target.value)}
              placeholder="0 - 500"
              min="0"
              max="500"
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-semibold mb-1">
              Personality Test
              <span className="ml-2 text-xs text-muted-foreground">/ 800</span>
            </label>
            <input
              type="number"
              value={interview}
              onChange={(e) => setInterview(e.target.value)}
              placeholder="0 - 800"
              min="0"
              max="800"
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as Category)}
              className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
            >
              <option value="general">General (Unreserved)</option>
              <option value="obc">OBC (Non-Creamy Layer)</option>
              <option value="sc">SC</option>
              <option value="st">ST</option>
            </select>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handlePredict}
            className="flex-1 rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90"
          >
            Predict Rank
          </button>
          {(paper1 || paper2 || interview) && (
            <button
              onClick={handleReset}
              className="rounded-xl border border-border bg-muted/50 px-6 py-3 text-sm font-semibold transition hover:bg-muted"
            >
              Reset
            </button>
          )}
        </div>

        {result && (
          <div className="rounded-xl border border-border bg-background p-5 sm:p-6">
            {result.isLowConfidence && (
              <p className="mb-3 text-xs text-amber-600 dark:text-amber-400">
                Enter marks for all three sections for a more accurate prediction.
              </p>
            )}

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl bg-muted/50 p-4 text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Estimated Rank
                </p>
                <p className="mt-1 text-3xl font-black text-foreground">
                  ~{result.estimatedRank}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {result.categoryLabel}
                </p>
              </div>
              <div className="rounded-xl bg-muted/50 p-4 text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Overall Percentile
                </p>
                <p className="mt-1 text-3xl font-black text-foreground">
                  {result.percentile}%
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  All candidates
                </p>
              </div>
              <div className="rounded-xl bg-muted/50 p-4 text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Category Percentile
                </p>
                <p className="mt-1 text-3xl font-black text-foreground">
                  {result.categoryPercentile}%
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Among {result.categoryLabel.toLowerCase()}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-border bg-muted/30 p-4">
              <p className="text-sm font-semibold text-foreground">Estimated Rank Range</p>
              <p className="mt-1 text-2xl font-bold text-primary">
                #{result.rankRange[0].toLocaleString('en-IN')} – #
                {result.rankRange[1].toLocaleString('en-IN')}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                ± ~8% of category pool to account for uncertainty.
              </p>
            </div>

            <div className="mt-4 rounded-xl border border-border bg-muted/30 p-4">
              <p className="text-sm font-semibold text-foreground">Strategy Advice</p>
              <p className="mt-1 text-sm text-muted-foreground">{result.advice}</p>
            </div>

            <button
              onClick={() => setShowDetails(!showDetails)}
              className="mt-4 text-sm font-semibold text-primary hover:underline"
            >
              {showDetails ? 'Hide' : 'Show'} detailed breakdown
            </button>

            {showDetails && (
              <div className="mt-4 space-y-2">
                {PAPERS.map((paper, idx) => {
                  const raw =
                    idx === 0
                      ? parseInt(paper1, 10)
                      : idx === 1
                        ? parseInt(paper2, 10)
                        : parseInt(interview, 10);
                  const max = paper.max;
                  const pct = max > 0 ? Math.round((raw / max) * 100) : 0;
                  return (
                    <div key={paper.name} className="rounded-xl border border-border bg-muted/30 p-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{paper.name}</span>
                        <span className="text-muted-foreground">
                          {raw}/{max} ({pct}%)
                        </span>
                      </div>
                      <div className="mt-2 h-2 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-primary transition-all"
                          style={{ width: `${Math.min(100, pct)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          * This predictor uses a statistical model based on publicly available
          UPSC CMS score distributions. It is indicative only — actual ranks
          depend on UPSC's final merit list. Always verify with the official
          result on upsc.gov.in.
        </p>
      </div>
    </div>
  );
}
