/**
 * NEET PG Question Player — entry route.
 *
 * /questions/neet-pg/practice
 *   ?year=2025               — practice NEET PG 2025 paper
 *   ?subject=<id-or-name>    — filter by subject
 *   ?topic=<name>            — filter by topic
 *   ?bookmarked=1            — only bookmarked questions
 *   ?q=<id>                  — start at a single question (loads it plus
 *                              a window of nearby questions)
 *
 * Loads questions via /api/questions/?exam_type=neet_pg&... and hands
 * them off to <NeetPgPlayer>. Completely independent of the UPSC CMS
 * /questions/practice route — different layout, palette, colour scheme.
 */
'use client';
import { Suspense, useEffect, useState, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { questionsAPI } from '@/lib/api';
import NeetPgPlayer from '@/components/neet-pg/NeetPgPlayer';
import { Loader2, Stethoscope } from 'lucide-react';

function NeetPgPracticeInner() {
    const searchParams = useSearchParams();
    const year = searchParams.get('year');
    const subject = searchParams.get('subject');
    const topic = searchParams.get('topic');
    const bookmarked = searchParams.get('bookmarked') === '1';
    const startId = searchParams.get('q');

    const [questions, setQuestions] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        (async () => {
            try {
                const params: Record<string, string | number> = {
                    exam_type: 'neet_pg',
                    page_size: 200,
                };
                if (year) params.year = year;
                if (subject) params.subject = subject;
                if (topic) params.topic = topic;
                if (bookmarked) params.bookmarked = 'true';

                const res = await questionsAPI.list(params);
                const results = (res as any)?.results ?? (res as any) ?? [];

                let initialIndex = 0;
                if (startId) {
                    const i = results.findIndex((q: any) => String(q.id) === startId);
                    if (i >= 0) initialIndex = i;
                }
                if (!cancelled) {
                    setQuestions(results);
                    setLoading(false);
                }
            } catch (e: any) {
                if (!cancelled) {
                    setError(e?.message || 'Failed to load NEET PG questions');
                    setLoading(false);
                }
            }
        })();
        return () => { cancelled = true; };
    }, [year, subject, topic, bookmarked, startId]);

    const title = useMemo(() => {
        const parts = ['NEET PG'];
        if (year) parts.push(String(year));
        if (subject) parts.push(subject);
        if (topic) parts.push(topic);
        if (bookmarked) parts.push('Bookmarked');
        return parts.join(' · ');
    }, [year, subject, topic, bookmarked]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-50/40 via-white to-emerald-50/40">
                <div className="text-center space-y-3">
                    <Loader2 className="w-10 h-10 animate-spin text-teal-600 mx-auto" />
                    <p className="text-sm text-slate-600 font-semibold">Loading NEET PG Practice…</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 via-white to-rose-50 p-4">
                <div className="text-center max-w-md space-y-3">
                    <Stethoscope className="w-10 h-10 mx-auto text-rose-500" />
                    <h2 className="text-lg font-bold text-slate-800">Couldn't load NEET PG questions</h2>
                    <p className="text-sm text-slate-600">{error}</p>
                </div>
            </div>
        );
    }

    return <NeetPgPlayer questions={questions} title={title} />;
}

export default function NeetPgPracticePage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-50/40 via-white to-emerald-50/40">
                <Loader2 className="w-10 h-10 animate-spin text-teal-600" />
            </div>
        }>
            <NeetPgPracticeInner />
        </Suspense>
    );
}
