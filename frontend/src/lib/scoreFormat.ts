/**
 * A score or a mark total for display: at most two decimals ("0.34", "2", "1.67"), "–" when missing.
 * Test scores carry negative marking (-0.33 per wrong answer), so the raw float can read 0.33999999999999997.
 *
 * Keep this file free of imports (it is unit-tested directly with Node).
 */
export function formatMarks(value: unknown): string {
    if (value === null || value === undefined || value === '') return '–';
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return '–';
    const rounded = Math.round(n * 100) / 100;
    return String(Object.is(rounded, -0) ? 0 : rounded);
}
