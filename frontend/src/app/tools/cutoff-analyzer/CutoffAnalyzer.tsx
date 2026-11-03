'use client';

import { useMemo, useState } from 'react';
import {
    CUTOFF_MAX_MARKS,
    historicalCutoffs,
    linearRegressionPredict,
    scoreAdvice,
    trendCategories,
    type Confidence,
} from './cutoffModel';

interface CutoffResult {
    selectedCategory: string;
    lastYear: string;
    cutoffMarks: number;
    predictedNext: number;
    deltaFromLast: number;
    confidence: Confidence;
    recommendation: string;
    trendDirection: 'rising' | 'falling' | 'stable';
    comparison: Record<string, number>;
}

export default function CutoffAnalyzer() {
    const HISTORICAL_CUTOFFS = useMemo(() => historicalCutoffs(), []);
    const CATEGORIES = useMemo(() => trendCategories(HISTORICAL_CUTOFFS), [HISTORICAL_CUTOFFS]);
    const [category, setCategory] = useState(CATEGORIES[0] ?? 'General');
    const [score, setScore] = useState('');
    const [result, setResult] = useState<CutoffResult | null>(null);

    const predictFor = (cat: string) => {
        const historical = HISTORICAL_CUTOFFS[cat] ?? {};
        const years = Object.keys(historical).sort();
        return { years, ...linearRegressionPredict(years.map((y) => historical[y])) };
    };

    const analyze = () => {
        const historical = HISTORICAL_CUTOFFS[category] ?? {};
        const { years, predicted, slope, confidence } = predictFor(category);
        const lastYear = years[years.length - 1];
        const lastCutoff = historical[lastYear];

        const trendDirection: 'rising' | 'falling' | 'stable' = slope > 2 ? 'rising' : slope < -2 ? 'falling' : 'stable';

        // Each category's own estimate (it used to show the selected
        // category's number for every category).
        const comparison: Record<string, number> = {};
        CATEGORIES.forEach((cat) => {
            comparison[cat] = predictFor(cat).predicted;
        });

        setResult({
            selectedCategory: category,
            lastYear,
            cutoffMarks: lastCutoff,
            predictedNext: predicted,
            deltaFromLast: predicted - lastCutoff,
            confidence,
            recommendation: scoreAdvice(score ? Number(score) : null, predicted),
            trendDirection,
            comparison,
        });
    };

    const historical = HISTORICAL_CUTOFFS[category] ?? {};
    const years = Object.keys(historical).sort();
    const values = years.map((y) => historical[y]);
    const firstYear = years[0];
    const latestYear = years[years.length - 1];

    // mini sparkline width helper
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;
    const points = values.map((v, i) => {
        const x = values.length > 1 ? (i / (values.length - 1)) * 100 : 50;
        const y = 100 - ((v - minVal) / range) * 100;
        return `${x},${y}`;
    }).join(' ');

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS Cutoff Analyzer {firstYear}–{latestYear} + Next-Cycle Estimate</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                See how the approximate written cutoff (out of {CUTOFF_MAX_MARKS}) has moved across categories and get a simple
                trend-based estimate for the next cycle. Values are the approximate ranges published on our cutoff pages —
                verify exact numbers on upsc.gov.in.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label htmlFor="cutoff-category" className="block text-sm font-semibold mb-1">Category</label>
                    <select id="cutoff-category" value={category} onChange={(e) => { setCategory(e.target.value); setResult(null); }} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        {CATEGORIES.map((c) => (
                            <option key={c} value={c}>{c}</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label htmlFor="cutoff-score" className="block text-sm font-semibold mb-1">Your Written Score (out of {CUTOFF_MAX_MARKS}, optional)</label>
                    <input id="cutoff-score" type="number" value={score} onChange={(e) => setScore(e.target.value)} min="0" max={CUTOFF_MAX_MARKS} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                </div>
            </div>

            <button onClick={analyze} className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                Analyse Cutoff Trends
            </button>

            <div className="mt-6 rounded-xl border border-border bg-muted/50 p-5">
                <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">Historical Trend</p>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-24" aria-hidden="true">
                    <polyline fill="none" stroke="currentColor" strokeWidth="2" points={points} className="text-primary" />
                    {values.map((v, i) => {
                        const x = values.length > 1 ? (i / (values.length - 1)) * 100 : 50;
                        const y = 100 - ((v - minVal) / range) * 100;
                        return (
                            <circle key={i} cx={x} cy={y} r="1.5" className="text-primary" />
                        );
                    })}
                </svg>
                <div className="mt-3 grid grid-cols-4 gap-2 text-[11px] text-muted-foreground">
                    {years.map((y) => (
                        <div key={y} className="flex flex-col items-center">
                            <span className="font-mono font-bold">{historical[y]}</span>
                            <span>{y}</span>
                        </div>
                    ))}
                </div>
            </div>

            {result && (
                <div className="mt-6 space-y-4" aria-live="polite">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div className="rounded-xl border border-border bg-background p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">{result.lastYear} Cutoff (approx.)</p>
                            <p className="mt-1 text-3xl font-black text-foreground">{result.cutoffMarks} / {CUTOFF_MAX_MARKS}</p>
                            <p className="mt-1 text-xs text-muted-foreground">{result.selectedCategory} • {result.lastYear}</p>
                        </div>
                        <div className="rounded-xl border border-border bg-background p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Next-Cycle Estimate</p>
                            <p className="mt-1 text-3xl font-black text-foreground">{result.predictedNext} / {CUTOFF_MAX_MARKS}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                {result.deltaFromLast >= 0 ? '+' : ''}{result.deltaFromLast} vs {result.lastYear} • {result.trendDirection === 'rising' ? 'Rising' : result.trendDirection === 'falling' ? 'Falling' : 'Stable'} trend • Confidence: {result.confidence}
                            </p>
                        </div>
                    </div>

                    <div className="rounded-xl border border-border bg-background p-5">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">Category Comparison — Next-Cycle Estimates</p>
                        <div className="grid gap-2 sm:grid-cols-3">
                            {CATEGORIES.map((cat) => (
                                <div key={cat} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                                    <span className="text-xs font-semibold">{cat}</span>
                                    <span className="text-xs font-bold">{result.comparison[cat]} / {CUTOFF_MAX_MARKS}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-xl border border-border bg-muted/50 p-5">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Your Position vs Estimated Cutoff</p>
                        <p className="mt-1 text-sm text-foreground">{result.recommendation}</p>
                    </div>

                    <p className="text-xs text-muted-foreground">
                        * The estimate is a straight-line trend through {years.length} approximate yearly values, so its
                        confidence is low. The actual cutoff depends on paper difficulty, vacancy count and candidate volume.
                        Treat this as a planning guide, not a guarantee.
                    </p>
                </div>
            )}
        </div>
    );
}
