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
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import EngagingLoader from '@/components/EngagingLoader';
import { ExamTrackProvider } from '@/components/ExamTrackProvider';
import { Loader2, Stethoscope } from 'lucide-react';

const ALL_PAGES = 200; // DRF caps page_size at 20, so paginate to fetch everything.

async function fetchAllNeetPgQuestions(
    params: Record<string, string | number>,
    onProgress?: (loaded: number) => void,
): Promise<any[]> {
    const results: any[] = [];
    let page = 1;
    // eslint-disable-next-line no-constant-condition
    while (true) {
        const res: any = await questionsAPI.list({ ...params, page, page_size: 20 });
        const chunk: any[] = res?.results ?? (Array.isArray(res) ? res : []);
        if (!chunk.length) break;
        results.push(...chunk);
        onProgress?.(results.length);
        const next = res?.next;
        if (!next) break;
        page += 1;
        if (page > ALL_PAGES) break;
    }
    return results;
}

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
    const [mounted, setMounted] = useState(false);
    const [loadedCount, setLoadedCount] = useState(0);

    useEffect(() => { setMounted(true); }, []);

    useEffect(() => {
        let cancelled = false;
        if (!mounted) return;
        setLoading(true);
        setError(null);
        setQuestions([]);
        setLoadedCount(0);

        (async () => {
            try {
                const params: Record<string, string | number> = { exam_type: 'neet_pg' };
                if (year) params.year = year;
                if (subject) params.subject = subject;
                if (topic) params.topic = topic;
                if (bookmarked) params.bookmarked = 'true';

                const results = await fetchAllNeetPgQuestions(params, (n) => {
                    if (!cancelled) setLoadedCount(n);
                });

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
    }, [year, subject, topic, bookmarked, startId, mounted]);

    const title = useMemo(() => {
        const parts = ['NEET PG'];
        if (year) parts.push(String(year));
        if (subject) parts.push(subject);
        if (topic) parts.push(topic);
        if (bookmarked) parts.push('Bookmarked');
        return parts.join(' · ');
    }, [year, subject, topic, bookmarked]);

    // Before the client has mounted we render ONLY the spinner to avoid
    // server/client hydration mismatches on React #418 (the loader-vs-empty
    // branch race). Only after `mounted` is true do we let the empty /
    // error branch render — by then the fetch has had a chance to land.
    if (!mounted || (loading && questions.length === 0)) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-50/40 via-white to-emerald-50/40">
                <div className="text-center space-y-3">
                    <Loader2 className="w-10 h-10 animate-spin text-teal-600 mx-auto" />
                    <p className="text-sm text-slate-600 font-semibold">
                        Loading NEET PG Practice… {loadedCount > 0 ? `(${loadedCount} loaded)` : ''}
                    </p>
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

    if (!loading && questions.length === 0) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-50 via-white to-emerald-50">
                <div className="text-center space-y-3">
                    <Stethoscope className="w-10 h-10 mx-auto text-teal-500" />
                    <p className="text-base font-semibold text-slate-700">No NEET PG questions available</p>
                    <a
                        href="/questions?exam=neet-pg"
                        className="inline-block px-4 py-2 rounded-lg bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700"
                    >
                        Back to NEET PG Bank
                    </a>
                </div>
            </div>
        );
    }

    return <NeetPgPlayer questions={questions} title={title} />;
}

export default function NeetPgPracticePage() {
    return (
        <ExamTrackProvider>
            <Sidebar />
            <Suspense fallback={
                <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-50/40 via-white to-emerald-50/40">
                    <Loader2 className="w-10 h-10 animate-spin text-teal-600" />
                </div>
            }>
                <NeetPgPracticeInner />
            </Suspense>
        </ExamTrackProvider>
    );
}
