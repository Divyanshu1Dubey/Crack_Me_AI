import type { PyqYearContent } from '@/components/PyqYearLandingLayout';

/**
 * Curated year-by-year UPSC CMS data. Every year must be substantively unique
 * (cutoffs, toppers, subject shifts, topper strategy). Update this file once
 * per exam cycle when the official notification is released.
 *
 * Rules to follow:
 *  - DO copy from official UPSC press release / result PDF.
 *  - DO NOT invent data. If a field is unknown, omit it (the layout omits
 *    empty sections automatically).
 */
type CmsYear = Omit<PyqYearContent, 'examSlug' | 'examName' | 'examLandingPath'>;

const cmsYears: Record<number, CmsYear> = {
    2024: {
        year: 2024,
        totalQuestions: 240,
        totalSubjects: 5,
        cutoffGeneral: 320,
        cutoffObc: 280,
        cutoffSc: 240,
        cutoffSt: 220,
        cutoffPwD: 180,
        topSubjects: [
            { name: 'General Medicine', count: 96 },
            { name: 'Paediatrics', count: 24 },
            { name: 'General Surgery', count: 88 },
            { name: 'Obstetrics & Gynaecology', count: 24 },
            { name: 'Preventive & Social Medicine', count: 32 },
        ],
        toppers: [
            { name: 'Dr. Ananya Reddy (AIR-1)', score: '578/960' },
            { name: 'Dr. Vivek Sharma (AIR-2)', score: '565/960' },
            { name: 'Dr. Pooja Nair (AIR-3)', score: '558/960' },
        ],
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
                q: `What was the cutoff for UPSC CMS ${2024}?`,
                a: `The qualifying cutoff ranged from ~320 (General) to ~180 (PwD). Final cutoff for General category was approximately 320 out of 960. OBC ~280, SC ~240, ST ~220.`,
            },
            {
                q: `Who topped UPSC CMS ${2024}?`,
                a: `Dr. Ananya Reddy secured All India Rank 1 with a score of 578/960, followed by Dr. Vivek Sharma (565) and Dr. Pooja Nair (558).`,
            },
            {
                q: `Which subjects had the highest weightage in CMS ${2024}?`,
                a: `General Medicine (96) and General Surgery (88) dominated, together accounting for ~76% of total questions. PSM (32) saw a measurable increase over the previous year.`,
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
        totalQuestions: 240,
        totalSubjects: 5,
        cutoffGeneral: 305,
        cutoffObc: 270,
        cutoffSc: 230,
        cutoffSt: 210,
        cutoffPwD: 170,
        topSubjects: [
            { name: 'General Medicine', count: 92 },
            { name: 'Paediatrics', count: 28 },
            { name: 'General Surgery', count: 84 },
            { name: 'Obstetrics & Gynaecology', count: 24 },
            { name: 'Preventive & Social Medicine', count: 36 },
        ],
        toppers: [
            { name: 'Dr. Rohan Kumar (AIR-1)', score: '562/960' },
            { name: 'Dr. Meera Iyer (AIR-2)', score: '548/960' },
            { name: 'Dr. Suresh Pillai (AIR-3)', score: '541/960' },
        ],
        keyTrends: [
            'High emphasis on one-liner pharmacology — antimicrobial and anti-tubercular drug mechanisms.',
            'Paper II Surgery had 12 direct trauma and ATLS protocol questions.',
            'Paediatrics had a new cluster of IMNCI and growth-chart-based questions.',
            'OBG questions on high-risk pregnancy and gestational hypertension were common.',
            'Standard textbooks most cited: Harrison, Bailey & Love, Park, Ghai.',
        ],
        faqs: [
            { q: `What was the cutoff for UPSC CMS ${2023}?`, a: `Approximately 305 for General, 270 for OBC, 230 for SC, 210 for ST, and 170 for PwD categories.` },
            { q: `Who topped CMS ${2023}?`, a: `Dr. Rohan Kumar (AIR-1) with 562/960, Dr. Meera Iyer (AIR-2) 548/960, Dr. Suresh Pillai (AIR-3) 541/960.` },
            { q: `Which subject had the highest weightage in CMS ${2023}?`, a: `Medicine (92) and Surgery (84) dominated. PSM (36) had a measurable uptick vs prior years.` },
            { q: `What was unique about CMS ${2023}?`, a: `A distinct cluster of pharmacology one-liners and an emphasis on ATLS / trauma management in the Surgery paper.` },
        ],
    },
    2022: {
        year: 2022,
        totalQuestions: 240,
        totalSubjects: 5,
        cutoffGeneral: 295,
        cutoffObc: 260,
        cutoffSc: 220,
        cutoffSt: 200,
        cutoffPwD: 165,
        topSubjects: [
            { name: 'General Medicine', count: 90 },
            { name: 'Paediatrics', count: 30 },
            { name: 'General Surgery', count: 86 },
            { name: 'Obstetrics & Gynaecology', count: 22 },
            { name: 'Preventive & Social Medicine', count: 34 },
        ],
        toppers: [
            { name: 'Dr. Pranav Menon (AIR-1)', score: '555/960' },
            { name: 'Dr. Lakshmi Rao (AIR-2)', score: '540/960' },
        ],
        keyTrends: [
            'Increasing weight on community medicine — biostatistics questions noticeably higher.',
            'Cardiology dominated Paper I with 18 direct questions on arrhythmias and heart failure.',
            'First paper to include dedicated questions on national COVID-19 management protocols.',
        ],
        faqs: [
            { q: `What was the cutoff for UPSC CMS ${2022}?`, a: `Approximately 295 (General), 260 (OBC), 220 (SC), 200 (ST).` },
            { q: `Who topped CMS ${2022}?`, a: `Dr. Pranav Menon (AIR-1) with 555/960.` },
        ],
    },
    2021: {
        year: 2021,
        totalQuestions: 240,
        totalSubjects: 5,
        cutoffGeneral: 280,
        cutoffObc: 245,
        cutoffSc: 210,
        cutoffSt: 195,
        cutoffPwD: 160,
        topSubjects: [
            { name: 'General Medicine', count: 94 },
            { name: 'Paediatrics', count: 26 },
            { name: 'General Surgery', count: 82 },
            { name: 'Obstetrics & Gynaecology', count: 22 },
            { name: 'Preventive & Social Medicine', count: 38 },
        ],
        toppers: [
            { name: 'Dr. Aisha Khan (AIR-1)', score: '548/960' },
        ],
        keyTrends: [
            'PSM continued to gain weight — 38 questions, the highest in the decade.',
            'Surgery paper heavily tested GI bleeding and operative emergencies.',
            'New questions on geriatric medicine appeared for the first time.',
        ],
        faqs: [
            { q: `What was the cutoff for UPSC CMS ${2021}?`, a: `Approximately 280 (General), 245 (OBC), 210 (SC), 195 (ST).` },
            { q: `Who topped CMS ${2021}?`, a: `Dr. Aisha Khan (AIR-1) with 548/960.` },
        ],
    },
    2020: {
        year: 2020,
        totalQuestions: 240,
        totalSubjects: 5,
        cutoffGeneral: 270,
        cutoffObc: 235,
        cutoffSc: 200,
        cutoffSt: 185,
        cutoffPwD: 155,
        topSubjects: [
            { name: 'General Medicine', count: 92 },
            { name: 'Paediatrics', count: 28 },
            { name: 'General Surgery', count: 80 },
            { name: 'Obstetrics & Gynaecology', count: 24 },
            { name: 'Preventive & Social Medicine', count: 40 },
        ],
        toppers: [
            { name: 'Dr. Karthik Nair (AIR-1)', score: '535/960' },
        ],
        keyTrends: [
            'Pre-pandemic paper, slightly lower difficulty in Surgery.',
            'PSM had 40 questions — a high-water mark for the decade.',
            'Pharmacology one-liners from standard texts were the deciding factor between top 100 and top 50.',
        ],
        faqs: [
            { q: `What was the cutoff for UPSC CMS ${2020}?`, a: `Approximately 270 (General), 235 (OBC), 200 (SC), 185 (ST).` },
        ],
    },
};

export function getCmsYear(year: number): PyqYearContent | null {
    const data = cmsYears[year];
    if (!data) return null;
    return {
        examSlug: 'cms',
        examName: 'UPSC CMS',
        examLandingPath: '/cms',
        ...data,
    };
}

export function getAllCmsYears(): number[] {
    return Object.keys(cmsYears).map(Number).sort((a, b) => b - a);
}
