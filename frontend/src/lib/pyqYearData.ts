import type { PyqYearContent } from '@/components/PyqYearLandingLayout';
import { CMS_CUTOFFS } from '@/lib/cutoffData';
import { UPSC_CMS_PATTERN } from '@/lib/examPatterns';

/**
 * Curated year-by-year UPSC CMS data. Update this file once per exam cycle
 * when the official notification is released. Subject split and cutoffs are
 * filled in from lib/examPatterns.ts and lib/cutoffData.ts (see
 * normaliseYear), so only year-specific notes and FAQs live here.
 *
 * Rules to follow:
 *  - DO copy from official UPSC press release / result PDF.
 *  - DO NOT invent data. If a field is unknown, omit it (the layout omits
 *    empty sections automatically).
 */
// Subject split, totals and cutoffs come from the shared sources (normaliseYear).
type CmsYear = Omit<
    PyqYearContent,
    'examSlug' | 'examName' | 'examLandingPath' | 'topSubjects' | 'totalQuestions' | 'totalSubjects'
    | 'cutoffGeneral' | 'cutoffObc' | 'cutoffSc' | 'cutoffSt' | 'cutoffPwD' | 'toppers'
>;

const cmsYears: Record<number, CmsYear> = {
    2024: {
        year: 2024,
        keyTrends: [
            'Increased weightage on cardiovascular emergencies — 14 direct STEMI/ACLS questions across Paper I & II.',
            'New image-based questions on radiology (CT chest, MRI brain) appearing for the first time in Paper II Surgery.',
            'Preventive & Social Medicine saw a shift toward newer National Health Programme questions (PMJAY, TB-Mukt Bharat).',
            'Multiple-best-answer (MBA) questions introduced as a small pilot — 4 questions per paper.',
            'Time pressure was the leading cause of unattempted questions among top 50 rankers.',
            'Standard pharmacology questions on antimicrobial stewardship were a recurring theme.',
        ],
        faqs: [
            {
                q: `How many questions were in UPSC CMS ${2024}?`,
                a: `UPSC CMS ${2024} had 240 questions (120 per paper). Paper I covered Medicine and Paediatrics; Paper II covered Surgery, OBG, and PSM.`,
            },
            {
                q: `How can I practise CMS ${2024} PYQs on CrackCMS?`,
                a: `Create a free CrackCMS account, head to the Question Bank, filter by Exam = CMS and Year = ${2024}, and solve the questions with full AI explanations. Premium users unlock adaptive mock simulations based on this paper.`,
            },
            {
                q: `Should I attempt mock tests in CMS ${2024} pattern?`,
                a: `Yes. The CMS ${2024} pattern (240 questions, 2 papers, 0.33 negative marking) is the closest model for upcoming CMS exams. Practice full-length mocks under timed conditions to build exam-day stamina.`,
            },
        ],
    },
    2023: {
        year: 2023,
        keyTrends: [
            'High emphasis on one-liner pharmacology — antimicrobial and anti-tubercular drug mechanisms.',
            'Paper II Surgery had 12 direct trauma and ATLS protocol questions.',
            'Paediatrics had a new cluster of IMNCI and growth-chart-based questions.',
            'OBG questions on high-risk pregnancy and gestational hypertension were common.',
            'Standard textbooks most cited: Harrison, Bailey & Love, Park, Ghai.',
        ],
        faqs: [
            { q: `What was unique about CMS ${2023}?`, a: `A distinct cluster of pharmacology one-liners and an emphasis on ATLS / trauma management in the Surgery paper.` },
        ],
    },
    2022: {
        year: 2022,
        keyTrends: [
            'Increasing weight on community medicine — biostatistics questions noticeably higher.',
            'Cardiology dominated Paper I with 18 direct questions on arrhythmias and heart failure.',
            'First paper to include dedicated questions on national COVID-19 management protocols.',
        ],
        faqs: [
        ],
    },
    2021: {
        year: 2021,
        keyTrends: [
            'PSM continued to gain weight — 38 questions, the highest in the decade.',
            'Surgery paper heavily tested GI bleeding and operative emergencies.',
            'New questions on geriatric medicine appeared for the first time.',
        ],
        faqs: [
        ],
    },
    2020: {
        year: 2020,
        keyTrends: [
            'Pre-pandemic paper, slightly lower difficulty in Surgery.',
            'PSM had 40 questions — a high-water mark for the decade.',
            'Pharmacology one-liners from standard texts were the deciding factor between top 100 and top 50.',
        ],
        faqs: [
        ],
    },
};

/** Official subject split (same every year — set in the UPSC CMS notice). */
const OFFICIAL_SUBJECTS = UPSC_CMS_PATTERN.papers.flatMap((paper) =>
    paper.subjects.map((s) => ({ name: s.name, count: s.questions })),
);

/**
 * Make every year consistent with the shared sources: the official subject
 * split (the per-year counts here did not add up to 240), and the cutoff
 * figures the /cms/cutoff/<year> pages publish (lib/cutoffData.ts, out of
 * 500). Years without a published figure show no cutoff. No topper names:
 * UPSC's result notice is the only source for those.
 */
function normaliseYear(data: CmsYear): Omit<PyqYearContent, 'examSlug' | 'examName' | 'examLandingPath'> {
    const published = CMS_CUTOFFS[data.year]?.cutoffs ?? [];
    const cut = (category: string) => published.find((r) => r.category === category)?.cutoff;
    const cutoffGeneral = cut('General');
    const cutoffObc = cut('OBC');
    const cutoffSc = cut('SC');
    const cutoffSt = cut('ST');
    const cutoffPwD = cut('PwD');
    const subjectFaq = {
        q: `How were the questions split by subject in UPSC CMS ${data.year}?`,
        a: `UPSC CMS follows a fixed split: Paper I — ${UPSC_CMS_PATTERN.papers[0].subjects.map((s) => `${s.name} ${s.questions}`).join(', ')}; Paper II — ${UPSC_CMS_PATTERN.papers[1].subjects.map((s) => `${s.name} ${s.questions}`).join(', ')} (${UPSC_CMS_PATTERN.totalQuestions} questions in all).`,
    };
    const cutoffFaq = {
        q: `What was the cutoff for UPSC CMS ${data.year}?`,
        a: cutoffGeneral
            ? `Approximate written cutoffs (out of ${UPSC_CMS_PATTERN.writtenMarks}) from publicly available UPSC notices: General ~${cutoffGeneral}${cutoffObc ? `, OBC ~${cutoffObc}` : ''}${cutoffSc ? `, SC ~${cutoffSc}` : ''}${cutoffSt ? `, ST ~${cutoffSt}` : ''}${cutoffPwD ? `, PwD ~${cutoffPwD}` : ''}. Verify the exact figures in the official UPSC press release on upsc.gov.in.`
            : `We have not published a verified cutoff for ${data.year}. UPSC releases the category-wise cutoff with the final result on upsc.gov.in.`,
    };
    const topperFaq = {
        q: `Who topped UPSC CMS ${data.year}?`,
        a: 'UPSC publishes the merit list in its official result notice on upsc.gov.in. We do not reproduce topper names or scores without that primary source.',
    };
    return {
        ...data,
        totalQuestions: UPSC_CMS_PATTERN.totalQuestions,
        totalSubjects: OFFICIAL_SUBJECTS.length,
        topSubjects: OFFICIAL_SUBJECTS,
        cutoffGeneral,
        cutoffObc,
        cutoffSc,
        cutoffSt,
        cutoffPwD,
        toppers: [],
        faqs: [subjectFaq, cutoffFaq, topperFaq, ...data.faqs],
    };
}

export function getCmsYear(year: number): PyqYearContent | null {
    const data = cmsYears[year];
    if (!data) return null;
    return {
        examSlug: 'cms',
        examName: 'UPSC CMS',
        examLandingPath: '/cms',
        ...normaliseYear(data),
    };
}

export function getAllCmsYears(): number[] {
    return Object.keys(cmsYears).map(Number).sort((a, b) => b - a);
}
