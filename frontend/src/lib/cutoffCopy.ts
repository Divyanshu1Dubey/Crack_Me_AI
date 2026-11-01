import type { CutoffContent } from '@/components/CutoffLayout';

/**
 * One sentence on what a cutoff page shows, for its meta description,
 * JSON-LD and hero. Topper scores and the year-over-year table render only
 * when the data has rows (every cutoffData entry has toppers: [] and
 * trend: [] today), and a cycle whose cutoff is not out yet has no table,
 * so the copy promises only what the page has.
 *
 * Kept free of runtime imports so it can be unit-tested directly with Node.
 */
export function cutoffSummary(
    c: Pick<CutoffContent, 'examName' | 'year' | 'cutoffs' | 'toppers' | 'trend'>,
): string {
    if (c.cutoffs.length === 0) {
        return `The category-wise ${c.examName} ${c.year} cutoff comes with the final result; we add the verified figures once it is out. Until then: answers to common questions.`;
    }
    const extras = [
        c.toppers.length > 0 ? 'topper scores' : null,
        c.trend.length > 0 ? 'year-over-year trends' : null,
    ].filter((x): x is string => x !== null);
    const withExtras = extras.length > 0 ? `, ${extras.join(' and ')},` : '';
    return `Category-wise qualifying marks for ${c.examName} ${c.year}${withExtras} and answers to common questions about this cycle.`;
}

/** Meta description for a cutoff page. */
export function cutoffMetaDescription(
    c: Pick<CutoffContent, 'examName' | 'year' | 'cutoffs' | 'toppers' | 'trend'>,
): string {
    return c.cutoffs.length > 0 ? `${cutoffSummary(c)} See if you would have qualified.` : cutoffSummary(c);
}
