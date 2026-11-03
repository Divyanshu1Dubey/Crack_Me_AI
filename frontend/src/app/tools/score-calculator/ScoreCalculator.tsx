'use client';

import { useState } from 'react';
import {
    CMS_MARKING_LABEL,
    CMS_MARKS_PER_QUESTION,
    CMS_PENALTY_PER_WRONG,
    UPSC_CMS_PATTERN,
    cmsMaxMarks,
    round2,
    scoreCmsAttempt,
} from '@/lib/examPatterns';

export default function ScoreCalculator() {
    const [correct, setCorrect] = useState('0');
    const [incorrect, setIncorrect] = useState('0');
    const [unattempted, setUnattempted] = useState('0');
    const [totalQuestions, setTotalQuestions] = useState(String(UPSC_CMS_PATTERN.papers[0].questions));
    const [showBreakdown, setShowBreakdown] = useState(false);

    const correctNum = Number(correct) || 0;
    const incorrectNum = Number(incorrect) || 0;
    const unattemptedNum = Number(unattempted) || 0;
    const totalNum = Number(totalQuestions) || 0;

    const answeredNum = correctNum + incorrectNum;
    const expectedUnattempted = Math.max(0, totalNum - answeredNum);

    // Official UPSC CMS marking (lib/examPatterns): 250 marks / 120 questions
    // per paper, one-third of a question's marks deducted per wrong answer.
    const breakdown = scoreCmsAttempt({ correct: correctNum, incorrect: incorrectNum });
    const rawScore = breakdown.score;
    const maxScore = cmsMaxMarks(totalNum);
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
                Estimate your UPSC CMS score using the official marking: {CMS_MARKING_LABEL} per question
                ({UPSC_CMS_PATTERN.papers[0].marks} marks for {UPSC_CMS_PATTERN.papers[0].questions} questions per paper,
                one-third negative marking). Enter your attempted answers to see your projected score and performance level.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label htmlFor="score-total" className="block text-sm font-semibold mb-1">Total Questions</label>
                    <input
                        id="score-total"
                        type="number"
                        value={totalQuestions}
                        onChange={(e) => setTotalQuestions(e.target.value)}
                        min="1"
                        max={UPSC_CMS_PATTERN.totalQuestions}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                        {UPSC_CMS_PATTERN.papers[0].questions} for one paper, {UPSC_CMS_PATTERN.totalQuestions} for both.
                    </p>
                </div>
                <div>
                    <label htmlFor="score-correct" className="block text-sm font-semibold mb-1">Correct Answers</label>
                    <input
                        id="score-correct"
                        type="number"
                        value={correct}
                        onChange={(e) => setCorrect(e.target.value)}
                        min="0"
                        max={totalQuestions}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label htmlFor="score-incorrect" className="block text-sm font-semibold mb-1">Incorrect Answers</label>
                    <input
                        id="score-incorrect"
                        type="number"
                        value={incorrect}
                        onChange={(e) => setIncorrect(e.target.value)}
                        min="0"
                        max={totalQuestions}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label htmlFor="score-unattempted" className="block text-sm font-semibold mb-1">Unattempted Questions</label>
                    <input
                        id="score-unattempted"
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
                <div className="mt-6 rounded-xl border border-border bg-muted/50 p-6" aria-live="polite">
                    <div className="grid gap-4 sm:grid-cols-3">
                        <div>
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Raw Score</p>
                            <p className="text-3xl font-black text-foreground">{rawScore.toFixed(2)}</p>
                            <p className="text-xs text-muted-foreground">out of {maxScore.toFixed(2)}</p>
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
                            <p className="text-lg font-bold text-green-600">+{breakdown.correctMarks.toFixed(2)} marks</p>
                            <p className="text-xs text-muted-foreground">+{round2(CMS_MARKS_PER_QUESTION).toFixed(2)} each</p>
                        </div>
                        <div className="rounded-lg bg-background p-4">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Incorrect ({incorrectNum})</p>
                            <p className="text-lg font-bold text-red-600">−{breakdown.penalty.toFixed(2)} marks</p>
                            <p className="text-xs text-muted-foreground">−{round2(CMS_PENALTY_PER_WRONG).toFixed(2)} each</p>
                        </div>
                        <div className="rounded-lg bg-background p-4">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Unattempted ({unattemptedNum})</p>
                            <p className="text-lg font-bold text-muted-foreground">0 marks</p>
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
