'use client';

import { useState } from 'react';

interface EstimateResult {
    totalMonths: number;
    dailyHoursNeeded: number;
    phaseBreakdown: {
        foundation: { months: number; hoursPerDay: number };
        practice: { months: number; hoursPerDay: number };
        sprint: { months: number; hoursPerDay: number };
    };
    tips: string[];
    rankReachable: string;
}

export default function PreparationTimeEstimator() {
    const [currentLevel, setCurrentLevel] = useState('beginner');
    const [targetRank, setTargetRank] = useState('top-1000');
    const [dailyHours, setDailyHours] = useState('5');
    const [weakSubjects, setWeakSubjects] = useState<string[]>([]);
    const [previousAttempts, setPreviousAttempts] = useState('0');
    const [result, setResult] = useState<EstimateResult | null>(null);
    const [showResult, setShowResult] = useState(false);

    const cmsSubjects = [
        'General Medicine', 'General Surgery', 'Paediatrics', 'OBG', 'PSM',
        'ENT', 'Ophthalmology', 'Orthopaedics', 'Anaesthesia', 'Radiology',
        'Psychiatry', 'Dermatology', 'TB & Chest', 'Emergency Medicine'
    ];

    const toggleSubject = (s: string) => {
        setWeakSubjects(prev => (prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]));
    };

    const estimatePreparationTime = () => {
        const hrs = Number(dailyHours) || 5;
        const attempts = Number(previousAttempts) || 0;

        const baseMatrix: Record<string, Record<string, number>> = {
            'beginner': { 'top-100': 10, 'top-500': 8, 'top-1000': 7, 'top-2000': 5.5, 'qualified': 4 },
            'intermediate': { 'top-100': 7, 'top-500': 5, 'top-1000': 4, 'top-2000': 3, 'qualified': 2 },
            'advanced': { 'top-100': 4.5, 'top-500': 3.5, 'top-1000': 3, 'top-2000': 2, 'qualified': 1.5 },
        };

        let totalMonths = baseMatrix[currentLevel]?.[targetRank] || 6;

        const weakCount = Math.min(weakSubjects.length, 3);
        totalMonths += weakCount * 0.4;

        if (attempts > 0) {
            totalMonths *= Math.max(0.55, 1 - attempts * 0.15);
        }

        totalMonths = Math.round(totalMonths * 2) / 2;
        totalMonths = Math.max(1.5, totalMonths);

        const foundationMonths = Math.round(totalMonths * 0.40 * 2) / 2;
        const practiceMonths = Math.round(totalMonths * 0.35 * 2) / 2;
        const sprintMonths = Math.round(totalMonths - foundationMonths - practiceMonths);

        const foundHours = hrs;
        const pracHours = Math.min(hrs, 8);
        const sprintHours = Math.max(Math.min(hrs, 7), 4);

        const rankLabels: Record<string, string> = {
            'top-100': 'Top 100 rank (highly competitive)',
            'top-500': 'Top 500 rank (competitive)',
            'top-1000': 'Top 1000 rank (moderately competitive)',
            'top-2000': 'Top 2000 rank (comfortable zone)',
            'qualified': 'Simply qualify (realistic for most)'
        };

        const tips: string[] = [];
        if (currentLevel === 'beginner') {
            tips.push('Start with high-yield textbooks (e.g., Harper for Pathology, Essentials of Medical Pharmacology) before diving into PYQs.');
        }
        if (hrs < 5) {
            tips.push('With fewer than 5 hours/day, maximise weekends — use Saturday/Sunday for full-length mock tests and deep-dive topics.');
        }
        if (weakSubjects.length > 0) {
            tips.push(`Prioritise ${weakSubjects.join(' and ')} early. Dedicate an extra 30 minutes daily to these until you consistently score >75% on their QBank.`);
        }
        if (sprintMonths >= 3) {
            tips.push('With a long prep timeline, maintain discipline. Set weekly milestones and use spaced-repetition flashcards daily.');
        }
        tips.push('Take at least one full mock every weekend starting from the practice phase. Analyse every mistake.');
        if (attempts === 0) {
            tips.push('Your first attempt is learning — expect to score lower on mocks than your final target. Trust the process.');
        }

        setResult({
            totalMonths,
            dailyHoursNeeded: hrs,
            phaseBreakdown: {
                foundation: { months: foundationMonths, hoursPerDay: foundHours },
                practice: { months: practiceMonths, hoursPerDay: pracHours },
                sprint: { months: sprintMonths, hoursPerDay: sprintHours },
            },
            tips,
            rankReachable: rankLabels[targetRank] || targetRank,
        });
        setShowResult(true);
    };

    const levelLabels: Record<string, string> = {
        'beginner': 'Beginner — starting from scratch or very little PYQ exposure',
        'intermediate': 'Intermediate — familiar with most subjects, done some PYQs',
        'advanced': 'Advanced — done thorough PYQ practice, know weak areas'
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS Preparation Time Estimator</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                Estimate how many months you need to prepare for UPSC CMS based on your current level, target rank, daily study hours, and subjects. This is a data-driven estimate — adapt as you progress.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label className="block text-sm font-semibold mb-1">Current Preparation Level</label>
                    <select value={currentLevel} onChange={(e) => setCurrentLevel(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="beginner">Beginner</option>
                        <option value="intermediate">Intermediate</option>
                        <option value="advanced">Advanced</option>
                    </select>
                    <p className="mt-1 text-xs text-muted-foreground">{levelLabels[currentLevel]}</p>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Target Rank</label>
                    <select value={targetRank} onChange={(e) => setTargetRank(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="top-100">Top 100 (highly competitive)</option>
                        <option value="top-500">Top 500 (competitive)</option>
                        <option value="top-1000">Top 1000 (moderately competitive)</option>
                        <option value="top-2000">Top 2000 (comfortable zone)</option>
                        <option value="qualified">Simply qualify</option>
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Daily Study Hours</label>
                    <input type="number" value={dailyHours} onChange={(e) => setDailyHours(e.target.value)} min="1" max="16" className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Previous UPSC CMS Attempts</label>
                    <input type="number" value={previousAttempts} onChange={(e) => setPreviousAttempts(e.target.value)} min="0" max="5" className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                    <p className="mt-1 text-xs text-muted-foreground">Each attempt reduces prep time by ~15%.</p>
                </div>
            </div>

            <div className="mt-5">
                <label className="block text-sm font-semibold mb-2">Weak Subjects (select all that apply)</label>
                <div className="flex flex-wrap gap-2">
                    {cmsSubjects.map(s => (
                        <button key={s} onClick={() => toggleSubject(s)} className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${weakSubjects.includes(s) ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:border-primary/40'}`}>
                            {s}
                        </button>
                    ))}
                </div>
            </div>

            <button onClick={estimatePreparationTime} className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                Estimate Preparation Time
            </button>

            {showResult && result && (
                <div className="mt-8 space-y-6">
                    <div className="rounded-xl border border-border bg-muted/50 p-5 sm:p-6">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                            <div>
                                <p className="text-sm text-muted-foreground font-semibold uppercase tracking-wider">Estimated Prep Time</p>
                                <p className="text-4xl font-black text-foreground mt-1">{result.totalMonths} <span className="text-xl font-semibold text-muted-foreground">months</span></p>
                                <p className="text-xs text-muted-foreground mt-1">Goal: {result.rankReachable}</p>
                            </div>
                            <div className="text-left sm:text-right">
                                <p className="text-sm text-muted-foreground font-semibold uppercase tracking-wider">At</p>
                                <p className="text-2xl font-bold text-foreground">{result.dailyHoursNeeded} hrs<span className="text-sm font-semibold text-muted-foreground">/day</span></p>
                            </div>
                        </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-3">
                        {[
                            { label: 'Foundation', months: result.phaseBreakdown.foundation.months, hours: result.phaseBreakdown.foundation.hoursPerDay, color: 'border-blue-500/40 bg-blue-50 dark:bg-blue-950/20', textColor: 'text-blue-700 dark:text-blue-300' },
                            { label: 'Practice', months: result.phaseBreakdown.practice.months, hours: result.phaseBreakdown.practice.hoursPerDay, color: 'border-amber-500/40 bg-amber-50 dark:bg-amber-950/20', textColor: 'text-amber-700 dark:text-amber-300' },
                            { label: 'Sprint', months: result.phaseBreakdown.sprint.months, hours: result.phaseBreakdown.sprint.hoursPerDay, color: 'border-green-500/40 bg-green-50 dark:bg-green-950/20', textColor: 'text-green-700 dark:text-green-300' },
                        ].map(phase => (
                            <div key={phase.label} className={`rounded-xl border p-4 ${phase.color}`}>
                                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{phase.label}</p>
                                <p className={`text-2xl font-black mt-1 ${phase.textColor}`}>{phase.months} <span className="text-sm font-medium">months</span></p>
                                <p className={`text-xs mt-1 ${phase.textColor}`}>{phase.hours}h/day avg</p>
                            </div>
                        ))}
                    </div>

                    <div className="rounded-xl border border-border bg-background p-5">
                        <h4 className="text-sm font-bold mb-3">Personalised Tips</h4>
                        <ul className="space-y-2">
                            {result.tips.map((tip, i) => (
                                <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                                    <span className="text-primary font-bold shrink-0">&#x2022;</span>
                                    <span>{tip}</span>
                                </li>
                            ))}
                        </ul>
                    </div>

                    <p className="text-xs text-muted-foreground">
                        * This is an indicative estimate. Actual prep time depends on consistency, quality of study, and exam difficulty. Use it as a planning baseline, not a guarantee.
                    </p>
                </div>
            )}
        </div>
    );
}
