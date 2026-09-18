'use client';

import { useState } from 'react';

interface PlanDay {
    day: number;
    focus: string;
    tasks: string[];
    hours: number;
}

export default function StudyPlanBuilder() {
    const [exam, setExam] = useState('neet-pg');
    const [examDate, setExamDate] = useState('');
    const [dailyHours, setDailyHours] = useState('6');
    const [weakSubjects, setWeakSubjects] = useState<string[]>([]);
    const [plan, setPlan] = useState<PlanDay[] | null>(null);

    const allSubjects: Record<string, string[]> = {
        'neet-pg': ['Anatomy', 'Physiology', 'Biochemistry', 'Pathology', 'Pharmacology', 'Microbiology', 'Forensic Medicine', 'PSM', 'Medicine', 'Surgery', 'OBG', 'Paediatrics', 'Orthopaedics', 'ENT', 'Ophthalmology', 'Psychiatry', 'Dermatology', 'Anaesthesia', 'Radiology'],
        'cms': ['General Medicine', 'General Surgery', 'Paediatrics', 'OBG', 'PSM', 'ENT', 'Ophthalmology', 'Orthopaedics', 'Anaesthesia', 'Radiology'],
        'ini-cet': ['Anatomy', 'Physiology', 'Biochemistry', 'Pathology', 'Pharmacology', 'Microbiology', 'Forensic Medicine', 'PSM', 'Medicine', 'Surgery', 'OBG', 'Paediatrics', 'Orthopaedics', 'ENT', 'Ophthalmology', 'Psychiatry', 'Dermatology', 'Anaesthesia', 'Radiology'],
    };

    const examLabels: Record<string, string> = { 'neet-pg': 'NEET PG', 'cms': 'UPSC CMS', 'ini-cet': 'INI-CET' };

    const toggleSubject = (s: string) => {
        setWeakSubjects((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
    };

    const generatePlan = () => {
        if (!examDate) return;
        const subjects = allSubjects[exam] || allSubjects['neet-pg'];
        const hrs = Number(dailyHours);
        const daysUntil = Math.max(1, Math.ceil((new Date(examDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)));
        const totalDays = Math.min(daysUntil, 180);
        const generated: PlanDay[] = [];

        // Phase 1: Foundation (first 40% of days) — cover all subjects once
        const phase1Days = Math.floor(totalDays * 0.4);
        const subjectsPerDay = Math.max(1, Math.ceil(subjects.length / phase1Days));
        for (let i = 0; i < phase1Days && generated.length < totalDays; i++) {
            const daySubjects = subjects.slice(i * subjectsPerDay, (i + 1) * subjectsPerDay);
            const isWeak = daySubjects.some((s) => weakSubjects.includes(s));
            generated.push({
                day: i + 1,
                focus: isWeak ? `Foundation + extra practice on weak topics` : `Foundation: ${daySubjects.join(', ')}`,
                tasks: [
                    ...daySubjects.flatMap((s) => [`Read core concepts: ${s}`, `Solve 30 ${s} MCQs`]),
                    weakSubjects.filter((s) => daySubjects.includes(s)).map((s) => `Extra: 15 additional ${s} MCQs (weak subject)`),
                    `Review previous day's mistakes`,
                ].flat(),
                hours: hrs,
            });
        }

        // Phase 2: Practice (next 35% of days) — mocks + revision
        const phase2Start = phase1Days;
        const phase2Days = Math.floor(totalDays * 0.35);
        for (let i = 0; i < phase2Days && generated.length < totalDays; i++) {
            const dayNum = phase2Start + i + 1;
            const isMockDay = i % 7 === 0;
            generated.push({
                day: dayNum,
                focus: isMockDay ? 'Full mock test + analysis' : `Practice + revision`,
                tasks: isMockDay
                    ? [`Take full ${examLabels[exam]} mock (timed)`, `Analyse all incorrect answers`, `Update weak subject list`]
                    : [
                          `Solve 80 MCQs from QBank`,
                          `Revise 2 weak subjects`,
                          `Review flashcards / mnemonics`,
                          `Read high-yield notes for ${weakSubjects.length > 0 ? weakSubjects.slice(0, 2).join(', ') : 'all subjects'}`,
                      ],
                hours: hrs,
            });
        }

        // Phase 3: Sprint (last 25% of days) — only mocks + rapid revision
        const phase3Start = phase2Start + phase2Days;
        for (let i = 0; generated.length < totalDays; i++) {
            const dayNum = phase3Start + i + 1;
            generated.push({
                day: dayNum,
                focus: 'Final sprint — mocks + rapid revision',
                tasks: [
                    `Take ${i % 2 === 0 ? 'full mock test' : 'subject-wise rapid revision'}`,
                    `Review all mock mistakes`,
                    `Quick revision of weak subjects`,
                    `Sleep well — no last-minute cramming night before exam`,
                ],
                hours: Math.max(hrs - 1, 4),
            });
        }

        setPlan(generated.slice(0, totalDays));
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">Personalised Study Plan Builder</h3>
            <p className="mt-2 text-sm text-muted-foreground">Enter your details below to generate a custom study plan for your target exam.</p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <div>
                    <label className="block text-sm font-semibold mb-1">Target Exam</label>
                    <select value={exam} onChange={(e) => { setExam(e.target.value); setWeakSubjects([]); }} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
                        <option value="neet-pg">NEET PG</option>
                        <option value="cms">UPSC CMS</option>
                        <option value="ini-cet">INI-CET</option>
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Exam Date</label>
                    <input type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                </div>
                <div>
                    <label className="block text-sm font-semibold mb-1">Daily Study Hours</label>
                    <input type="number" value={dailyHours} onChange={(e) => setDailyHours(e.target.value)} min="1" max="16" className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm" />
                </div>
            </div>

            <div className="mt-5">
                <label className="block text-sm font-semibold mb-2">Weak Subjects (select all that apply)</label>
                <div className="flex flex-wrap gap-2">
                    {(allSubjects[exam] || allSubjects['neet-pg']).map((s) => (
                        <button key={s} onClick={() => toggleSubject(s)} className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${weakSubjects.includes(s) ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:border-primary/40'}`}>
                            {s}
                        </button>
                    ))}
                </div>
            </div>

            <button onClick={generatePlan} className="mt-6 w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                Generate Study Plan
            </button>

            {plan && (
                <div className="mt-8 max-h-[600px] overflow-y-auto rounded-xl border border-border">
                    <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-muted">
                            <tr>
                                <th className="border border-border px-3 py-2 text-left font-bold">Day</th>
                                <th className="border border-border px-3 py-2 text-left font-bold">Focus</th>
                                <th className="border border-border px-3 py-2 text-left font-bold">Tasks</th>
                                <th className="border border-border px-3 py-2 text-left font-bold">Hours</th>
                            </tr>
                        </thead>
                        <tbody>
                            {plan.map((d) => (
                                <tr key={d.day} className="hover:bg-muted/30">
                                    <td className="border border-border px-3 py-2 font-mono">{d.day}</td>
                                    <td className="border border-border px-3 py-2">{d.focus}</td>
                                    <td className="border border-border px-3 py-2">{d.tasks.join(' · ')}</td>
                                    <td className="border border-border px-3 py-2">{d.hours}h</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {plan && (
                <p className="mt-3 text-xs text-muted-foreground">Plan covers {plan.length} days. Adjust daily hours or exam date to regenerate. This is a starting template — adapt based on your mock performance.</p>
            )}
        </div>
    );
}
