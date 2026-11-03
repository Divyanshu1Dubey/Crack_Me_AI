/**
 * UPSC CMS "college predictor" model (pure, unit-tested with Node).
 *
 * UPSC CMS does not fill posts at AIIMS, PGIMER, JIPMER or NIMHANS (those
 * institutes recruit separately); it recommends candidates for four
 * general-duty services, allocated by rank and the candidate's preference
 * order. This used to list those institutes with invented "closing ranks".
 *
 * There is no official service-wise closing-rank data in this codebase, so
 * no per-service rank is made up here. The estimate is per category: the
 * illustrative last rank a category can reach is its share of the advertised
 * vacancies (the same reservation model as the Category Rank Filter tool).
 * Which of the four services you then get depends on your preferences and
 * those of the candidates ranked above you.
 */
import { CATEGORIES, categoryVacancies, type Category } from '../category-rank-filter/rankModel';

export interface CmsService {
    id: 'chs' | 'railways' | 'ndmc' | 'mcd';
    name: string;
    group: 'Category I' | 'Category II';
}

/** The services UPSC CMS recruits for (Category I and Category II posts). */
export const CMS_SERVICES: CmsService[] = [
    { id: 'chs', name: 'Central Health Service — General Duty Medical Officer (GDMO) sub-cadre', group: 'Category I' },
    { id: 'railways', name: 'Indian Railways — Assistant Divisional Medical Officer (ADMO)', group: 'Category II' },
    { id: 'ndmc', name: 'New Delhi Municipal Council — General Duty Medical Officer', group: 'Category II' },
    { id: 'mcd', name: 'Municipal Corporation of Delhi — General Duty Medical Officer Gr-II', group: 'Category II' },
];

export type Band = 'safe' | 'moderate' | 'reach';

export interface ServicePrediction {
    band: Band;
    categoryLabel: string;
    /** Illustrative last rank in the category's list (its share of vacancies). */
    illustrativeLimit: number;
    services: CmsService[];
}

/** Ranks within 60% of the category limit are "high confidence". */
const SAFE_RATIO = 0.6;

export function predictServices(rank: number, category: Category): ServicePrediction | null {
    if (!Number.isFinite(rank) || rank <= 0) return null;
    const info = CATEGORIES.find((c) => c.id === category) ?? CATEGORIES[0];
    const limit = categoryVacancies(info.id);
    const ratio = rank / limit;
    const band: Band = ratio <= SAFE_RATIO ? 'safe' : ratio <= 1 ? 'moderate' : 'reach';
    return { band, categoryLabel: info.label, illustrativeLimit: limit, services: CMS_SERVICES };
}
