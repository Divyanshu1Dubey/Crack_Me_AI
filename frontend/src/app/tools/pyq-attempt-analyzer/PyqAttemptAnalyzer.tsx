'use client';

import { useState } from 'react';
import { analyzePyqAttempts, MASTERED_THRESHOLD, NEEDS_WORK_THRESHOLD, type AttemptAnalysis } from './analyze';

export default function PyqAttemptAnalyzer() {
    const [attempts, setAttempts] = useState('');
    const [result, setResult] = useState<AttemptAnalysis | null>(null);

    const analyzeAttempts = () => {
        setResult(analyzePyqAttempts(attempts));
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">PYQ Attempt Analyzer</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                Analyze your previous year question performance. Enter topic-wise attempt data to get topic mastery percentages,
                identify improvement areas, and get recommendations for focused revision.
            </p>

            <div className="mt-6 space-y-5">
                <div>
                    <label htmlFor="pyq-attempts" className="block text-sm font-semibold mb-1">PYQ Attempts (one per line)</label>
                    <p id="pyq-attempts-format" className="text-xs text-muted-foreground mb-2">Format: Topic Name, Correct Count, Total Questions</p>
                    <textarea
                        id="pyq-attempts"
                        aria-describedby="pyq-attempts-format"
                        value={attempts}
                        onChange={(e) => setAttempts(e.target.value)}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm font-mono"
                        rows={8}
                        placeholder="Cardiology, 8, 10&#10;Neurology, 6, 8&#10;Surgery, 5, 7&#10;OBG, 9, 10"
                    />
                </div>

                <button onClick={analyzeAttempts} className="w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                    Analyze Performance
                </button>

                {result && (
                    <div className="mt-6 space-y-4" aria-live="polite">
                        <div className="rounded-xl border border-border bg-muted/50 p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Overall Accuracy</p>
                            <p className="text-4xl font-black text-foreground mt-1">{result.accuracy}%</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                {result.totalCorrect} correct out of {result.totalQuestions} questions
                                {result.skippedLines > 0 && ` · ${result.skippedLines} line${result.skippedLines === 1 ? '' : 's'} skipped (use "Topic, correct, total")`}
                            </p>
                        </div>

                        {result.mastered.length > 0 && (
                            <div className="rounded-xl border border-green-500/40 bg-green-50 dark:bg-green-950/30 p-5">
                                <p className="text-sm font-bold text-green-700 dark:text-green-400 mb-2">Mastered Topics (≥{MASTERED_THRESHOLD}%)</p>
                                <ul className="space-y-1">
                                    {result.mastered.map((t, i) => (
                                        <li key={i} className="text-sm text-green-700 dark:text-green-300">✓ {t}</li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {result.needsWork.length > 0 && (
                            <div className="rounded-xl border border-red-500/40 bg-red-50 dark:bg-red-950/30 p-5">
                                <p className="text-sm font-bold text-red-700 dark:text-red-400 mb-2">Needs Improvement (&lt;{NEEDS_WORK_THRESHOLD}%)</p>
                                <ul className="space-y-1">
                                    {result.needsWork.map((t, i) => (
                                        <li key={i} className="text-sm text-red-700 dark:text-red-300">✗ {t}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
