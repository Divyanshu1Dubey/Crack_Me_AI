/**
 * recallFacets — display helpers for the /recall/search facet chips.
 *
 * The recall_search endpoint returns facet keys as stored values
 * (`neet_pg`, `single_best`, year `0`, …). These helpers turn them into
 * readable labels and decide which chips to show. Framework-free so they
 * can be unit-tested in plain Node (tests/e2e/practice-data.spec.ts).
 */

/** Same labels as ExamSwitcher / Question.EXAM_CHOICES. */
const EXAM_LABELS: Record<string, string> = {
    cms: 'UPSC CMS',
    neet_pg: 'NEET PG',
    ini_cet: 'INI-CET',
    usmle: 'USMLE',
    fmge: 'FMGE',
};

/** Question.QUESTION_TYPE_CHOICES. */
const QUESTION_TYPE_LABELS: Record<string, string> = {
    single_best: 'Single best answer',
    multiple_correct: 'Multiple correct',
    assertion_reason: 'Assertion–reason',
    match: 'Match the following',
    image_based: 'Image-based',
    numerical: 'Numerical',
};

/** QuestionImage.MODALITY_CHOICES values whose plain humanised form reads wrong. */
const MODALITY_LABELS: Record<string, string> = {
    ct: 'CT',
    mri: 'MRI',
    ecg: 'ECG',
    x_ray: 'X-ray',
};

/** `clinical_system` → `Clinical system`. */
export function humaniseKey(value: string): string {
    const text = value.replace(/_/g, ' ').trim();
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

/** Readable chip text for one facet value. */
export function facetLabel(facet: string, value: string): string {
    if (facet === 'year') return value === '0' || value === '' ? 'Undated' : value;
    if (value === '') return 'Unspecified';
    if (facet === 'exam_type') return EXAM_LABELS[value] || humaniseKey(value);
    if (facet === 'question_type') return QUESTION_TYPE_LABELS[value] || humaniseKey(value);
    if (facet === 'modality') return MODALITY_LABELS[value] || humaniseKey(value);
    return humaniseKey(value);
}

/**
 * The chips to show for one facet group: years newest first (every year,
 * the undated bucket last), other groups by count (top `limit`). A group
 * with a single value offers nothing to drill into and is hidden — unless
 * that value is the active filter, so it can still be cleared.
 */
export function facetEntries(
    facet: string,
    counts: Record<string, number> | undefined,
    selected: string | undefined,
    limit = 8,
): Array<[string, number]> {
    const entries = Object.entries(counts || {});
    if (entries.length === 0) return [];
    if (entries.length === 1 && !(selected && entries[0][0] === selected)) return [];
    if (facet === 'year') {
        return entries.sort((a, b) => (Number(b[0]) || 0) - (Number(a[0]) || 0));
    }
    return entries.sort((a, b) => b[1] - a[1]).slice(0, limit);
}
