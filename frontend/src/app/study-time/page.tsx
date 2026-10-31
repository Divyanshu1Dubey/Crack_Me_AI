'use client';
import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { studyTimeAPI } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, Award, Calendar, Clock, RotateCcw, TrendingUp } from 'lucide-react';

/** One row of `StudyTimeBreakdownSerializer`: a subject on one day. */
interface StudyRow {
    id: number;
    subject: number;
    subject_name: string;
    subject_color: string;
    seconds: number;
    question_count: number;
    date: string; // YYYY-MM-DD
}

type Range = '7' | '30' | 'all';
const RANGES: { key: Range; label: string }[] = [
    { key: '7', label: 'Last 7 days' },
    { key: '30', label: 'Last 30 days' },
    { key: 'all', label: 'All time' },
];

const FALLBACK_COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#ec4899'];

function formatDuration(seconds: number): string {
    const s = Math.max(0, Math.round(seconds));
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    if (hrs > 0) return `${hrs}h ${mins}m`;
    if (mins > 0) return `${mins}m`;
    return s > 0 ? `${s}s` : '0m';
}

/** Parse YYYY-MM-DD as a local date (new Date('2026-01-02') is UTC midnight). */
function localDate(iso: string): Date {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, (m || 1) - 1, d || 1);
}

function isoDaysAgo(days: number): string {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function StudyTimePage() {
    const router = useRouter();
    const { isAuthenticated, loading: authLoading } = useAuth();
    const [rows, setRows] = useState<StudyRow[]>([]);
    const [range, setRange] = useState<Range>('30');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (authLoading) return;
        if (!isAuthenticated) { router.push('/login'); return; }
        let alive = true;
        setLoading(true);
        setError(null);
        const params = range === 'all' ? undefined : { start: isoDaysAgo(Number(range) - 1) };
        studyTimeAPI.list(params).then(res => {
            if (!alive) return;
            const data = res.data;
            // API: { breakdown: [...], totals: [...] } (older builds returned a bare array).
            setRows((Array.isArray(data) ? data : data?.breakdown ?? []) as StudyRow[]);
        }).catch(() => {
            if (alive) setError('Could not load your study time. Check your connection and try again.');
        }).finally(() => {
            if (alive) setLoading(false);
        });
        return () => { alive = false; };
    }, [authLoading, isAuthenticated, range, reloadKey, router]);

    const summary = useMemo(() => {
        const totalSeconds = rows.reduce((sum, r) => sum + (r.seconds || 0), 0);
        const totalQuestions = rows.reduce((sum, r) => sum + (r.question_count || 0), 0);
        const byDay = new Map<string, { seconds: number; questions: number; subjects: StudyRow[] }>();
        const bySubject = new Map<number, { id: number; name: string; color: string; seconds: number; questions: number }>();
        for (const r of rows) {
            const day = byDay.get(r.date) ?? { seconds: 0, questions: 0, subjects: [] };
            day.seconds += r.seconds || 0;
            day.questions += r.question_count || 0;
            day.subjects.push(r);
            byDay.set(r.date, day);
            const subj = bySubject.get(r.subject) ?? { id: r.subject, name: r.subject_name || `Subject ${r.subject}`, color: r.subject_color, seconds: 0, questions: 0 };
            subj.seconds += r.seconds || 0;
            subj.questions += r.question_count || 0;
            bySubject.set(r.subject, subj);
        }
        const days = [...byDay.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
        const subjects = [...bySubject.values()].sort((a, b) => b.seconds - a.seconds || b.questions - a.questions);
        return { totalSeconds, totalQuestions, days, subjects };
    }, [rows]);

    const maxSubjectSeconds = Math.max(1, ...summary.subjects.map(s => s.seconds));
    const studyDays = summary.days.length;

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
            {/* Header */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                        <Clock className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold">Study Time</h1>
                        <p className="text-sm text-muted-foreground">Time spent on questions and tests, by subject</p>
                    </div>
                </div>
                <div className="flex gap-1.5" role="tablist" aria-label="Date range">
                    {RANGES.map(r => (
                        <Button
                            key={r.key}
                            role="tab"
                            aria-selected={range === r.key}
                            size="sm"
                            variant={range === r.key ? 'default' : 'outline'}
                            className="rounded-full"
                            onClick={() => setRange(r.key)}
                        >
                            {r.label}
                        </Button>
                    ))}
                </div>
            </div>

            {error && (
                <Card className="border-red-300 dark:border-red-800">
                    <CardContent className="p-4 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
                            <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
                        </div>
                        <Button size="sm" variant="outline" onClick={() => setReloadKey(k => k + 1)}>
                            <RotateCcw className="w-3 h-3 mr-1" /> Retry
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                    { icon: Clock, color: 'text-blue-500', label: 'Total study time', value: formatDuration(summary.totalSeconds) },
                    { icon: TrendingUp, color: 'text-green-500', label: 'Questions answered', value: String(summary.totalQuestions) },
                    { icon: Calendar, color: 'text-purple-500', label: 'Days studied', value: String(studyDays) },
                    { icon: Award, color: 'text-amber-500', label: 'Avg per study day', value: studyDays ? formatDuration(summary.totalSeconds / studyDays) : '0m' },
                ].map(card => (
                    <Card key={card.label}>
                        <CardContent className="p-4 text-center">
                            <card.icon className={`w-5 h-5 ${card.color} mx-auto mb-1`} />
                            {loading ? <Skeleton className="h-7 w-16 mx-auto" /> : <div className="text-xl font-bold tabular-nums">{card.value}</div>}
                            <div className="text-xs text-muted-foreground">{card.label}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {loading ? (
                <div className="space-y-3">
                    {[1, 2, 3].map(i => <Skeleton key={i} className="h-16" />)}
                </div>
            ) : rows.length === 0 && !error ? (
                <Card>
                    <CardContent className="p-8 text-center text-muted-foreground">
                        <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
                        <p className="mb-4">
                            {range === 'all'
                                ? 'No study time recorded yet. Time is tracked automatically as you answer questions and take tests.'
                                : 'No study time in this period. Try "All time" or start a practice session.'}
                        </p>
                        <Link href="/questions"><Button>Start Practicing</Button></Link>
                    </CardContent>
                </Card>
            ) : (
                <>
                    {/* By subject */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">By subject</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {summary.subjects.map((s, i) => (
                                <div key={s.id} className="space-y-1">
                                    <div className="flex items-center justify-between gap-2 text-sm">
                                        <span className="font-medium truncate">{s.name}</span>
                                        <span className="text-muted-foreground tabular-nums shrink-0">
                                            {formatDuration(s.seconds)} · {s.questions} q
                                        </span>
                                    </div>
                                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                                        <div
                                            className="h-full rounded-full"
                                            style={{
                                                width: `${Math.max(2, Math.round((s.seconds / maxSubjectSeconds) * 100))}%`,
                                                backgroundColor: s.color || FALLBACK_COLORS[i % FALLBACK_COLORS.length],
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </CardContent>
                    </Card>

                    {/* Daily log */}
                    <div className="space-y-2">
                        <h2 className="text-sm font-semibold text-muted-foreground">Daily log</h2>
                        {summary.days.map(([date, day]) => (
                            <Card key={date}>
                                <CardContent className="p-4 space-y-2">
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <div className="font-medium">
                                                {localDate(date).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
                                            </div>
                                            <div className="text-sm text-muted-foreground">{day.questions} questions</div>
                                        </div>
                                        <Badge variant="secondary" className="text-sm tabular-nums">{formatDuration(day.seconds)}</Badge>
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {day.subjects
                                            .slice()
                                            .sort((a, b) => b.seconds - a.seconds)
                                            .map(r => (
                                                <span key={r.id} className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                                                    {r.subject_name || `Subject ${r.subject}`} · {formatDuration(r.seconds)}
                                                </span>
                                            ))}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
