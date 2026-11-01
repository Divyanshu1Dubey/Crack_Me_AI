/**
 * examPatterns.ts — single source of truth for exam-pattern facts.
 *
 * Every public page, FAQ, JSON-LD block and calculator that states how an
 * exam is marked should read from here, so the numbers cannot drift apart
 * again (they used to: /cms said 4 marks per question, /cms/exam-pattern
 * said 960 marks in OMR mode, the Score Calculator used +3/-1 and the rank
 * predictor assumed an 800-mark interview).
 *
 * UPSC CMS source: the "Plan of Examination" in the UPSC Combined Medical
 * Services Examination notice — Part I is a Computer Based Examination of
 * 500 marks (Paper I and Paper II, 250 marks and 120 questions each, two
 * hours each) and Part II is a Personality Test of 100 marks. A wrong answer
 * costs one-third of the marks assigned to that question; an unanswered
 * question costs nothing. Re-check each year's notice on upsc.gov.in before
 * changing a value here.
 *
 * Keep this file free of imports (it is unit-tested directly with Node).
 */

export interface ExamSubjectSplit {
    name: string;
    /** Number of questions UPSC sets from this subject in the paper. */
    questions: number;
    /** Sub-specialities the notice folds into this subject. */
    includes?: string;
}

export interface ExamPaper {
    name: string;
    questions: number;
    marks: number;
    durationMinutes: number;
    subjects: ExamSubjectSplit[];
}

export const UPSC_CMS_PATTERN = {
    examName: 'UPSC CMS',
    fullName: 'UPSC Combined Medical Services Examination',
    conductingBody: 'Union Public Service Commission (UPSC)',
    mode: 'Computer-Based Test (CBT)',
    modeShort: 'CBT',
    papers: [
        {
            name: 'Paper I',
            questions: 120,
            marks: 250,
            durationMinutes: 120,
            subjects: [
                { name: 'General Medicine', questions: 96, includes: 'Cardiology, Neurology, Dermatology and Psychiatry' },
                { name: 'Paediatrics', questions: 24 },
            ],
        },
        {
            name: 'Paper II',
            questions: 120,
            marks: 250,
            durationMinutes: 120,
            subjects: [
                { name: 'Surgery', questions: 40, includes: 'ENT, Ophthalmology, Traumatology and Orthopaedics' },
                { name: 'Gynaecology & Obstetrics', questions: 40 },
                { name: 'Preventive & Social Medicine', questions: 40 },
            ],
        },
    ] as ExamPaper[],
    totalQuestions: 240,
    writtenMarks: 500,
    personalityTestMarks: 100,
    totalMarks: 600,
    /** Fraction of a question's marks deducted for a wrong answer. */
    negativeMarkingFraction: 1 / 3,
    ageLimit: 'Below 32 years on 1 August of the exam year (relaxations as per UPSC rules)',
} as const;

/** Marks a correct answer earns in a UPSC CMS paper (250 / 120 ≈ 2.083). */
export const CMS_MARKS_PER_QUESTION = UPSC_CMS_PATTERN.papers[0].marks / UPSC_CMS_PATTERN.papers[0].questions;

/** Marks a wrong answer costs in a UPSC CMS paper (one-third of 2.083 ≈ 0.694). */
export const CMS_PENALTY_PER_WRONG = CMS_MARKS_PER_QUESTION * UPSC_CMS_PATTERN.negativeMarkingFraction;

/** Round to two decimals for display (2.0833 → 2.08). */
export function round2(value: number): number {
    return Math.round(value * 100) / 100;
}

/** "+2.08 / −0.69" — the per-question marking scheme as shown on pages. */
export const CMS_MARKING_LABEL = `+${round2(CMS_MARKS_PER_QUESTION).toFixed(2)} / −${round2(CMS_PENALTY_PER_WRONG).toFixed(2)}`;

/** One-line plain-English description used in FAQs and tables. */
export const CMS_NEGATIVE_MARKING_TEXT =
    `One-third of the question's marks per wrong answer (−${round2(CMS_PENALTY_PER_WRONG).toFixed(2)} of ${round2(CMS_MARKS_PER_QUESTION).toFixed(2)}); no penalty for unanswered questions`;

/** Short "Paper I (…) + Paper II (…)" summary for tables. */
export const CMS_SUBJECTS_SUMMARY = UPSC_CMS_PATTERN.papers
    .map((p) => `${p.name}: ${p.subjects.map((s) => s.name).join(', ')}`)
    .join(' · ');

export interface ScoreInput {
    correct: number;
    incorrect: number;
}

export interface ScoreBreakdown {
    correctMarks: number;
    penalty: number;
    score: number;
}

/**
 * Score a UPSC CMS attempt (one paper or both — the per-question marks are
 * the same in both papers). Negative inputs are treated as zero.
 */
export function scoreCmsAttempt({ correct, incorrect }: ScoreInput): ScoreBreakdown {
    const c = Math.max(0, Number.isFinite(correct) ? correct : 0);
    const w = Math.max(0, Number.isFinite(incorrect) ? incorrect : 0);
    const correctMarks = c * CMS_MARKS_PER_QUESTION;
    const penalty = w * CMS_PENALTY_PER_WRONG;
    return {
        correctMarks: round2(correctMarks),
        penalty: round2(penalty),
        score: round2(correctMarks - penalty),
    };
}

/** Maximum marks for a given number of UPSC CMS questions. */
export function cmsMaxMarks(totalQuestions: number): number {
    return round2(Math.max(0, totalQuestions) * CMS_MARKS_PER_QUESTION);
}

/**
 * Current UPSC CMS cycle facts quoted on public pages. The vacancy figure is
 * the one the site already publishes for the 2026 notice (cutoffData.ts and
 * the /cms FAQ) — update both together.
 */
export const UPSC_CMS_CYCLE = {
    year: 2026,
    examDate: '2026-08-02',
    vacancies: 1358,
} as const;

export interface ExamDate {
    name: string;
    /** ISO date (YYYY-MM-DD), local exam day. */
    date: string;
    href: string;
}

/**
 * Exam days shown by the homepage countdown. Concluded dates are hidden
 * automatically (see upcomingExamDates); add the next cycle's dates here once
 * the official notices are out.
 */
export const EXAM_DATES: ExamDate[] = [
    { name: 'UPSC CMS 2026', date: UPSC_CMS_CYCLE.examDate, href: '/cms' },
    { name: 'NEET PG 2026', date: '2026-08-30', href: '/neet-pg' },
];

/** Exam dates that have not finished yet, soonest first. */
export function upcomingExamDates(now: Date = new Date(), dates: ExamDate[] = EXAM_DATES): ExamDate[] {
    return dates
        .filter((d) => {
            // An exam day counts as upcoming until the end of that day.
            const end = new Date(`${d.date}T23:59:59`);
            return !Number.isNaN(end.getTime()) && end.getTime() >= now.getTime();
        })
        .sort((a, b) => (a.date < b.date ? -1 : 1));
}

export const NEET_PG_PATTERN = {
    examName: 'NEET PG',
    conductingBody: 'National Board of Examinations in Medical Sciences (NBEMS)',
    mode: 'Computer-Based Test (CBT)',
    totalQuestions: 200,
    marksPerQuestion: 4,
    penaltyPerWrong: 1,
    totalMarks: 800,
    durationMinutes: 210,
    negativeMarkingText: 'Yes — −1 per wrong answer (+4 per correct answer)',
} as const;

export const INI_CET_PATTERN = {
    examName: 'INI-CET',
    conductingBody: 'AIIMS New Delhi',
    mode: 'Computer-Based Test (CBT)',
    totalQuestions: 200,
    marksPerQuestion: 1,
    negativeMarkingFraction: 1 / 3,
    totalMarks: 200,
    durationMinutes: 180,
    negativeMarkingText: 'Yes — one-third of a mark per wrong answer (+1 per correct answer)',
} as const;

export const FMGE_PATTERN = {
    examName: 'FMGE',
    conductingBody: 'NBEMS (on behalf of the NMC)',
    mode: 'Computer-Based Test (CBT)',
    totalQuestions: 300,
    parts: 2,
    questionsPerPart: 150,
    minutesPerPart: 150,
    passMarks: 150,
    negativeMarkingText: 'No negative marking',
} as const;
