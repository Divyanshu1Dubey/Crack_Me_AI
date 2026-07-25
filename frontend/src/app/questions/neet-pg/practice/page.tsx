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
 * PRODUCTION-INCIDENT FIX (2026-07-25): Previously this route fetched
 * EVERY page of /api/questions/?exam_type=neet_pg&page=N sequentially
 * up to ALL_PAGES=200 (up to 200 requests). With 3-4 concurrent users
 * that saturated the DRF throttle / Cloudflare and returned 429. The
 * player then sat on the spinner forever, eventually surfacing
 * "Couldn't load NEET PG questions / Request failed with status code
 * 429". React #418 also fired because the spinner-vs-empty branch
 * raced with hydration.
 *
 * New behaviour:
 *   - Fetch ONLY page 1 (20 questions) on mount.
 *   - Hand the player a `loadMore(page)` callback that fetches the
 *     NEXT page only when the player reaches near the end of what's
 *     loaded (or jumps via the palette past `questions.length`).
 *   - Show the player immediately with the first 20 questions —
 *     spinner exits as soon as page 1 lands.
 *   - 429 produces a clear retry UI (not an infinite spinner).
 */
'use client';
import { Suspense, useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { questionsAPI } from '@/lib/api';
import NeetPgPlayer from '@/components/neet-pg/NeetPgPlayer';
import Sidebar from '@/components/Sidebar';
import { ExamTrackProvider } from '@/components/ExamTrackProvider';
import { Loader2, Stethoscope, RefreshCcw } from 'lucide-react';

const PAGE_SIZE = 20;

interface FetchPageResult {
    questions: any[];
    hasMore: boolean;
    /** Set when the API responded with HTTP 429 — caller should show retry UI. */
    rateLimited?: boolean;
}

async function fetchNeetPgPage(
    params: Record<string, string | number>,
    page: number,
): Promise<FetchPageResult> {
    try {
        const res: any = await questionsAPI.list({ ...params, page, page_size: PAGE_SIZE });
        const body = res?.data ?? res;
        const chunk: any[] = body?.results ?? (Array.isArray(body) ? body : []);
        // Treat an empty page OR a missing `next` cursor as the end.
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
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [rateLimited, setRateLimited] = useState(false);
    const inFlight = useRef(false);

    useEffect(() => { setMounted(true); }, []);

    // Stable filter params — re-runs the loader only when filters change.
    const filterParams = useMemo<Record<string, string | number>>(() => {
        const p: Record<string, string | number> = { exam_type: 'neet_pg' };
        if (year) p.year = year;
        if (subject) p.subject = subject;
        if (topic) p.topic = topic;
        if (bookmarked) p.bookmarked = 'true';
        return p;
    }, [year, subject, topic, bookmarked]);

    // Initial load: page 1 only.
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
            const result = await fetchNeetPgPage(filterParams, 1);
            if (cancelled) return;
            if (result.rateLimited) {
                setRateLimited(true);
                setLoading(false);
                return;
            }
            let initial = result.questions;
            let initialIndex = 0;
            if (startId) {
                const i = initial.findIndex((q: any) => String(q.id) === startId);
                if (i >= 0) initialIndex = i;
            }
            setQuestions(initial);
            setHasMore(result.hasMore);
            setPage(1);
            setLoading(false);
            // Stash the initial index so the player can pick it up via prop.
            (window as any).__neetPgInitialIndex = initialIndex;
        })().catch((e) => {
            if (cancelled) return;
            setError(e?.message || 'Failed to load NEET PG questions');
            setLoading(false);
        });
        return () => { cancelled = true; };
    }, [filterParams, startId, mounted]);

    // loadMore: fetch the next page on demand from the player.
    const loadMore = useCallback(async () => {
        if (inFlight.current || !hasMore || loadingMore || rateLimited) return;
        inFlight.current = true;
        setLoadingMore(true);
        try {
            const nextPage = page + 1;
            const result = await fetchNeetPgPage(filterParams, nextPage);
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
        // Re-trigger the initial effect by changing the key.
        setQuestions([]);
        setPage(1);
        setHasMore(true);
        // The simplest way: bump mounted-state via state change → effect re-runs.
        setMounted(false);
        setTimeout(() => setMounted(true), 0);
    }, []);

    const title = useMemo(() => {
        const parts = ['NEET PG'];
        if (year) parts.push(String(year));
        if (subject) parts.push(subject);
        if (topic) parts.push(topic);
        if (bookmarked) parts.push('Bookmarked');
        return parts.join(' · ');
    }, [year, subject, topic, bookmarked]);

    const initialIndex = (window as any).__neetPgInitialIndex || 0;

    // Before mount: render ONLY the spinner. This matches what the
    // server renders, so React #418 doesn't fire on the loader branch.
    if (!mounted || (loading && questions.length === 0)) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-teal-50/40 via-white to-emerald-50/40">
                <div className="text-center space-y-3">
                    <Loader2 className="w-10 h-10 animate-spin text-teal-600 mx-auto" />
                    <p className="text-sm text-slate-600 font-semibold">
                        Loading NEET PG Practice…
                    </p>
                </div>
            </div>
        );
    }

    if (rateLimited && questions.length === 0) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-rose-50 via-white to-rose-50 p-4">
                <div className="text-center max-w-md space-y-4">
                    <Stethoscope className="w-10 h-10 mx-auto text-rose-500" />
                    <h2 className="text-lg font-bold text-slate-800">Server is rate-limiting requests</h2>
                    <p className="text-sm text-slate-600">
                        We&rsquo;re loading too many questions at once. Click below to retry with a small batch.
                    </p>
                    <button
                        onClick={retryFromScratch}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700"
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
                    <Stethoscope className="w-10 h-10 mx-auto text-rose-500" />
                    <h2 className="text-lg font-bold text-slate-800">Couldn't load NEET PG questions</h2>
                    <p className="text-sm text-slate-600">{error}</p>
                    <button
                        onClick={retryFromScratch}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700"
                    >
                        <RefreshCcw className="w-4 h-4" /> Retry
                    </button>
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

    return (
        <NeetPgPlayer
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
