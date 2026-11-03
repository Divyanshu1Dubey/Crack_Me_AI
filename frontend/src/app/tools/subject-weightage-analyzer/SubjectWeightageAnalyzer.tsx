'use client';

/**
 * Subject Weightage Analyzer — shows how the UPSC CMS paper is weighted by
 * subject (official question split) and lets the student compare it with
 * the time they plan to spend. When the PYQ bank stats endpoint answers, the
 * number of practice questions available per subject is shown as well.
 *
 * (This file used to be a copy of the PYQ Attempt Analyzer.)
 */

import { useEffect, useMemo, useState } from 'react';
import { questionsAPI } from '@/lib/api';
import { bankCountsByCmsSubject, officialCmsWeightage } from './weightage';

export default function SubjectWeightageAnalyzer() {
    const rows = useMemo(() => officialCmsWeightage(), []);
    const [hours, setHours] = useState('20');
    const [bankCounts, setBankCounts] = useState<Record<string, number> | null>(null);

    useEffect(() => {
        let cancelled = false;
        questionsAPI
            .getStats({ exam_type: 'cms' })
            .then((res) => {
                if (!cancelled) setBankCounts(bankCountsByCmsSubject(res.data?.by_subject));
            })
            .catch(() => {
                /* optional enrichment — the official split still renders */
            });
        return () => {
            cancelled = true;
        };
    }, []);

    const weeklyHours = Math.max(0, Number(hours) || 0);

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">UPSC CMS Subject Weightage Analyzer</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                How the {rows.reduce((a, r) => a + r.questions, 0)} UPSC CMS questions are split by subject, and how many
                study hours each subject earns if you split your week by weightage.
            </p>

            <div className="mt-6 max-w-xs">
                <label htmlFor="weightage-hours" className="block text-sm font-semibold mb-1">Study hours per week</label>
                <input
                    id="weightage-hours"
                    type="number"
                    min="0"
                    max="120"
                    value={hours}
                    onChange={(e) => setHours(e.target.value)}
                    className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm"
                />
            </div>

            <div className="mt-6 overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
                            <th className="py-2 pr-3 font-semibold">Subject</th>
                            <th className="py-2 pr-3 font-semibold">Paper</th>
                            <th className="py-2 pr-3 font-semibold">Questions</th>
                            <th className="py-2 pr-3 font-semibold">Weightage</th>
                            <th className="py-2 pr-3 font-semibold">Hours / week</th>
                            {bankCounts && <th className="py-2 font-semibold">PYQs in our bank</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((r) => (
                            <tr key={r.subject} className="border-b border-border/60 align-top">
                                <td className="py-3 pr-3">
                                    <span className="font-semibold text-foreground">{r.subject}</span>
                                    {r.includes && <span className="block text-xs text-muted-foreground">incl. {r.includes}</span>}
                                    <div className="mt-2 h-2 rounded-full bg-muted" aria-hidden="true">
                                        <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(100, r.sharePct)}%` }} />
                                    </div>
                                </td>
                                <td className="py-3 pr-3 text-muted-foreground">{r.paper}</td>
                                <td className="py-3 pr-3 font-semibold">{r.questions}</td>
                                <td className="py-3 pr-3 font-semibold">{r.sharePct}%</td>
                                <td className="py-3 pr-3">{(weeklyHours * r.sharePct / 100).toFixed(1)}</td>
                                {bankCounts && <td className="py-3">{(bankCounts[r.subject] ?? 0).toLocaleString('en-IN')}</td>}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <p className="mt-4 text-xs text-muted-foreground">
                * Question split as given in the UPSC CMS notice (marks ≈ {rows[0]?.marks ? (rows[0].marks / rows[0].questions).toFixed(2) : '2.08'} per
                question). Topic-level weightage within a subject varies from year to year; check the PYQ bank for recent papers.
            </p>
        </div>
    );
}
