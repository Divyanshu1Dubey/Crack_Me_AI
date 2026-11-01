'use client';
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { mistakeNotebookAPI } from '@/lib/api';
import { extractAnalysisFromJson, sanitizeOptionText, sanitizeQuestionText } from '@/lib/textCleanup';
import { FormattedText, FormattedOptionText } from '@/components/FormattedText';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, BookOpen, CalendarClock, CheckCircle2, ChevronDown, ChevronUp, ExternalLink, Flag, RotateCcw } from 'lucide-react';

/** Shape of `MistakeNotebookSerializer` (backend/analytics/serializers.py). */
interface MistakeEntry {
    id: number;
    question: number;
    question_text: string;
    option_a: string;
    option_b: string;
    option_c: string;
    option_d: string;
    selected_answer: string | null;
    correct_answer: string;
    explanation: string;
    subject_name: string;
    topic_name: string;
    exam_type: string;
    user_note: string;
    is_flagged: boolean;
    review_status: 'new' | 'learning' | 'reviewing' | 'mastered' | string;
    review_count: number;
    next_review_at: string | null;
    created_at: string;
}

interface MistakeStats {
    total: number;
    by_status: Record<string, number>;
    flagged: number;
    due_today: number;
}

type Filter = 'all' | 'due' | 'new' | 'learning' | 'reviewing' | 'mastered';

const FILTERS: { key: Filter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'due', label: 'Due now' },
    { key: 'new', label: 'New' },
    { key: 'learning', label: 'Learning' },
    { key: 'reviewing', label: 'Reviewing' },
    { key: 'mastered', label: 'Mastered' },
];

const PAGE_SIZE = 20;

const STATUS_STYLES: Record<string, string> = {
    new: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    learning: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    reviewing: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    mastered: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
};

/** Question-bank route for a question's exam (each bank opens `?q=<id>`). */
function bankHref(examType: string, questionId: number): string {
    if (examType === 'neet_pg') return `/questions/neet-pg/practice?q=${questionId}`;
    if (examType === 'ini_cet') return `/questions/inicet/practice?q=${questionId}`;
    return `/questions?q=${questionId}`;
}

/** The notebook does not load question images; show a marker instead of raw tokens. */
const withoutImageTokens = (text: string) => (text || '').replace(/\[\[img:\d+\]\]/g, ' [image] ');

function formatNextReview(iso: string | null): string {
    if (!iso) return '';
    const when = new Date(iso);
    if (Number.isNaN(when.getTime())) return '';
    if (when.getTime() <= Date.now()) return 'Due now';
    return `Next review ${when.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`;
}

export default function MistakeNotebookPage() {
    // Member-only page: logged-out visitors go to /login?next=/mistake-notebook.
    const { ready } = useRequireAuth();
    const [entries, setEntries] = useState<MistakeEntry[]>([]);
    const [count, setCount] = useState(0);
    const [page, setPage] = useState(1);
    const [filter, setFilter] = useState<Filter>('all');
    const [stats, setStats] = useState<MistakeStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expanded, setExpanded] = useState<number | null>(null);
    const [reviewing, setReviewing] = useState<number | null>(null);
    const [reloadKey, setReloadKey] = useState(0);

    const loadStats = useCallback(() => {
        mistakeNotebookAPI.stats().then(res => setStats(res.data as MistakeStats)).catch(() => { });
    }, []);

    const loadEntries = useCallback(async (nextFilter: Filter, nextPage: number) => {
        if (nextFilter === 'due') {
            // The due endpoint is not paginated (it returns everything due now).
            const res = await mistakeNotebookAPI.due();
            const rows = (res.data?.results ?? []) as MistakeEntry[];
            return { rows, total: res.data?.count ?? rows.length };
        }
        const params: Record<string, string | number> = { page: nextPage, page_size: PAGE_SIZE };
        if (nextFilter !== 'all') params.review_status = nextFilter;
        const res = await mistakeNotebookAPI.list(params);
        const data = res.data;
        const rows = (Array.isArray(data) ? data : data?.results ?? []) as MistakeEntry[];
        return { rows, total: Array.isArray(data) ? rows.length : data?.count ?? rows.length };
    }, []);

    useEffect(() => {
        if (!ready) return;
        let alive = true;
        setLoading(true);
        setError(null);
        setExpanded(null);
        loadEntries(filter, 1).then(({ rows, total }) => {
            if (!alive) return;
            setEntries(rows);
            setCount(total);
            setPage(1);
        }).catch(() => {
            if (alive) setError('Could not load your mistake notebook. Check your connection and try again.');
        }).finally(() => {
            if (alive) setLoading(false);
        });
        return () => { alive = false; };
    }, [ready, filter, reloadKey, loadEntries]);

    useEffect(() => {
        if (ready) loadStats();
    }, [ready, reloadKey, loadStats]);

    const loadMore = async () => {
        setLoadingMore(true);
        try {
            const { rows, total } = await loadEntries(filter, page + 1);
            setEntries(prev => [...prev, ...rows.filter(r => !prev.some(p => p.id === r.id))]);
            setCount(total);
            setPage(page + 1);
        } catch {
            setError('Could not load more entries. Please try again.');
        } finally {
            setLoadingMore(false);
        }
    };

    const handleReview = async (entryId: number) => {
        setReviewing(entryId);
        try {
            const res = await mistakeNotebookAPI.review(entryId);
            const updated = res.data as MistakeEntry;
            // Reviewed entries leave the "due" view and views of another status.
            const stillVisible = filter === 'all' || (filter !== 'due' && updated.review_status === filter);
            setEntries(prev => (stillVisible
                ? prev.map(e => (e.id === entryId ? { ...e, ...updated } : e))
                : prev.filter(e => e.id !== entryId)));
            if (!stillVisible) setCount(c => Math.max(0, c - 1));
            loadStats();
        } catch {
            setError('Could not save the review. Please try again.');
        } finally {
            setReviewing(null);
        }
    };

    const inReview = (stats?.by_status?.learning || 0) + (stats?.by_status?.reviewing || 0);
    const statCards = [
        { label: 'Total mistakes', value: stats?.total ?? 0, className: '' },
        { label: 'Due now', value: stats?.due_today ?? 0, className: 'text-red-600 dark:text-red-400' },
        { label: 'In review', value: inReview, className: 'text-blue-600 dark:text-blue-400' },
        { label: 'Mastered', value: stats?.by_status?.mastered ?? 0, className: 'text-green-600 dark:text-green-400' },
    ];

    // The route layout puts this page inside the app shell (.page-container),
    // which already pads the page; keep our own padding only outside it.
    return (
        <div className="max-w-4xl mx-auto p-4 md:p-6 [.page-container_&]:p-0 space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
                    <BookOpen className="w-6 h-6 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold">Mistake Notebook</h1>
                    <p className="text-sm text-muted-foreground">
                        Every question you get wrong lands here. Review it until it sticks.
                    </p>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {statCards.map(card => (
                    <Card key={card.label}>
                        <CardContent className="p-4 text-center">
                            {stats ? (
                                <div className={`text-2xl font-bold tabular-nums ${card.className}`}>{card.value}</div>
                            ) : (
                                <Skeleton className="h-8 w-12 mx-auto" />
                            )}
                            <div className="text-xs text-muted-foreground mt-1">{card.label}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Filters */}
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1" role="tablist" aria-label="Filter mistakes">
                {FILTERS.map(f => (
                    <Button
                        key={f.key}
                        role="tab"
                        aria-selected={filter === f.key}
                        size="sm"
                        variant={filter === f.key ? 'default' : 'outline'}
                        className="shrink-0 rounded-full"
                        onClick={() => setFilter(f.key)}
                    >
                        {f.label}
                        {f.key === 'due' && (stats?.due_today ?? 0) > 0 && (
                            <span className="ml-1.5 rounded-full bg-red-500 px-1.5 text-[10px] font-semibold text-white">
                                {stats?.due_today}
                            </span>
                        )}
                    </Button>
                ))}
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

            {/* Entries */}
            {loading ? (
                <div className="space-y-3">
                    {[1, 2, 3].map(i => <Skeleton key={i} className="h-32" />)}
                </div>
            ) : entries.length === 0 && !error ? (
                <Card>
                    <CardContent className="p-12 text-center">
                        <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold mb-2">
                            {filter === 'all' ? 'No mistakes yet!' : filter === 'due' ? 'Nothing due right now' : 'Nothing here'}
                        </h3>
                        <p className="text-muted-foreground mb-4">
                            {filter === 'all'
                                ? 'Practice questions or take a test. Wrong answers are saved here automatically.'
                                : 'Try another filter, or keep practicing.'}
                        </p>
                        <Link href="/questions">
                            <Button>Start Practicing</Button>
                        </Link>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    {entries.map(entry => {
                        const open = expanded === entry.id;
                        const correct = (entry.correct_answer || '').toUpperCase();
                        const picked = (entry.selected_answer || '').toUpperCase();
                        const options = [
                            { letter: 'A', text: entry.option_a },
                            { letter: 'B', text: entry.option_b },
                            { letter: 'C', text: entry.option_c },
                            { letter: 'D', text: entry.option_d },
                        ].filter(o => o.text);
                        const explanation = entry.explanation ? extractAnalysisFromJson(entry.explanation) : '';
                        const nextReview = formatNextReview(entry.next_review_at);
                        return (
                            <Card key={entry.id} className={entry.is_flagged ? 'border-amber-300 dark:border-amber-700' : ''}>
                                <CardContent className="p-4 space-y-3">
                                    <div className="flex flex-wrap items-center gap-2 text-xs">
                                        <Badge className={`text-xs capitalize ${STATUS_STYLES[entry.review_status] || 'bg-muted text-foreground'}`}>
                                            {entry.review_status}
                                        </Badge>
                                        {entry.subject_name && <Badge variant="outline" className="text-xs">{entry.subject_name}</Badge>}
                                        {entry.topic_name && <span className="text-muted-foreground truncate max-w-[14rem]">{entry.topic_name}</span>}
                                        {entry.is_flagged && (
                                            <Badge variant="outline" className="text-xs border-amber-400 text-amber-600">
                                                <Flag className="w-3 h-3 mr-1" /> Flagged
                                            </Badge>
                                        )}
                                        {nextReview && (
                                            <span className="ml-auto inline-flex items-center gap-1 text-muted-foreground">
                                                <CalendarClock className="w-3 h-3" /> {nextReview}
                                            </span>
                                        )}
                                    </div>

                                    <div className={`text-sm font-medium leading-relaxed ${open ? '' : 'line-clamp-3'}`}>
                                        <FormattedOptionText text={withoutImageTokens(sanitizeQuestionText(entry.question_text))} />
                                    </div>

                                    {!open && (
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <Badge variant="outline" className="text-xs border-red-300 text-red-700 dark:border-red-800 dark:text-red-300">
                                                Your answer: {picked || 'Skipped'}
                                            </Badge>
                                            <Badge className="text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
                                                Correct: {correct || '?'}
                                            </Badge>
                                        </div>
                                    )}

                                    {open && (
                                        <div className="space-y-2">
                                            {options.map(o => {
                                                const isCorrect = o.letter === correct;
                                                const isPicked = o.letter === picked && !isCorrect;
                                                return (
                                                    <div
                                                        key={o.letter}
                                                        className={`flex gap-3 rounded-md border p-2.5 text-sm ${isCorrect
                                                            ? 'border-green-400 bg-green-50 dark:border-green-700 dark:bg-green-950/40'
                                                            : isPicked
                                                                ? 'border-red-400 bg-red-50 dark:border-red-800 dark:bg-red-950/40'
                                                                : 'border-border'}`}
                                                    >
                                                        <span className="font-semibold w-5 shrink-0">{o.letter}</span>
                                                        <div className="flex-1 min-w-0">
                                                            <FormattedOptionText text={withoutImageTokens(sanitizeOptionText(o.text))} />
                                                        </div>
                                                        {isCorrect && <span className="text-xs font-medium text-green-700 dark:text-green-300 shrink-0">Correct</span>}
                                                        {isPicked && <span className="text-xs font-medium text-red-700 dark:text-red-300 shrink-0">Your answer</span>}
                                                    </div>
                                                );
                                            })}
                                            {explanation ? (
                                                <div className="rounded-md bg-muted/50 p-3 text-sm">
                                                    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Explanation</div>
                                                    <FormattedText text={withoutImageTokens(explanation)} />
                                                </div>
                                            ) : (
                                                <p className="text-xs text-muted-foreground">
                                                    No written explanation yet. Open it in the question bank for the AI explanation.
                                                </p>
                                            )}
                                        </div>
                                    )}

                                    {entry.user_note && (
                                        <div className="bg-muted/50 rounded-md p-2 text-xs text-muted-foreground">
                                            <strong>Your note:</strong> {entry.user_note}
                                        </div>
                                    )}

                                    <div className="flex items-center gap-2 flex-wrap">
                                        <Button variant="outline" size="sm" onClick={() => setExpanded(open ? null : entry.id)} aria-expanded={open}>
                                            {open ? <ChevronUp className="w-3 h-3 mr-1" /> : <ChevronDown className="w-3 h-3 mr-1" />}
                                            {open ? 'Hide answer' : 'Review answer'}
                                        </Button>
                                        {entry.review_status !== 'mastered' && (
                                            <Button size="sm" onClick={() => handleReview(entry.id)} disabled={reviewing === entry.id}>
                                                {reviewing === entry.id ? 'Saving…' : 'Mark as reviewed'}
                                            </Button>
                                        )}
                                        <Link href={bankHref(entry.exam_type, entry.question)} className="ml-auto">
                                            <Button variant="ghost" size="sm">
                                                <ExternalLink className="w-3 h-3 mr-1" /> Open in question bank
                                            </Button>
                                        </Link>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}

                    {filter !== 'due' && entries.length < count && (
                        <div className="flex justify-center pt-2">
                            <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
                                {loadingMore ? 'Loading…' : `Load more (${count - entries.length} left)`}
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
