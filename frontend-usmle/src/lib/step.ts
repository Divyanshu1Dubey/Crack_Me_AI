/**
 * step.ts — USMLE Step switcher helpers.
 * The backend `Question` model uses an `exam_track` enum; we keep a small
 * mapping here so UI can address each Step cleanly.
 */
export type USMLEStep = "step1" | "step2_ck" | "step3";

export const STEP_INFO: Record<USMLEStep, { label: string; fullName: string; tagline: string; questionCount?: number }> = {
    step1: {
        label: "Step 1",
        fullName: "USMLE Step 1",
        tagline: "Pre-clinical basic science foundation",
    },
    step2_ck: {
        label: "Step 2 CK",
        fullName: "USMLE Step 2 CK",
        tagline: "Clinical knowledge, supervised patient care",
    },
    step3: {
        label: "Step 3",
        fullName: "USMLE Step 3",
        tagline: "Independent clinical practice",
    },
};

/**
 * Convert a percent-correct score to an estimated 3-digit Step score.
 * Calibration is approximate — the real curve shifts by year. Use only
 * for aspirational tracking, never for predictive assessment.
 */
export function estimateStepScore(pct: number, step: USMLEStep): number {
    const clamped = Math.max(0, Math.min(100, pct));
    switch (step) {
        case "step1":
            // Step 1 (pass/fail since 2022, but historically 192–300 scale).
            // Map 50% → 192, 75% → 235, 90% → 260, 100% → 300.
            if (clamped < 50) return 192;
            return Math.round(192 + ((clamped - 50) / 50) * 108);
        case "step2_ck":
            // Step 2 CK scale ~194–300, passing 218.
            if (clamped < 50) return 194;
            return Math.round(194 + ((clamped - 50) / 50) * 106);
        case "step3":
            // Step 3 scale ~196–300, passing 200.
            if (clamped < 50) return 196;
            return Math.round(196 + ((clamped - 50) / 50) * 104);
    }
}

export function isPassing(step: USMLEStep, score: number): boolean {
    if (step === "step1") return score >= 196; // current pass threshold
    if (step === "step2_ck") return score >= 218;
    return score >= 200;
}
