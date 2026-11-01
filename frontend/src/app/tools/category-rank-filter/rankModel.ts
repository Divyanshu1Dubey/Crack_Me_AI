/**
 * Indicative category-rank model for the Category Rank Filter tool (pure,
 * unit-tested with Node).
 *
 * Vertical reservation for central posts: OBC (NCL) 27%, SC 15%, ST 7.5%,
 * EWS 10%. The unreserved (General) list is the OPEN pool — every post not
 * reserved vertically (40.5%) — which the old code modelled as 0% of
 * vacancies, so a General candidate was "Very Low" even at rank 1.
 * PwBD (4%) is horizontal: it is carved out of the vertical categories.
 * Total vacancies come from the same cycle figure the cutoff pages quote.
 */
import { UPSC_CMS_CYCLE } from '@/lib/examPatterns';

export type Category = 'general' | 'obc' | 'sc' | 'st' | 'ews' | 'pwbd';

export interface CategoryInfo {
    id: Category;
    label: string;
    /** Share of all vacancies this list competes for, in percent. */
    vacancyPct: number;
    /** How the share is described in the UI ("Open", "27%", ...). */
    reservationLabel: string;
    description: string;
}

const VERTICAL = { obc: 27, sc: 15, st: 7.5, ews: 10 } as const;
const OPEN_PCT = 100 - (VERTICAL.obc + VERTICAL.sc + VERTICAL.st + VERTICAL.ews);

export const CATEGORIES: CategoryInfo[] = [
    { id: 'general', label: 'General (UR)', vacancyPct: OPEN_PCT, reservationLabel: 'Open', description: `Unreserved — the open pool (${OPEN_PCT}% of posts), open to all on merit` },
    { id: 'ews', label: 'EWS', vacancyPct: VERTICAL.ews, reservationLabel: `${VERTICAL.ews}%`, description: `Economically Weaker Section — ${VERTICAL.ews}% reservation` },
    { id: 'obc', label: 'OBC (NCL)', vacancyPct: VERTICAL.obc, reservationLabel: `${VERTICAL.obc}%`, description: `Non-Creamy Layer — ${VERTICAL.obc}% reservation` },
    { id: 'sc', label: 'SC', vacancyPct: VERTICAL.sc, reservationLabel: `${VERTICAL.sc}%`, description: `Scheduled Caste — ${VERTICAL.sc}% reservation` },
    { id: 'st', label: 'ST', vacancyPct: VERTICAL.st, reservationLabel: `${VERTICAL.st}%`, description: `Scheduled Tribe — ${VERTICAL.st}% reservation` },
    { id: 'pwbd', label: 'PwBD', vacancyPct: 4, reservationLabel: '4%', description: 'Persons with Benchmark Disability — 4% reservation (horizontal)' },
];

/** Approximate applicant pool sizes for UPSC CMS (indicative only). */
export const POOL_SIZES: Record<Category, number> = {
    general: 45000,
    ews: 8000,
    obc: 35000,
    sc: 15000,
    st: 10000,
    pwbd: 5000,
};

export const TOTAL_VACANCIES: number = UPSC_CMS_CYCLE.vacancies;

export function categoryInfo(category: Category): CategoryInfo {
    return CATEGORIES.find((c) => c.id === category)!;
}

export function poolForCategory(category: Category): number {
    return POOL_SIZES[category];
}

export function categoryVacancies(category: Category, total: number = TOTAL_VACANCIES): number {
    return Math.max(1, Math.round(total * (categoryInfo(category).vacancyPct / 100)));
}

export interface RankAnalysis {
    equivalentRank: number;
    categoryRank: number;
    vacancies: number;
    selectionChance: 'Very High' | 'High' | 'Moderate' | 'Low' | 'Very Low';
    note: string;
}

export function computeRankAnalysis(rankInput: number, sourceCategory: Category, targetCategory: Category): RankAnalysis {
    const sourcePool = poolForCategory(sourceCategory);
    const targetPool = poolForCategory(targetCategory);

    // Convert the rank to a percentile in the source list, then to the
    // equivalent rank in the target list.
    const sourcePercentile = Math.max(0, Math.min(100, (1 - rankInput / sourcePool) * 100));
    const equivalentRank = sourceCategory === targetCategory
        ? Math.max(1, Math.round(rankInput))
        : Math.max(1, Math.round(targetPool * (1 - sourcePercentile / 100)));

    const vacancies = categoryVacancies(targetCategory);
    const categoryRank = equivalentRank;
    const ratio = categoryRank / vacancies;

    let selectionChance: RankAnalysis['selectionChance'];
    let note: string;
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

    return { equivalentRank, categoryRank, vacancies, selectionChance, note };
}
