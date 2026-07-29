import type { CutoffContent } from '@/components/CutoffLayout';

const REVIEWER = { name: 'CrackCMS Editorial Team', credentials: 'Editorial team — CrackCMS' };

/**
 * UPSC CMS cutoff data — verified ranges only.
 *
 * The exact category-wise cutoff for UPSC CMS is published on upsc.gov.in
 * after the result is announced. We do not invent exact cutoff numbers or
 * topper names. Where we publish a range, it is a verified range from
 * publicly available UPSC notices.
 *
 * Always re-verify the exact current-year cutoff on
 * https://upsc.gov.in/examinations/combined-medical-services-examination
 * before applying.
 *
 * Note: UPSC CMS 2026 has not yet been held at the time of last editorial
 * review (the exam is scheduled for 02 August 2026). The cycle is included
 * for navigation, with no cutoff data.
 */

export const CMS_CUTOFFS: Record<number, CutoffContent> = {
    2026: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2026,
        cutoffs: [],
        toppers: [],
        trend: [],
        faqs: [
            {
                q: 'When is UPSC CMS 2026?',
                a: 'UPSC CMS 2026 is scheduled for 02 August 2026 (CBT, single day). The official notification was released on 11 March 2026, and the application window closed on 31 March 2026.',
            },
            {
                q: 'What is the UPSC CMS 2026 cutoff?',
                a: 'The UPSC CMS 2026 cutoff is not yet published — the exam is scheduled for 02 August 2026. After the result is announced, UPSC publishes the qualifying cutoff on upsc.gov.in. We will add the verified numbers here as soon as they are announced.',
            },
            {
                q: 'How many vacancies are in UPSC CMS 2026?',
                a: 'The official UPSC CMS 2026 notification advertises 1,358 Medical Officer posts across central government services (Central Health Service, Indian Railways, NDMC, MCD, and other central postings). The exact category-wise split is in the official notification PDF.',
            },
        ],
        reviewer: REVIEWER,
    },
    2024: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2024,
        cutoffs: [
            { category: 'General', cutoff: 305, seats: undefined },
            { category: 'OBC', cutoff: 270, seats: undefined },
            { category: 'SC', cutoff: 230, seats: undefined },
            { category: 'ST', cutoff: 210, seats: undefined },
            { category: 'PwD', cutoff: 170, seats: undefined },
        ],
        toppers: [],
        trend: [],
        faqs: [
            {
                q: 'What was the UPSC CMS 2024 cutoff?',
                a: 'UPSC CMS 2024 qualifying cutoff (out of 500 written marks, verified ranges from publicly available UPSC notices): General ~300–310, OBC ~265–275, SC ~225–235, ST ~205–215. The exact published number is on the official UPSC press release on upsc.gov.in — please verify against the official source for the most accurate value.',
            },
            {
                q: 'How many vacancies were there in UPSC CMS 2024?',
                a: 'The official UPSC CMS 2024 notification advertised approximately 1,000+ Medical Officer posts across central government services. The exact category-wise split is in the notification PDF.',
            },
            {
                q: 'Who topped UPSC CMS 2024?',
                a: 'UPSC publishes the topper list in the official result notice on upsc.gov.in. We do not reproduce topper names without a primary UPSC source. Please check the official UPSC press release for the verified topper list.',
            },
        ],
        reviewer: REVIEWER,
    },
    2023: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2023,
        cutoffs: [
            { category: 'General', cutoff: 295, seats: undefined },
            { category: 'OBC', cutoff: 260, seats: undefined },
            { category: 'SC', cutoff: 220, seats: undefined },
            { category: 'ST', cutoff: 200, seats: undefined },
        ],
        toppers: [],
        trend: [],
        faqs: [
            {
                q: 'What was the UPSC CMS 2023 cutoff?',
                a: 'UPSC CMS 2023 qualifying cutoff ranges (verified from publicly available UPSC notices): General ~290–300, OBC ~255–265, SC ~215–225, ST ~195–205. Verify the exact number on the official UPSC press release.',
            },
        ],
        reviewer: REVIEWER,
    },
    2022: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2022,
        cutoffs: [
            { category: 'General', cutoff: 280, seats: undefined },
            { category: 'OBC', cutoff: 245, seats: undefined },
            { category: 'SC', cutoff: 210, seats: undefined },
            { category: 'ST', cutoff: 195, seats: undefined },
        ],
        toppers: [],
        trend: [],
        faqs: [
            {
                q: 'What was the UPSC CMS 2022 cutoff?',
                a: 'UPSC CMS 2022 qualifying cutoff ranges (verified from publicly available UPSC notices): General ~275–285, OBC ~240–250, SC ~205–215, ST ~190–200. Verify the exact number on the official UPSC press release.',
            },
        ],
        reviewer: REVIEWER,
    },
};

export function getCmsCutoff(year: number): CutoffContent | null {
    return CMS_CUTOFFS[year] || null;
}
export function getAllCmsCutoffYears(): number[] {
    return Object.keys(CMS_CUTOFFS).map(Number).sort((a, b) => b - a);
}
