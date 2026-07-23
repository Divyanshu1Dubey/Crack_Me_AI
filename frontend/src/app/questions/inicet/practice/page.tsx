/**
 * INI-CET Question Player — entry route.
 *
 * /questions/inicet/practice
 *   ?year=2024               — practice INI-CET paper year
 *   ?subject=<id-or-name>    — filter by subject
 *   ?topic=<name>            — filter by topic
 *   ?q=<id>                  — start at a single question
 *
 * Loads via /api/questions/?exam_type=ini_cet&... and hands them off to
 * <IniCetPlayer>. Independent of NEET PG — different palette, image-rich
 * explanation panels.
 */
'use client';
import { Suspense, useEffect, useState, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { questionsAPI } from '@/lib/api';
import IniCetPlayer from '@/components/inicet-pg/IniCetPlayer';
import { Loader2, BookOpen } from 'lucide-react';

const ALL_PAGES = 200;

async function fetchAllIniCetQuestions(
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

function IniCetPracticeInner() {
    const searchParams = useSearchParams();
    const year = searchParams.get('year');
    const subject = searchParams.get('subject');
    const topic = searchParams.get('topic');
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
                const params: Record<string, string | number> = { exam_type: 'ini_cet' };
                if (year) params.year = year;
                if (subject) params.subject = subject;
                if (topic) params.topic = topic;

                const results = await fetchAllIniCetQuestions(params, (n) => {
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
                    setError(e?.message || 'Failed to load INI-CET questions');
                    setLoading(false);
                }
            }
        })();
        return () => { cancelled = true; };
    }, [year, subject, topic, startId, mounted]);

    const title = useMemo(() => {
        const parts = ['INI-CET'];
        if (year) parts.push(String(year));
        if (subject) parts.push(subject);
        if (topic) parts.push(topic);
        return parts.join(' · ');
    }, [year, subject, topic]);

    if (!mounted || (loading && questions.length === 0)) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50/40 via-white to-sky-50/40">
                <div className="text-center space-y-3">
                    <Loader2 className="w-10 h-10 animate-spin text-indigo-600 mx-auto" />
                    <p className="text-sm text-slate-600 font-semibold">
                        Loading INI-CET Practice… {loadedCount > 0 ? `(${loadedCount} loaded)` : ''}
                    </p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 via-white to-rose-50 p-4">
                <div className="text-center max-w-md space-y-3">
                    <BookOpen className="w-10 h-10 mx-auto text-rose-500" />
                    <h2 className="text-lg font-bold text-slate-800">Couldn't load INI-CET questions</h2>
                    <p className="text-sm text-slate-600">{error}</p>
                </div>
            </div>
        );
    }

    if (!loading && questions.length === 0) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-sky-50">
                <div className="text-center space-y-3">
                    <BookOpen className="w-10 h-10 mx-auto text-indigo-500" />
                    <p className="text-base font-semibold text-slate-700">No INI-CET questions available</p>
                    <a
                        href="/questions?exam=ini-cet"
                        className="inline-block px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700"
                    >
                        Back to INI-CET Bank
                    </a>
                </div>
            </div>
        );
    }

    return <IniCetPlayer questions={questions} title={title} />;
}

export default function IniCetPracticePage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50/40 via-white to-sky-50/40">
                <Loader2 className="w-10 h-10 animate-spin text-indigo-600" />
            </div>
        }>
            <IniCetPracticeInner />
        </Suspense>
    );
}
