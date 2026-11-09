/**
 * "Dropped by UPSC": the question stays in the bank, but UPSC dropped it from evaluation, so it is not scored
 * (the backend leaves it out of test scores: tests_engine.scoring). The answer the bank shows with it is the
 * bank's own, not an official UPSC key.
 */
export const DROPPED_BY_UPSC_NOTE =
    'UPSC dropped this question from evaluation, so it is not scored. The answer shown is the question bank\'s, not an official UPSC key.';

export default function DroppedByUpscBadge({ className = '' }: { className?: string }) {
    return (
        <span
            className={`inline-flex items-center rounded-full border border-slate-400/40 bg-slate-500/10 px-2 py-0.5 text-[11px] font-semibold text-slate-700 dark:text-slate-200 ${className}`}
            title={DROPPED_BY_UPSC_NOTE}
        >
            Dropped by UPSC
            <span className="sr-only">: {DROPPED_BY_UPSC_NOTE}</span>
        </span>
    );
}
