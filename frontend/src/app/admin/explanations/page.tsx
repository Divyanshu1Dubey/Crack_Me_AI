'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
    editorialAPI,
    explanationBatchAPI,
    type ExplanationBatchItemRow,
    type ExplanationBatchOverview,
    type ExplanationReviewRow,
} from '@/lib/editorialAPI';
import { FormattedText } from '@/components/FormattedText';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Sparkles, CheckCircle2, AlertTriangle, ExternalLink } from 'lucide-react';

/**
 * /admin/explanations — the AI explanation batch and its review queue (backend questions/explanation_batch.py).
 *
 * A batch generates explanations only for questions that have none (or one written for another key), and saves one
 * only when the AI's own answer is the stored key, without any citation the model made up. Saved explanations are
 * "AI-generated, not yet reviewed" for students until an admin reviews them here. Questions where the AI chose
 * another answer are listed for a key check; nothing is saved for them.
 */

const STATUS_LABEL: Record<string, string> = {
    queued: 'Queued',
    claimed: 'Generating',
    done: 'Saved (to review)',
    disagrees: 'AI chose another answer',
    invalid: 'Unusable output',
    failed: 'No AI answered',
    skipped: 'Skipped',
};
const EXAMS: { value: string; label: string }[] = [
    { value: '', label: 'All exams' },
    { value: 'cms', label: 'UPSC CMS' },
    { value: 'neet_pg', label: 'NEET PG' },
    { value: 'ini_cet', label: 'INI-CET' },
];

function errorText(err: unknown, fallback: string): string {
    const data = (err as { response?: { data?: { error?: string } } })?.response?.data;
    return data?.error || fallback;
}

function paperLabel(row: { exam_type: string; year: number; paper: number; display_number: number | null }): string {
    const parts = [row.exam_type.toUpperCase().replace('_', ' ')];
    if (row.year) parts.push(String(row.year));
    if (row.paper) parts.push(`Paper ${row.paper === 1 ? 'I' : 'II'}`);
    if (row.display_number) parts.push(`Q${row.display_number}`);
    return parts.join(' · ');
}

export default function AdminExplanationsPage() {
    const { user, loading: authLoading } = useAuth();
    const router = useRouter();
    const isAdmin = !!user && (user.role === 'admin' || user.is_admin);

    const [overview, setOverview] = useState<ExplanationBatchOverview | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [exam, setExam] = useState('');
    const [years, setYears] = useState('');
    const [limit, setLimit] = useState('');
    const [includeStale, setIncludeStale] = useState(true);
    const [processCount, setProcessCount] = useState('100');
    const [itemsFor, setItemsFor] = useState<{ runId: number; status: string } | null>(null);
    const [items, setItems] = useState<ExplanationBatchItemRow[]>([]);
    const [review, setReview] = useState<ExplanationReviewRow[]>([]);
    const [reviewCount, setReviewCount] = useState(0);
    const [reviewPage, setReviewPage] = useState(1);
    const [reviewExam, setReviewExam] = useState('');

    const loadOverview = useCallback(async () => {
        try {
            setOverview((await explanationBatchAPI.overview()).data);
        } catch (err) {
            setError(errorText(err, 'Could not load the explanation batches.'));
        }
    }, []);

    const loadReview = useCallback(async (page: number, examType: string) => {
        try {
            const res = await explanationBatchAPI.reviewQueue({ page, exam_type: examType || undefined });
            setReview(res.data.results);
            setReviewCount(res.data.count);
            setReviewPage(res.data.page);
        } catch (err) {
            setError(errorText(err, 'Could not load the review queue.'));
        }
    }, []);

    useEffect(() => {
        if (authLoading) return;
        if (!user) {
            router.replace('/login?next=' + encodeURIComponent('/admin/explanations'));
            return;
        }
        if (!isAdmin) {
            router.replace('/dashboard');
            return;
        }
        loadOverview();
        loadReview(1, '');
    }, [authLoading, user, isAdmin, router, loadOverview, loadReview]);

    const createRun = async (e: React.FormEvent) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        setNotice(null);
        try {
            const yearList = years.split(',').map(y => Number(y.trim())).filter(y => Number.isInteger(y) && y > 0);
            const res = await explanationBatchAPI.create({
                exam_type: exam || undefined,
                years: yearList.length ? yearList : undefined,
                include_stale: includeStale,
                limit: Number(limit) > 0 ? Number(limit) : undefined,
            });
            setNotice(`Batch ${res.data.id} created: ${res.data.total} question(s) queued.`);
            await loadOverview();
        } catch (err) {
            setError(errorText(err, 'Could not create the batch.'));
        } finally {
            setBusy(false);
        }
    };

    const processRun = async (runId: number) => {
        setBusy(true);
        setError(null);
        setNotice(null);
        try {
            const res = await explanationBatchAPI.process(runId, { max_items: Number(processCount) || 100 });
            setNotice(`Batch ${runId}: the next ${res.data.max_items} question(s) are being generated by the worker. Refresh to see progress.`);
        } catch (err) {
            setError(errorText(err, 'Could not start the batch.'));
        } finally {
            setBusy(false);
        }
    };

    const showItems = async (runId: number, status: string) => {
        setItemsFor({ runId, status });
        try {
            setItems((await explanationBatchAPI.items(runId, { status })).data.results);
        } catch (err) {
            setError(errorText(err, 'Could not load the questions of this batch.'));
        }
    };

    const markReviewed = async (questionId: number) => {
        setError(null);
        try {
            await editorialAPI.reviewExplanation(questionId);
            setReview(rows => rows.filter(row => row.question_id !== questionId));
            setReviewCount(n => Math.max(0, n - 1));
        } catch (err) {
            setError(errorText(err, 'Could not mark this explanation reviewed (it may have changed: open it).'));
        }
    };

    if (authLoading || !user) {
        return <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">Checking admin access…</div>;
    }
    if (!isAdmin) return null;

    return (
        <div className="p-4 sm:p-6 [.page-container_&]:p-0 max-w-5xl mx-auto space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Sparkles className="h-6 w-6" />
                        AI Explanations
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
                        Generates explanations for questions without one. An explanation is saved only when the AI&apos;s
                        own answer is the stored key, never with a book or page reference the model made up, and students
                        see it as &quot;AI-generated, not yet reviewed&quot; until you review it below.
                    </p>
                </div>
                <Button variant="outline" onClick={() => { loadOverview(); loadReview(reviewPage, reviewExam); }} disabled={busy}>
                    Refresh
                </Button>
            </div>

            {error && (
                <div role="alert" className="rounded-md border border-red-500 bg-red-50 dark:bg-red-950/30 p-3 text-sm text-red-700 dark:text-red-300">{error}</div>
            )}
            {notice && (
                <div role="status" className="rounded-md border border-emerald-500/50 bg-emerald-50 dark:bg-emerald-950/30 p-3 text-sm text-emerald-800 dark:text-emerald-200">{notice}</div>
            )}

            <Card>
                <CardHeader>
                    <CardTitle>Questions without a usable explanation</CardTitle>
                    <CardDescription>
                        Active questions with a valid key whose explanation is missing or was written for another key.
                        Figure questions and locked explanations are left to the editors.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {overview ? (
                        <div className="flex flex-wrap gap-2 text-sm">
                            <Badge>{overview.needed.total} in all</Badge>
                            {Object.entries(overview.needed.by_exam).map(([examType, n]) => (
                                <Badge key={examType} variant="secondary">{examType.replace('_', ' ').toUpperCase()}: {n}</Badge>
                            ))}
                        </div>
                    ) : <p className="text-sm text-muted-foreground">Loading…</p>}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>New batch</CardTitle>
                    <CardDescription>Queues the questions that need an explanation now; nothing is generated until you process it.</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={createRun} className="grid gap-3 sm:grid-cols-2">
                        <label className="space-y-1 text-sm">
                            <span className="font-medium">Exam</span>
                            <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={exam} onChange={e => setExam(e.target.value)}>
                                {EXAMS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                            </select>
                        </label>
                        <label className="space-y-1 text-sm">
                            <span className="font-medium">Years (comma-separated, optional)</span>
                            <Input value={years} onChange={e => setYears(e.target.value)} placeholder="2024, 2025" />
                        </label>
                        <label className="space-y-1 text-sm">
                            <span className="font-medium">At most (optional)</span>
                            <Input type="number" min={1} value={limit} onChange={e => setLimit(e.target.value)} placeholder="500" />
                        </label>
                        <label className="flex items-center gap-2 text-sm pt-6">
                            <input type="checkbox" className="h-4 w-4 accent-primary" checked={includeStale} onChange={e => setIncludeStale(e.target.checked)} />
                            Also explanations written for an earlier (corrected) key
                        </label>
                        <div className="sm:col-span-2">
                            <Button type="submit" disabled={busy}>Create batch</Button>
                        </div>
                    </form>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Batches</CardTitle>
                    <CardDescription>
                        Processing runs on the background worker, a few questions a minute (AI provider limits). A batch can be
                        continued any time: no question is generated twice.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <label className="flex items-center gap-2 text-sm">
                        Questions per &quot;Process&quot;:
                        <Input className="w-24" type="number" min={1} max={500} value={processCount} onChange={e => setProcessCount(e.target.value)} />
                    </label>
                    {(overview?.runs ?? []).length === 0 ? (
                        <p className="text-sm text-muted-foreground">No batch yet.</p>
                    ) : (overview?.runs ?? []).map(run => (
                        <div key={run.id} className="rounded-lg border p-3 space-y-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="text-sm font-medium">
                                    Batch {run.id} · {new Date(run.created_at).toLocaleString('en-IN')} · {run.scope.exam_type || 'all exams'}
                                    {run.scope.years && run.scope.years.length ? ` · ${run.scope.years.join(', ')}` : ''} · {run.total} question(s)
                                </div>
                                <Button size="sm" disabled={busy || !(run.counts.queued || run.counts.claimed)} onClick={() => processRun(run.id)}>
                                    Process next {Number(processCount) || 100}
                                </Button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {Object.entries(run.counts).map(([status, n]) => (
                                    <button key={status} type="button" onClick={() => showItems(run.id, status)}
                                            className="rounded-full border px-2 py-0.5 text-xs hover:bg-muted">
                                        {STATUS_LABEL[status] ?? status}: {n}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                    {itemsFor && (
                        <div className="rounded-lg border bg-muted/20 p-3 space-y-2">
                            <div className="text-sm font-medium">
                                Batch {itemsFor.runId} · {STATUS_LABEL[itemsFor.status] ?? itemsFor.status} ({items.length} shown)
                            </div>
                            {itemsFor.status === 'disagrees' && (
                                <p className="text-xs text-muted-foreground flex items-start gap-1">
                                    <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                                    The AI answered these differently from the stored key. Nothing was saved; check the key against an
                                    official or textbook source in the answer-key review.
                                </p>
                            )}
                            {items.map(item => (
                                <div key={item.question_id} className="text-sm border-t pt-2">
                                    <div className="text-xs text-muted-foreground">#{item.question_id} · {paperLabel(item)} · key {item.key}{item.detail ? ` · ${item.detail}` : ''}</div>
                                    <div>{item.question_preview}</div>
                                    <Link href={`/admin/review-queue?q=${item.question_id}`} className="text-xs text-primary inline-flex items-center gap-1 hover:underline">
                                        Open in the answer-key review <ExternalLink className="h-3 w-3" />
                                    </Link>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Review queue ({reviewCount})</CardTitle>
                    <CardDescription>
                        AI-generated explanations nobody reviewed yet. Read each against a textbook; &quot;Mark reviewed&quot; records
                        your review for this exact text (an edit later needs a new review). To change one, open it.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <label className="flex items-center gap-2 text-sm">
                        Exam:
                        <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={reviewExam}
                                onChange={e => { setReviewExam(e.target.value); loadReview(1, e.target.value); }}>
                            {EXAMS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                        </select>
                    </label>
                    {review.length === 0 ? (
                        <p className="text-sm text-muted-foreground">Nothing to review.</p>
                    ) : review.map(row => (
                        <div key={row.question_id} className="rounded-lg border p-3 space-y-2">
                            <div className="text-xs text-muted-foreground">#{row.question_id} · {paperLabel(row)} · key {row.correct_answer}</div>
                            <div className="text-sm font-medium">{row.question_preview}</div>
                            <div className="text-sm rounded-md bg-muted/30 p-2">
                                <FormattedText text={row.explanation} />
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <Button size="sm" onClick={() => markReviewed(row.question_id)}>
                                    <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Mark reviewed
                                </Button>
                                <Button size="sm" variant="outline" asChild>
                                    <Link href={`/admin/review-queue?q=${row.question_id}`}>Open to edit</Link>
                                </Button>
                            </div>
                        </div>
                    ))}
                    {reviewCount > review.length && (
                        <div className="flex gap-2">
                            <Button size="sm" variant="outline" disabled={reviewPage <= 1} onClick={() => loadReview(reviewPage - 1, reviewExam)}>Previous</Button>
                            <Button size="sm" variant="outline" disabled={reviewPage * 50 >= reviewCount} onClick={() => loadReview(reviewPage + 1, reviewExam)}>Next</Button>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
