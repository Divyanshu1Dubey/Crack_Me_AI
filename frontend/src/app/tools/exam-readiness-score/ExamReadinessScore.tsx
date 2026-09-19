'use client';

import { useState } from 'react';

type SubjectProgress = {
    subject: string;
    completed: number;
};

const SUBJECTS = [
    'Medicine',
    'Surgery',
    'OBG',
    'Pediatrics',
    'PSM',
    'Pathology',
    'Pharmacology',
    'Microbiology',
    'Anatomy',
    'Physiology',
    'Biochemistry',
    'ENT',
    'Ophthalmology',
    'FM',
    'SPM',
];

export default function ExamReadinessScore() {
    const [daysRemaining, setDaysRemaining] = useState(90);
    const [hoursPerDay, setHoursPerDay] = useState(6);
    const [mocksTaken, setMocksTaken] = useState(0);
    const [revisionCycles, setRevisionCycles] = useState(0);
    const [subjects, setSubjects] = useState<SubjectProgress[]>(
        SUBJECTS.map((s) => ({ subject: s, completed: 0 }))
    );
    const [result, setResult] = useState<{ score: number; tier: string; advice: string[] } | null>(null);

    const handleSubjectChange = (index: number, value: number) => {
        setSubjects((prev) => {
            const next = [...prev];
            next[index] = { ...next[index], completed: Math.max(0, Math.min(100, value)) };
            return next;
        });
    };

    const computeScore = () => {
        const avgCompletion =
            subjects.reduce((sum, s) => sum + s.completed, 0) / subjects.length;
        const mockScore = Math.min(mocksTaken / 20, 1) * 25;
        const revisionScore = Math.min(revisionCycles / 3, 1) * 20;
        const hoursScore = Math.min(hoursPerDay / 8, 1) * 15;
        const urgencyPenalty = daysRemaining < 30 ? 10 : daysRemaining < 60 ? 5 : 0;

        const rawScore = avgCompletion * 0.4 + mockScore + revisionScore + hoursScore;
        const score = Math.max(0, Math.min(100, Math.round(rawScore - urgencyPenalty)));

        let tier: string;
        let advice: string[];
        if (score >= 80) {
            tier = 'Exam Ready';
            advice = [
                'Your preparation is strong. Focus on high-yield revision and timed mocks.',
                'Identify weak areas from mock performance and revise them in the final week.',
                'Maintain sleep and routine — avoid last-minute cramming.',
            ];
        } else if (score >= 60) {
            tier = 'Intermediate';
            advice = [
                'You have a solid base. Prioritise incomplete subjects and take at least 5 more mocks.',
                'Start your first revision cycle if you haven\'t already — spaced repetition boosts retention.',
                'Increase daily study hours if possible and cut distractions.',
            ];
        } else if (score >= 35) {
            tier = 'Beginner';
            advice = [
                'Focus on completing the core syllabus before attempting too many mocks.',
                'Aim for at least one full revision before the exam date.',
                'Create a day-wise plan and stick to a consistent schedule.',
            ];
        } else {
            tier = 'Needs Serious Work';
            advice = [
                'Assess how many days you realistically have and prioritise high-weightage topics.',
                'Consider reducing syllabus breadth and increasing depth in core subjects.',
                'Seek guidance from a mentor or structured course to accelerate progress.',
            ];
        }

        setResult({ score, tier, advice });
    };

    const getScoreColor = (score: number) => {
        if (score >= 80) return 'text-green-600 dark:text-green-400';
        if (score >= 60) return 'text-amber-600 dark:text-amber-400';
        if (score >= 35) return 'text-orange-600 dark:text-orange-400';
        return 'text-red-600 dark:text-red-400';
    };

    const getTierBg = (tier: string) => {
        if (tier === 'Exam Ready') return 'bg-green-50 dark:bg-green-950/30 border-green-500/40';
        if (tier === 'Intermediate') return 'bg-amber-50 dark:bg-amber-950/30 border-amber-500/40';
        if (tier === 'Beginner') return 'bg-orange-50 dark:bg-orange-950/30 border-orange-500/40';
        return 'bg-red-50 dark:bg-red-950/30 border-red-500/40';
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS Exam Readiness Score</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                Fill in your preparation details to get a personalised readiness score and actionable advice.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label className="block text-sm font-semibold mb-1">Days Remaining Until Exam</label>
                    <input
                        type="number"
                        min={1}
                        value={daysRemaining}
                        onChange={(e) => setDaysRemaining(Number(e.target.value))}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Study Hours Per Day</label>
                    <input
                        type="number"
                        min={0}
                        max={16}
                        value={hoursPerDay}
                        onChange={(e) => setHoursPerDay(Number(e.target.value))}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Mock Tests Completed</label>
                    <input
                        type="number"
                        min={0}
                        max={100}
                        value={mocksTaken}
                        onChange={(e) => setMocksTaken(Number(e.target.value))}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Revision Cycles Completed</label>
                    <input
                        type="number"
                        min={0}
                        max={10}
                        value={revisionCycles}
                        onChange={(e) => setRevisionCycles(Number(e.target.value))}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                    />
                </div>
            </div>

            <div className="mt-6">
                <label className="block text-sm font-semibold mb-2">Subject Completion (%)</label>
                <div className="grid gap-3 sm:grid-cols-2">
                    {subjects.map((s, i) => (
                        <div key={s.subject} className="flex items-center gap-3">
                            <span className="w-28 text-xs font-medium text-muted-foreground truncate">{s.subject}</span>
                            <input
                                type="range"
                                min={0}
                                max={100}
                                value={s.completed}
                                onChange={(e) => handleSubjectChange(i, Number(e.target.value))}
                                className="flex-1"
                            />
                            <span className="w-9 text-right text-xs font-bold">{s.completed}%</span>
                        </div>
                    ))}
                </div>
            </div>

            <button
                onClick={computeScore}
                className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90"
            >
                Calculate Readiness Score
            </button>

            {result && (
                <div className={`mt-6 rounded-xl border p-5 ${getTierBg(result.tier)}`}>
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div>
                            <p className={`text-3xl font-black ${getScoreColor(result.score)}`}>
                                {result.score}/100
                            </p>
                            <p className="text-sm font-semibold text-foreground mt-1">{result.tier}</p>
                        </div>
                        <div className="w-full sm:w-32 h-3 rounded-full bg-muted overflow-hidden">
                            <div
                                className="h-full rounded-full bg-primary transition-all"
                                style={{ width: `${result.score}%` }}
                            />
                        </div>
                    </div>
                    <ul className="mt-4 space-y-2 text-sm">
                        {result.advice.map((a, i) => (
                            <li key={i} className="flex gap-2">
                                <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                                <span className="text-foreground">{a}</span>
                            </li>
                        ))}
                    </ul>
                    <p className="mt-3 text-xs text-muted-foreground">
                        This score is indicative only. Use it to prioritise subjects and track improvement over time.
                    </p>
                </div>
            )}
        </div>
    );
}
