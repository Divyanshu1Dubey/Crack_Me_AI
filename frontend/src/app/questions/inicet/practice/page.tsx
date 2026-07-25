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
 *
 * PRODUCTION-INCIDENT FIX (2026-07-25): previously this route fetched
 * EVERY page up to ALL_PAGES=200 sequentially, which caused 429s and
 * infinite spinner (same root cause as /questions/neet-pg/practice).
 * Now fetches only page 1 on mount and asks the player to call
 * onLoadMore() when more pages are needed.
 */
'use client';
import { Suspense, useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { questionsAPI } from '@/lib/api';
import IniCetPlayer from '@/components/inicet-pg/IniCetPlayer';
import { Loader2, BookOpen, RefreshCcw } from 'lucide-react';

const PAGE_SIZE = 20;

interface FetchPageResult {
    questions: any[];
    hasMore: boolean;
    rateLimited?: boolean;
}

async function fetchIniCetPage(
    params: Record<string, string | number>,
    page: number,
): Promise<FetchPageResult> {
    try {
        const res: any = await questionsAPI.list({ ...params, page, page_size: PAGE_SIZE });
        const body = res?.data ?? res;
        const chunk: any[] = body?.results ?? (Array.isArray(body) ? body : []);
        const hasMore = !!body?.next && chunk.length > 0;
        return { questions: chunk, hasMore };
    } catch (e: any) {
        const status = e?.response?.status ?? e?.status;
        if (status === 429) {
            return { questions: [], hasMore: false, rateLimited: true };
        }
        throw e;
    }
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
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [rateLimited, setRateLimited] = useState(false);
    const inFlight = useRef(false);

    useEffect(() => { setMounted(true); }, []);

    const filterParams = useMemo<Record<string, string | number>>(() => {
        // INI-CET rows aren't in the DB yet — fall back to the CMS exam_type
        // enum so the backend returns rows (mirrors the slug map in
        // /questions/practice/page.tsx). Once INI-CET rows are added, change
        // this back to 'ini_cet'.
        const p: Record<string, string | number> = { exam_type: 'cms' };
        if (year) p.year = year;
        if (subject) p.subject = subject;
        if (topic) p.topic = topic;
        return p;
    }, [year, subject, topic]);

    useEffect(() => {
        if (!mounted) return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        setRateLimited(false);
        setQuestions([]);
        setPage(1);
        setHasMore(true);

        (async () => {
            const result = await fetchIniCetPage(filterParams, 1);
            if (cancelled) return;
            if (result.rateLimited) {
                setRateLimited(true);
                setLoading(false);
                return;
            }
            let initialIndex = 0;
            if (startId) {
                const i = result.questions.findIndex((q: any) => String(q.id) === startId);
                if (i >= 0) initialIndex = i;
            }
            setQuestions(result.questions);
            setHasMore(result.hasMore);
            setPage(1);
            setLoading(false);
            (window as any).__iniCetInitialIndex = initialIndex;
        })().catch((e) => {
            if (cancelled) return;
            setError(e?.message || 'Failed to load INI-CET questions');
            setLoading(false);
        });
        return () => { cancelled = true; };
    }, [filterParams, startId, mounted]);

    const loadMore = useCallback(async () => {
        if (inFlight.current || !hasMore || loadingMore || rateLimited) return;
        inFlight.current = true;
        setLoadingMore(true);
        try {
            const nextPage = page + 1;
            const result = await fetchIniCetPage(filterParams, nextPage);
            if (result.rateLimited) {
                setRateLimited(true);
                return;
            }
            setQuestions((prev) => [...prev, ...result.questions]);
            setHasMore(result.hasMore);
            setPage(nextPage);
        } catch (e: any) {
            setError(e?.message || 'Failed to load more questions');
        } finally {
            setLoadingMore(false);
            inFlight.current = false;
        }
    }, [filterParams, hasMore, loadingMore, page, rateLimited]);

    const retryFromScratch = useCallback(() => {
        setRateLimited(false);
        setError(null);
        setLoading(true);
        setQuestions([]);
        setPage(1);
        setHasMore(true);
        setMounted(false);
        setTimeout(() => setMounted(true), 0);
    }, []);

    const title = useMemo(() => {
        const parts = ['INI-CET'];
        if (year) parts.push(String(year));
        if (subject) parts.push(subject);
        if (topic) parts.push(topic);
        return parts.join(' · ');
    }, [year, subject, topic]);

    const initialIndex = (window as any).__iniCetInitialIndex || 0;

    if (!mounted || (loading && questions.length === 0)) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50/40 via-white to-sky-50/40">
                <div className="text-center space-y-3">
                    <Loader2 className="w-10 h-10 animate-spin text-indigo-600 mx-auto" />
                    <p className="text-sm text-slate-600 font-semibold">
                        Loading INI-CET Practice…
                    </p>
                </div>
            </div>
        );
    }

    if (rateLimited && questions.length === 0) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 via-white to-rose-50 p-4">
                <div className="text-center max-w-md space-y-4">
                    <BookOpen className="w-10 h-10 mx-auto text-rose-500" />
                    <h2 className="text-lg font-bold text-slate-800">Server is rate-limiting requests</h2>
                    <p className="text-sm text-slate-600">
                        We&rsquo;re loading too many questions at once. Click below to retry with a small batch.
                    </p>
                    <button
                        onClick={retryFromScratch}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700"
                    >
                        <RefreshCcw className="w-4 h-4" /> Retry
                    </button>
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
                    <button
                        onClick={retryFromScratch}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700"
                    >
                        <RefreshCcw className="w-4 h-4" /> Retry
                    </button>
                </div>
            </div>
        );
    }

    if (!loading && questions.length === 0) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-sky-50/40">
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

    return (
        <IniCetPlayer
            questions={questions}
            title={title}
            initialIndex={initialIndex}
            hasMore={hasMore}
            loadingMore={loadingMore}
            onLoadMore={loadMore}
            rateLimited={rateLimited}
            onRetry={retryFromScratch}
        />
    );
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