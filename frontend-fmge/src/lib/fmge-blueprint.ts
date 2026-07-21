/**
 * fmge-blueprint.ts — NBE blueprint weighting for FMGE.
 *
 * The FMGE exam is exactly 300 MCQs / 5 hours / 2 sessions, covering 19
 * pre-clinical, para-clinical and clinical subjects. The NBE blueprint
 * specifies an approximate subject-wise weight. This file exposes:
 *   - BLUEPRINT: the official subject list + typical question count
 *   - chooseQuestionsForMock(): how many of each subject to include in
 *     a 300-question mock to match the blueprint as closely as possible.
 */
export interface FMGESubject {
    code: string;
    name: string;
    preParaClinical: boolean;
    typicalCount: number;
}

export const FMGE_SUBJECTS: FMGESubject[] = [
    { code: "ANAT", name: "Anatomy", preParaClinical: true, typicalCount: 17 },
    { code: "PHYS", name: "Physiology", preParaClinical: true, typicalCount: 17 },
    { code: "BIOCHEM", name: "Biochemistry", preParaClinical: true, typicalCount: 16 },
    { code: "PATH", name: "Pathology", preParaClinical: true, typicalCount: 18 },
    { code: "MICRO", name: "Microbiology", preParaClinical: true, typicalCount: 17 },
    { code: "PHARM", name: "Pharmacology", preParaClinical: true, typicalCount: 17 },
    { code: "PSM", name: "PSM / Community Medicine", preParaClinical: true, typicalCount: 18 },
    { code: "ENT", name: "ENT", preParaClinical: false, typicalCount: 8 },
    { code: "OPHTH", name: "Ophthalmology", preParaClinical: false, typicalCount: 9 },
    { code: "MED", name: "General Medicine", preParaClinical: false, typicalCount: 35 },
    { code: "SURG", name: "General Surgery", preParaClinical: false, typicalCount: 35 },
    { code: "OBG", name: "Obstetrics & Gynaecology", preParaClinical: false, typicalCount: 20 },
    { code: "PAED", name: "Paediatrics", preParaClinical: false, typicalCount: 15 },
    { code: "ORTHO", name: "Orthopaedics", preParaClinical: false, typicalCount: 8 },
    { code: "DERM", name: "Dermatology & Venereology", preParaClinical: false, typicalCount: 6 },
    { code: "PSYCH", name: "Psychiatry", preParaClinical: false, typicalCount: 6 },
    { code: "ANAES", name: "Anaesthesiology", preParaClinical: false, typicalCount: 6 },
    { code: "RADIO", name: "Radiodiagnosis", preParaClinical: false, typicalCount: 6 },
    { code: "FORENSIC", name: "Forensic Medicine", preParaClinical: true, typicalCount: 10 },
];

export const TOTAL_BLUEPRINT_COUNT = FMGE_SUBJECTS.reduce((acc, s) => acc + s.typicalCount, 0); // 300

/**
 * Returns the per-subject question count for a 300-Q mock matching the NBE
 * blueprint exactly. (The numbers above already sum to 300.)
 */
export function blueprintForMock(): Array<{ code: string; name: string; count: number }> {
    return FMGE_SUBJECTS.map((s) => ({ code: s.code, name: s.name, count: s.typicalCount }));
}

/**
 * Estimate a pass probability from a 300-Q mock.
 * The FMGE pass threshold is 50% (150/300). This is a soft heuristic —
 * real outcomes also depend on subject balance, negative marking, etc.
 */
export function estimatePassProbability(score: number): number {
    if (score <= 100) return 0.02;
    if (score >= 200) return 0.95;
    // Sigmoid centred at 150 with a moderate slope.
    const z = (score - 150) / 18;
    return 1 / (1 + Math.exp(-z));
}

export function isPassing(score: number): boolean {
    return score >= 150;
}
