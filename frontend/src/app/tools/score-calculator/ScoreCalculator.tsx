'use client';

import { useState, useMemo } from 'react';

export default function ScoreCalculator() {
    const [correct, setCorrect] = useState('0');
    const [incorrect, setIncorrect] = useState('0');
    const [unattempted, setUnattempted] = useState('0');
    const [totalQuestions, setTotalQuestions] = useState('120');
    const [showBreakdown, setShowBreakdown] = useState(false);

    const correctNum = Number(correct) || 0;
    const incorrectNum = Number(incorrect) || 0;
    const unattemptedNum = Number(unattempted) || 0;
    const totalNum = Number(totalQuestions) || 0;

    const answeredNum = correctNum + incorrectNum;
    const expectedUnattempted = Math.max(0, totalNum - answeredNum);

    const rawScore = useMemo(() => (correctNum * 3) + (incorrectNum * -1), [correctNum, incorrectNum]);
    const maxScore = totalNum * 3;
    const percentage = maxScore > 0 ? ((rawScore / maxScore) * 100).toFixed(2) : '0.00';
    const attemptedCount = answeredNum;
    const accuracy = attemptedCount > 0 ? ((correctNum / attemptedCount) * 100).toFixed(2) : '0.00';

    const getPerformanceLabel = () => {
        const pct = parseFloat(percentage);
        if (pct >= 70) return { label: 'Excellent', color: 'text-green-600' };
        if (pct >= 55) return { label: 'Good', color: 'text-blue-600' };
        if (pct >= 40) return { label: 'Average', color: 'text-yellow-600' };
        if (pct >= 25) return { label: 'Below Average', color: 'text-orange-600' };
        return { label: 'Needs Improvement', color: 'text-red-600' };
    };

    const performance = getPerformanceLabel();

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS Score Calculator 2026</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                Estimate your UPSC CMS 2026 score using the official +3 / -1 marking scheme.
                Enter your attempted answers to see your projected score and performance level.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label className="block text-sm font-semibold mb-1">Total Questions</label>
                    <input
                        type="number"
                        value={totalQuestions}
                        onChange={(e) => setTotalQuestions(e.target.value)}
                        min="1"
                        max="200"
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Correct Answers</label>
                    <input
                        type="number"
                        value={correct}
                        onChange={(e) => setCorrect(e.target.value)}
                        min="0"
                        max={totalQuestions}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Incorrect Answers</label>
                    <input
                        type="number"
                        value={incorrect}
                        onChange={(e) => setIncorrect(e.target.value)}
                        min="0"
                        max={totalQuestions}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Unattempted Questions</label>
                    <input
                        type="number"
                        value={unattempted}
                        onChange={(e) => setUnattempted(e.target.value)}
                        min="0"
                        max={totalQuestions}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                    {unattemptedNum !== expectedUnattempted && (
                        <p className="mt-1 text-xs text-muted-foreground">
                            Expected unattempted: {expectedUnattempted} (based on total - correct - incorrect)
                        </p>
                    )}
                </div>
            </div>

            <button
                onClick={() => setShowBreakdown(!showBreakdown)}
                className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90"
            >
                {showBreakdown ? 'Hide' : 'Calculate'} Score Breakdown
            </button>

            {showBreakdown && (
                <div className="mt-6 rounded-xl border border-border bg-muted/50 p-6">
                    <div className="grid gap-4 sm:grid-cols-3">
                        <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Raw Score</p>
                            <p className="text-3xl font-black text-foreground">{rawScore}</p>
                        </div>
                        <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Percentage</p>
                            <p className="text-3xl font-black text-foreground">{percentage}%</p>
                        </div>
                        <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Performance</p>
                            <p className={`text-2xl font-black ${performance.color}`}>{performance.label}</p>
                        </div>
                    </div>

                    <div className="mt-6 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-lg bg-background p-4">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Correct ({correctNum})</p>
                            <p className="text-lg font-bold text-green-600">+{correctNum * 3} points</p>
                        </div>
                        <div className="rounded-lg bg-background p-4">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Incorrect ({incorrectNum})</p>
                            <p className="text-lg font-bold text-red-600">{incorrectNum * -1} points</p>
                        </div>
                        <div className="rounded-lg bg-background p-4">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Unattempted ({unattemptedNum})</p>
                            <p className="text-lg font-bold text-muted-foreground">0 points</p>
                        </div>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-lg bg-background p-4">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Attempted</p>
                            <p className="text-lg font-bold">{attemptedCount} / {totalNum}</p>
                        </div>
                        <div className="rounded-lg bg-background p-4">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Accuracy</p>
                            <p className="text-lg font-bold">{accuracy}%</p>
                        </div>
                    </div>

                    <p className="mt-4 text-xs text-muted-foreground">
                        * This is an indicative score based on self-reported answers. Final results are published by UPSC.
                    </p>
                </div>
            )}
        </div>
    );
}
