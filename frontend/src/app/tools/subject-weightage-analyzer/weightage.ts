/**
 * Pure logic for the Subject Weightage Analyzer.
 *
 * The official weightage comes from the UPSC CMS question split in
 * lib/examPatterns.ts (Paper I: Medicine 96 + Paediatrics 24; Paper II:
 * Surgery, Gynaecology & Obstetrics and PSM 40 each). Optionally the live
 * per-subject counts of the CrackCMS PYQ bank (/api/questions/stats/) are
 * mapped onto those five subjects.
 */
import { CMS_MARKS_PER_QUESTION, UPSC_CMS_PATTERN, round2 } from '@/lib/examPatterns';

export interface SubjectWeight {
    subject: string;
    paper: string;
    questions: number;
    /** Share of all UPSC CMS questions, in percent (one decimal). */
    sharePct: number;
    /** Marks this subject carries (questions × marks per question). */
    marks: number;
    includes?: string;
}

export function officialCmsWeightage(): SubjectWeight[] {
    const total = UPSC_CMS_PATTERN.totalQuestions;
    return UPSC_CMS_PATTERN.papers.flatMap((paper) =>
        paper.subjects.map((s) => ({
            subject: s.name,
            paper: paper.name,
            questions: s.questions,
            sharePct: Math.round((s.questions / total) * 1000) / 10,
            marks: round2(s.questions * CMS_MARKS_PER_QUESTION),
            includes: s.includes,
        })),
    );
}

/**
 * Question-bank subject codes folded into the five UPSC CMS subjects the way
 * the notice groups them (Dermatology and Psychiatry are part of General
 * Medicine; ENT, Ophthalmology, Orthopaedics and Anaesthesia sit in Surgery).
 */
export const BANK_CODE_TO_CMS_SUBJECT: Record<string, string> = {
    MED: 'General Medicine',
    DER: 'General Medicine',
    PSY: 'General Medicine',
    PED: 'Paediatrics',
    SUR: 'Surgery',
    ENT: 'Surgery',
    OPH: 'Surgery',
    ORT: 'Surgery',
    ANS: 'Surgery',
    OBG: 'Gynaecology & Obstetrics',
    PSM: 'Preventive & Social Medicine',
};

/** Sum bank counts per CMS subject; unknown codes (e.g. "IMPORTED") are ignored. */
export function bankCountsByCmsSubject(
    bySubject: { code?: string | null; count?: number | null }[] | null | undefined,
): Record<string, number> {
    const out: Record<string, number> = {};
    for (const row of bySubject ?? []) {
        const subject = row.code ? BANK_CODE_TO_CMS_SUBJECT[row.code.toUpperCase()] : undefined;
        if (!subject) continue;
        out[subject] = (out[subject] ?? 0) + Math.max(0, Number(row.count) || 0);
    }
    return out;
}
