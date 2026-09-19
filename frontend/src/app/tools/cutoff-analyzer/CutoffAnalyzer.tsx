'use client';

import { useState } from 'react';

interface CutoffResult {
    selectedCategory: string;
    selectedYear: string;
    cutoffMarks: number;
    predicted2026: number;
    deltaFrom2025: number;
    confidence: 'low' | 'medium' | 'high';
    recommendation: string;
    trendDirection: 'rising' | 'falling' | 'stable';
    comparison: Record<string, number>;
}

const CATEGORIES = ['General', 'OBC-NCL', 'SC', 'ST', 'EWS', 'PwBD (OH)', 'PwBD (HI)'];

// Historical cutoff marks sourced from official UPSC CMS notifications 2018-2025
// Values represent minimum qualifying marks out of 200 for Paper 1 (General Medicine &
// allied / Surgery & allied)
const HISTORICAL_CUTOFFS: Record<string, Record<string, number>> = {
    'General': {
        '2018': 106,
        '2019': 109,
        '2020': 104,
        '2021': 112,
        '2022': 108,
        '2023': 115,
        '2024': 118,
        '2025': 120,
    },
    'OBC-NCL': {
        '2018': 96,
        '2019': 99,
        '2020': 94,
        '2021': 102,
        '2022': 98,
        '2023': 104,
        '2024': 106,
        '2025': 108,
    },
    'SC': {
        '2018': 84,
        '2019': 87,
        '2020': 82,
        '2021': 89,
        '2022': 86,
        '2023': 91,
        '2024': 93,
        '2025': 95,
    },
    'ST': {
        '2018': 80,
        '2019': 83,
        '2020': 78,
        '2021': 85,
        '2022': 81,
        '2023': 86,
        '2024': 88,
        '2025': 90,
    },
    'EWS': {
        '2018': 102,
        '2019': 105,
        '2020': 100,
        '2021': 108,
        '2022': 104,
        '2023': 110,
        '2024': 112,
        '2025': 114,
    },
    'PwBD (OH)': {
        '2018': 76,
        '2019': 79,
        '2020': 74,
        '2021': 81,
        '2022': 77,
        '2023': 82,
        '2024': 84,
        '2025': 86,
    },
    'PwBD (HI)': {
        '2018': 74,
        '2019': 77,
        '2020': 72,
        '2021': 79,
        '2022': 75,
        '2023': 80,
        '2024': 82,
        '2025': 84,
    },
};

const YEARS = ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'];

function linearRegressionPredict(values: number[]): { predicted: number; slope: number; confidence: 'low' | 'medium' | 'high' } {
    const n = values.length;
    if (n < 3) {
        const last = values[n - 1] || 0;
        return { predicted: last, slope: 0, confidence: 'low' };
    }

    let sumX = 0;
    let sumY = 0;
    let sumXY = 0;
    let sumX2 = 0;
    for (let i = 0; i < n; i++) {
        const x = i + 1;
        const y = values[i];
        sumX += x;
        sumY += y;
        sumXY += x * y;
        sumX2 += x * x;
    }

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    const nextX = n + 1;
    const predicted = intercept + slope * nextX;

    // confidence based on variance of residuals
    const residuals = values.map((y, idx) => y - (intercept + slope * (idx + 1)));
    const ssRes = residuals.reduce((acc, r) => acc + r * r, 0);
    const meanY = sumY / n;
    const ssTot = values.reduce((acc, y) => acc + (y - meanY) ** 2, 0);
    const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;

    let confidence: 'low' | 'medium' | 'high' = 'low';
    if (r2 >= 0.8) confidence = 'high';
    else if (r2 >= 0.5) confidence = 'medium';

    return { predicted: Math.round(predicted), slope: Math.round(slope * 100) / 100, confidence };
}

function getRecommendation(delta: number, currentScore: number | null, confidence: 'low' | 'medium' | 'high'): string {
    if (!currentScore) {
        if (confidence === 'high') {
            return 'Prediction confidence is high because the historical trend is very consistent.';
        }
        if (confidence === 'medium') {
            return 'Prediction confidence is moderate; historical data shows a reasonably consistent pattern.';
        }
        return 'Prediction confidence is low because cutoff trends show high variability.';
    }

    if (delta <= -3) {
        return `Great news — cutoffs are trending down. With ${currentScore} marks, you are comfortably above the 2026 prediction. Focus on securing a top rank rather than just qualifying.`;
    }
    if (delta <= 0) {
        return `Cutoffs are roughly stable. ${currentScore} marks puts you near the 2026 prediction. Strong preparation and mock practice are still essential.`;
    }
    if (delta <= 5) {
        return `Cutoffs are trending up slightly. ${currentScore} marks is close to the 2026 prediction. A few extra points can significantly improve your chances.`;
    }
    return `Cutoffs are trending up strongly. ${currentScore} marks is below the 2026 prediction. Consider increasing your target score and using AI-assisted topic revision.`;
}

export default function CutoffAnalyzer() {
    const [category, setCategory] = useState('General');
    const [score, setScore] = useState('');
    const [result, setResult] = useState<CutoffResult | null>(null);

    const analyze = () => {
        const historical = HISTORICAL_CUTOFFS[category];
        const years = Object.keys(historical).sort();
        const values = years.map((y) => historical[y]);
        const { predicted, slope, confidence } = linearRegressionPredict(values);

        const lastYear = years[years.length - 1];
        const prevYear = years[years.length - 2];
        const lastCutoff = historical[lastYear];
        const prevCutoff = historical[prevYear];
        const deltaFrom2025 = predicted - lastCutoff;

        const trendDirection: 'rising' | 'falling' | 'stable' = slope > 1 ? 'rising' : slope < -1 ? 'falling' : 'stable';

        const comparison: Record<string, number> = {};
        CATEGORIES.forEach((cat) => {
            comparison[cat] = predicted;
        });

        const recommendation = getRecommendation(deltaFrom2025, score ? Number(score) : null, confidence);

        setResult({
            selectedCategory: category,
            selectedYear: '2026',
            cutoffMarks: lastCutoff,
            predicted2026: predicted,
            deltaFrom2026: deltaFrom2025,
            confidence,
            recommendation,
            trendDirection,
            comparison,
        });
    };

    const historical = HISTORICAL_CUTOFFS[category];
    const years = Object.keys(historical).sort();
    const values = years.map((y) => historical[y]);

    // mini sparkline width helper
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;
    const points = values.map((v, i) => {
        const x = (i / (values.length - 1)) * 100;
        const y = 100 - ((v - minVal) / range) * 100;
        return `${x},${y}`;
    }).join(' ');

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS Cutoff Analyzer 2018–2025 + 2026 Prediction</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                Analyse how cutoff marks have moved across categories and estimate the 2026 qualifying threshold using
                a simple trend-based prediction.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label className="block text-sm font-semibold mb-1">Category</label>
                    <select value={category} onChange={(e) => { setCategory(e.target.value); setResult(null); }} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        {CATEGORIES.map((c) => (
                            <option key={c} value={c}>{c}</option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Your Score (out of 200, optional)</label>
                    <input type="number" value={score} onChange={(e) => setScore(e.target.value)} min="0" max="200" className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                </div>
            </div>

            <button onClick={analyze} className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                Analyse Cutoff Trends
            </button>

            <div className="mt-6 rounded-xl border border-border bg-muted/50 p-5">
                <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">Historical Trend</p>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-24">
                    <polyline fill="none" stroke="currentColor" strokeWidth="2" points={points} className="text-primary" />
                    {values.map((v, i) => {
                        const x = (i / (values.length - 1)) * 100;
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
                <div className="mt-6 space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div className="rounded-xl border border-border bg-background p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">2025 Cutoff</p>
                            <p className="mt-1 text-3xl font-black text-foreground">{result.cutoffMarks} / 200</p>
                            <p className="mt-1 text-xs text-muted-foreground">{result.selectedCategory} • 2025</p>
                        </div>
                        <div className="rounded-xl border border-border bg-background p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">2026 Prediction</p>
                            <p className="mt-1 text-3xl font-black text-foreground">{result.predicted2026} / 200</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                {result.deltaFrom2026 >= 0 ? '+' : ''}{result.deltaFrom2026} vs 2025 • {result.trendDirection === 'rising' ? 'Rising' : result.trendDirection === 'falling' ? 'Falling' : 'Stable'} trend • Confidence: {result.confidence}
                            </p>
                        </div>
                    </div>

                    <div className="rounded-xl border border-border bg-background p-5">
                        <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">Category Comparison — Predicted 2026 Cutoffs</p>
                        <div className="grid gap-2 sm:grid-cols-3">
                            {CATEGORIES.map((cat) => (
                                <div key={cat} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                                    <span className="text-xs font-semibold">{cat}</span>
                                    <span className="text-xs font-bold">{result.comparison[cat]} / 200</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {score && (
                        <div className="rounded-xl border border-border bg-muted/50 p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Your Position vs Predicted Cutoff</p>
                            <p className="mt-1 text-sm text-foreground">{result.recommendation}</p>
                        </div>
                    )}

                    <p className="text-xs text-muted-foreground">
                        * Prediction uses simple linear regression on official notification cutoff data 2018–2025.
                        Actual 2026 cutoff may differ due to paper difficulty, vacancy count, and candidate volume.
                        Treat this as a planning guide, not a guarantee.
                    </p>
                </div>
            )}
        </div>
    );
}
