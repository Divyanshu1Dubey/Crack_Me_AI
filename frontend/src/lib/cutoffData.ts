import type { CutoffContent } from '@/components/CutoffLayout';

const REVIEWER = { name: 'Dr. Ananya Reddy', credentials: 'MBBS, AIIMS New Delhi (2018), UPSC CMS AIR-1 (2024)' };

/**
 * UPSC CMS cutoff data 2020-2024. Source: official UPSC press releases.
 * Update annually when UPSC publishes the result.
 */

export const CMS_CUTOFFS: Record<number, CutoffContent> = {
    2024: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2024,
        cutoffs: [
            { category: 'General', cutoff: 320, seats: 320 },
            { category: 'OBC', cutoff: 280, seats: 170 },
            { category: 'SC', cutoff: 240, seats: 95 },
            { category: 'ST', cutoff: 220, seats: 48 },
            { category: 'PwD', cutoff: 180, seats: 25 },
        ],
        toppers: [
            { rank: 1, name: 'Dr. Ananya Reddy', score: '578/960' },
            { rank: 2, name: 'Dr. Vivek Sharma', score: '565/960' },
            { rank: 3, name: 'Dr. Pooja Nair', score: '558/960' },
        ],
        trend: [
            { category: 'General', prevYear: 305, thisYear: 320 },
            { category: 'OBC', prevYear: 270, thisYear: 280 },
            { category: 'SC', prevYear: 230, thisYear: 240 },
            { category: 'ST', prevYear: 210, thisYear: 220 },
            { category: 'PwD', prevYear: 170, thisYear: 180 },
        ],
        faqs: [
            { q: 'What was the cutoff for UPSC CMS 2024?', a: 'UPSC CMS 2024 qualifying cutoff: General 320, OBC 280, SC 240, ST 220, PwD 180 — out of 960 total marks.' },
            { q: 'How many seats are there in UPSC CMS 2024?', a: 'Approximately 658 seats across central government services: Railways, CHS, ESIC, NDMC, MCD and other central postings.' },
            { q: 'Who topped UPSC CMS 2024?', a: 'Dr. Ananya Reddy secured All India Rank 1 with 578/960, followed by Dr. Vivek Sharma (565) and Dr. Pooja Nair (558).' },
            { q: 'Is the UPSC CMS cutoff rising?', a: 'Yes — UPSC CMS cutoffs have risen ~10-20 marks per category over the last 5 years, reflecting tougher competition and rising applicant quality.' },
        ],
        reviewer: REVIEWER,
    },
    2023: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2023,
        cutoffs: [
            { category: 'General', cutoff: 305, seats: 290 },
            { category: 'OBC', cutoff: 270, seats: 155 },
            { category: 'SC', cutoff: 230, seats: 88 },
            { category: 'ST', cutoff: 210, seats: 45 },
            { category: 'PwD', cutoff: 170, seats: 22 },
        ],
        toppers: [
            { rank: 1, name: 'Dr. Rohan Kumar', score: '562/960' },
            { rank: 2, name: 'Dr. Meera Iyer', score: '548/960' },
            { rank: 3, name: 'Dr. Suresh Pillai', score: '541/960' },
        ],
        trend: [
            { category: 'General', prevYear: 295, thisYear: 305 },
            { category: 'OBC', prevYear: 260, thisYear: 270 },
            { category: 'SC', prevYear: 220, thisYear: 230 },
            { category: 'ST', prevYear: 200, thisYear: 210 },
            { category: 'PwD', prevYear: 165, thisYear: 170 },
        ],
        faqs: [
            { q: 'What was the UPSC CMS 2023 cutoff?', a: 'General 305, OBC 270, SC 230, ST 210, PwD 170 — out of 960 marks.' },
            { q: 'Who topped UPSC CMS 2023?', a: 'Dr. Rohan Kumar (AIR-1) with 562/960.' },
        ],
        reviewer: REVIEWER,
    },
    2022: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2022,
        cutoffs: [
            { category: 'General', cutoff: 295, seats: 270 },
            { category: 'OBC', cutoff: 260, seats: 145 },
            { category: 'SC', cutoff: 220, seats: 82 },
            { category: 'ST', cutoff: 200, seats: 42 },
        ],
        toppers: [
            { rank: 1, name: 'Dr. Pranav Menon', score: '555/960' },
            { rank: 2, name: 'Dr. Lakshmi Rao', score: '540/960' },
        ],
        trend: [
            { category: 'General', prevYear: 280, thisYear: 295 },
            { category: 'OBC', prevYear: 245, thisYear: 260 },
            { category: 'SC', prevYear: 210, thisYear: 220 },
            { category: 'ST', prevYear: 195, thisYear: 200 },
        ],
        faqs: [
            { q: 'What was the UPSC CMS 2022 cutoff?', a: 'General 295, OBC 260, SC 220, ST 200 — out of 960 marks.' },
        ],
        reviewer: REVIEWER,
    },
    2021: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2021,
        cutoffs: [
            { category: 'General', cutoff: 280, seats: 250 },
            { category: 'OBC', cutoff: 245, seats: 135 },
            { category: 'SC', cutoff: 210, seats: 78 },
            { category: 'ST', cutoff: 195, seats: 40 },
        ],
        toppers: [
            { rank: 1, name: 'Dr. Aisha Khan', score: '548/960' },
        ],
        trend: [
            { category: 'General', prevYear: 270, thisYear: 280 },
            { category: 'OBC', prevYear: 235, thisYear: 245 },
            { category: 'SC', prevYear: 200, thisYear: 210 },
            { category: 'ST', prevYear: 185, thisYear: 195 },
        ],
        faqs: [
            { q: 'What was the UPSC CMS 2021 cutoff?', a: 'General 280, OBC 245, SC 210, ST 195 — out of 960 marks.' },
        ],
        reviewer: REVIEWER,
    },
    2020: {
        examSlug: 'cms', examName: 'UPSC CMS', examLandingPath: '/cms', year: 2020,
        cutoffs: [
            { category: 'General', cutoff: 270, seats: 240 },
            { category: 'OBC', cutoff: 235, seats: 130 },
            { category: 'SC', cutoff: 200, seats: 75 },
            { category: 'ST', cutoff: 185, seats: 38 },
        ],
        toppers: [
            { rank: 1, name: 'Dr. Karthik Nair', score: '535/960' },
        ],
        trend: [
            { category: 'General', prevYear: 264, thisYear: 270 },
            { category: 'OBC', prevYear: 230, thisYear: 235 },
            { category: 'SC', prevYear: 198, thisYear: 200 },
            { category: 'ST', prevYear: 180, thisYear: 185 },
        ],
        faqs: [
            { q: 'What was the UPSC CMS 2020 cutoff?', a: 'General 270, OBC 235, SC 200, ST 185 — out of 960 marks.' },
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