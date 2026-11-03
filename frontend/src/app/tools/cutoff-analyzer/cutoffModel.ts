/**
 * Data + trend logic for the Cutoff Analyzer (pure, unit-tested with Node).
 *
 * Uses the same approximate category-wise UPSC CMS written cutoffs (out of
 * 500) that the /cms/cutoff/<year> pages publish (lib/cutoffData.ts). The
 * old tool shipped its own invented 2018-2025 numbers "out of 200 for
 * Paper 1" and labelled them as official.
 */
import { CMS_CUTOFFS } from '@/lib/cutoffData';
import { UPSC_CMS_PATTERN } from '@/lib/examPatterns';

export const CUTOFF_MAX_MARKS = UPSC_CMS_PATTERN.writtenMarks;

/** category -> year -> cutoff (only years that have published data). */
export function historicalCutoffs(): Record<string, Record<string, number>> {
    const out: Record<string, Record<string, number>> = {};
    Object.entries(CMS_CUTOFFS).forEach(([year, content]) => {
        (content.cutoffs ?? []).forEach((row) => {
            if (typeof row.cutoff !== 'number') return;
            out[row.category] = out[row.category] ?? {};
            out[row.category][year] = row.cutoff;
        });
    });
    return out;
}

/** Categories with at least two years of data (a trend needs two points). */
export function trendCategories(data = historicalCutoffs()): string[] {
    return Object.keys(data).filter((c) => Object.keys(data[c]).length >= 2);
}

export type Confidence = 'low' | 'medium' | 'high';

export function linearRegressionPredict(values: number[]): { predicted: number; slope: number; confidence: Confidence } {
    const n = values.length;
    if (n < 2) {
        return { predicted: values[0] ?? 0, slope: 0, confidence: 'low' };
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
    const predicted = intercept + slope * (n + 1);

    const meanY = sumY / n;
    const ssRes = values.reduce((acc, y, idx) => acc + (y - (intercept + slope * (idx + 1))) ** 2, 0);
    const ssTot = values.reduce((acc, y) => acc + (y - meanY) ** 2, 0);
    const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;

    // A handful of approximate yearly values cannot support a confident
    // forecast, however straight the line looks.
    let confidence: Confidence = 'low';
    if (n >= 5 && r2 >= 0.8) confidence = 'high';
    else if (n >= 5 && r2 >= 0.5) confidence = 'medium';

    return { predicted: Math.round(predicted), slope: Math.round(slope * 100) / 100, confidence };
}

/** Advice comparing the student's written score (out of 500) with the estimate. */
export function scoreAdvice(score: number | null, predicted: number): string {
    if (score === null || !Number.isFinite(score)) {
        return 'Enter your expected written score (out of 500) to compare it with the estimated cutoff.';
    }
    const gap = Math.round(score - predicted);
    if (gap >= 25) return `${score} is about ${gap} marks above the estimated cutoff — a comfortable margin. Focus on rank, not just qualifying.`;
    if (gap >= 0) return `${score} is just above the estimated cutoff (by ${gap}). Strong revision and full mocks will protect that margin.`;
    if (gap >= -25) return `${score} is about ${-gap} marks below the estimated cutoff. A few more correct answers per paper close that gap.`;
    return `${score} is well below the estimated cutoff (${-gap} marks). Prioritise high-weightage subjects and timed PYQ practice.`;
}
