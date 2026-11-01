'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { testsAPI, questionsAPI } from '@/lib/api';
import { FileText, Play, Clock, Target, Sparkles, Plus, Award, ChevronRight, Lock } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { LockedBadge } from '@/components/paywall/LockedBadge';
import { usePaywall } from '@/lib/paywall/paywallContext';
import { useAuth } from '@/lib/auth';

interface TestItem {
    id: number;
    title: string;
    test_type: string;
    subject?: number | null;
    topic?: number | null;
    subject_name: string;
    num_questions: number;
    time_limit_minutes: number;
    attempt_count: number;
    // Freemium (Task 4 / Task 11): true when admin marked this test as
    // a free-preview — free users can attempt it; everyone else needs
    // an active subscription. Surfaced by TestSerializer.
    is_free_preview?: boolean;
    // Derived from backend (2026-08-04): true if this test is free for
    // the CURRENT requester (at most 20 questions, counted server-side).
    // Mirrors the gate in tests_engine/views.py.
    is_free_for_current_user?: boolean;
}

interface Subject {
    id: number;
    name: string;
    code: string;
}

type ListScope = 'library' | 'mine';

// How many of the student's own practice tests are shown before "Show all".
const PRACTICE_PREVIEW = 4;

// Card badge text for Test.test_type (the raw enum values used to show).
const TEST_TYPE_LABELS: Record<string, string> = {
    subject: 'Subject',
    topic: 'Topic',
    mixed: 'Mixed',
    paper1: 'Paper 1',
    paper2: 'Paper 2',
    daily: 'Daily',
    pyq_year: 'PYQ',
    weak: 'Weak areas',
    adaptive: 'Adaptive',
};

// Loader fallback buckets ("Expert Curated" / "Imported"): not real subjects,
// so they get no subject-test chip (two identical "Expert Curated" chips used
// to be the only ones shown for UPSC CMS).
const LOADER_BUCKET_CODES = new Set(['EXPERT', 'IMPORTED']);
const LOADER_BUCKET_NAMES = new Set(['expert curated', 'imported']);

function subjectChips(subjects: Subject[]): Subject[] {
    const seen = new Set<string>();
    return subjects.filter(s => {
        const name = (s.name || '').trim().toLowerCase();
        const isBucket = LOADER_BUCKET_CODES.has((s.code || '').toUpperCase()) || LOADER_BUCKET_NAMES.has(name);
        if (!name || isBucket || seen.has(name)) return false;
        seen.add(name);
        return true;
    });
}

// One page of /tests/ (paginated `{results, next}`, or a bare array).
function pageOf(data: any): { results: TestItem[]; hasNext: boolean } {
    if (Array.isArray(data)) return { results: data, hasNext: false };
    return { results: Array.isArray(data?.results) ? data.results : [], hasNext: Boolean(data?.next) };
}

// Library: collapse duplicate published rows of the same template, keeping
// the newest. The API returns `subject` / `topic` ids; the old key read
// non-existent `subject_id` / `topic_id`, collapsing every test of one type
// (all subjects, all PYQ years) into a single card.
function dedupeLibrary(tests: TestItem[]): TestItem[] {
    const seen = new Set<string>();
    const unique: TestItem[] = [];
    for (const t of tests) {
        const key = `${t.test_type}:${t.subject ?? 'none'}:${t.topic ?? 'none'}:${t.title}`;
        if (seen.has(key)) continue;
        seen.add(key);
        unique.push(t);
    }
    return unique;
}

function uniqueById(tests: TestItem[]): TestItem[] {
    const seen = new Set<number>();
    return tests.filter(t => (seen.has(t.id) ? false : (seen.add(t.id), true)));
}

export default function TestsPage() {
    const { ready } = useRequireAuth();
    const { user } = useAuth();
    const { show: showPaywall } = usePaywall();
    const router = useRouter();
    // The official library and the student's own generated tests are listed
    // separately (and paginated): in one newest-first list, every "Generate"
    // click pushed the library further down until it fell off page 1.
    const [libraryTests, setLibraryTests] = useState<TestItem[]>([]);
    const [myTests, setMyTests] = useState<TestItem[]>([]);
    const [nextPage, setNextPage] = useState<Record<ListScope, number | null>>({ library: null, mine: null });
    const [loadingMore, setLoadingMore] = useState<ListScope | null>(null);
    const [showAllMine, setShowAllMine] = useState(false);
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [loading, setLoading] = useState(true);
    // The library request failed (as opposed to an empty library).
    const [loadError, setLoadError] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);
    const [generating, setGenerating] = useState(false);
    const [generateError, setGenerateError] = useState<string | null>(null);

    const [examType, setExamType] = useState('cms');

    // Freemium (Task 11): a user is "premium" if they have an active
    // subscription OR are admin/staff — same source of truth as the
    // Sidebar (mirrors backend `accounts.utils.is_premium`).
    const isPremium =
        user?.is_premium === true ||
        user?.subscription_info?.is_active === true ||
        user?.is_admin === true;

    useEffect(() => {
        const syncExam = () => {
            const saved = localStorage.getItem('crack_target_exam');
            if (saved && saved !== examType) setExamType(saved);
        };
        syncExam();
        window.addEventListener('exam_changed', syncExam);
        return () => window.removeEventListener('exam_changed', syncExam);
    }, [examType]);

    const fetchTests = (scope: ListScope, page: number) =>
        testsAPI.list({ exam_type: examType, scope, page: String(page) });

    useEffect(() => {
        if (!ready) return;
        setShowAllMine(false);
        // Subject chips are optional: a failed or throttled subjects call must
        // not throw away the test lists (it used to share one Promise.all, so
        // the page showed "No tests yet" over a full library).
        questionsAPI.getSubjects({ exam_type: examType, page_size: 100 })
            .then(sRes => setSubjects(subjectChips(sRes.data?.results || sRes.data || [])))
            .catch(() => setSubjects([]));
        Promise.allSettled([fetchTests('library', 1), fetchTests('mine', 1)])
            .then(([libRes, mineRes]) => {
                // A failed list is emptied rather than left showing another
                // exam's tests; the library failure gets its own error card.
                const lib = libRes.status === 'fulfilled' ? pageOf(libRes.value.data) : { results: [], hasNext: false };
                const mine = mineRes.status === 'fulfilled' ? pageOf(mineRes.value.data) : { results: [], hasNext: false };
                setLibraryTests(dedupeLibrary(lib.results));
                setMyTests(uniqueById(mine.results));
                setNextPage({ library: lib.hasNext ? 2 : null, mine: mine.hasNext ? 2 : null });
                setLoadError(libRes.status === 'rejected');
            })
            .finally(() => setLoading(false));
    }, [ready, examType, reloadKey]);

    const loadMore = async (scope: ListScope) => {
        const page = nextPage[scope];
        if (!page || loadingMore) return;
        setLoadingMore(scope);
        try {
            const res = await fetchTests(scope, page);
            const { results, hasNext } = pageOf(res.data);
            if (scope === 'library') setLibraryTests(prev => dedupeLibrary([...prev, ...results]));
            else setMyTests(prev => uniqueById([...prev, ...results]));
            setNextPage(prev => ({ ...prev, [scope]: hasNext ? page + 1 : null }));
        } catch {
            /* keep what is shown; the button stays available for a retry */
        } finally {
            setLoadingMore(null);
        }
    };

    const generateTest = async (type: string, subjectId?: number) => {
        setGenerating(true);
        setGenerateError(null);
        try {
            const data: Record<string, string | number> = { test_type: type, num_questions: 20 };
            // Tag the generated test with the active exam track so it shows up
            // in this track's list (the list is filtered by exam_type).
            if (['cms', 'neet_pg', 'ini_cet', 'usmle', 'fmge'].includes(examType)) data.exam_type = examType;
            if (subjectId) data.subject_id = subjectId;
            if (type === 'paper1' || type === 'paper2') data.num_questions = 120;
            if (type === 'daily') data.num_questions = 20;
            const res = await testsAPI.generate(data);
            setMyTests(prev => uniqueById([res.data, ...prev]));
        } catch (err: any) {
            console.error('Failed to generate test:', err);
            setGenerateError(
                err?.response?.data?.error
                || err?.response?.data?.detail
                || 'Could not generate a test right now. Please try again.'
            );
        } finally {
            setGenerating(false);
        }
    };

    const startTest = async (test: TestItem) => {
        // Freemium gate (Task 7/11, updated 2026-08-04): free users can
        // only start tests that are free for THEM — backend defines this
        // as a small practice test (at most 20 questions, counted on the
        // server). Backend enforces the same rule with a 402
        // upgrade_required; we open the modal proactively here so the user
        // sees the same nudge the backend would otherwise deliver via the
        // api.ts interceptor.
        if (!isPremium && !test.is_free_for_current_user) {
            showPaywall('Mock Tests');
            return;
        }
        router.push(`/tests/${test.id}`);
    };

    const renderTestCard = (test: TestItem) => {
        const isFreeForUser = isPremium || test.is_free_for_current_user;
        return (
            <Card key={test.id}>
                <CardContent className="p-5">
                    <div className="flex justify-between items-start mb-3 gap-2">
                        <h3 className="font-semibold text-sm text-foreground min-w-0 wrap-break-word">{test.title}</h3>
                        <div className="flex items-center gap-1.5 shrink-0">
                            {!isFreeForUser && <LockedBadge size="sm" />}
                            <Badge variant="secondary" className="whitespace-nowrap">{TEST_TYPE_LABELS[test.test_type] ?? test.test_type}</Badge>
                        </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs mb-4 text-muted-foreground">
                        <span className="flex items-center gap-1"><Target className="w-3 h-3" /> {test.num_questions} Qs</span>
                        <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {test.time_limit_minutes} min</span>
                        <span className="flex items-center gap-1"><Play className="w-3 h-3" /> {test.attempt_count} attempt{test.attempt_count === 1 ? '' : 's'}</span>
                    </div>
                    <Button variant="neon" onClick={() => startTest(test)} className="w-full" size="sm">
                        {isFreeForUser ? (
                            <>Start Test <ChevronRight className="w-4 h-4 ml-1" /></>
                        ) : (
                            <>Unlock Test <Lock className="w-4 h-4 ml-1" /></>
                        )}
                    </Button>
                </CardContent>
            </Card>
        );
    };

    const testTypes = [
        { type: 'daily', label: 'Daily Quick Test', desc: '20 questions, mixed subjects', icon: Sparkles, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10' },
        { type: 'mixed', label: 'Mixed Practice', desc: 'Questions from all subjects', icon: Target, color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-500/10' },
        { type: 'paper1', label: 'Paper 1 Mock', desc: 'Medicine + Pediatrics (120 Qs)', icon: FileText, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-500/10' },
        { type: 'paper2', label: 'Paper 2 Mock', desc: 'Surgery + OBG + PSM (120 Qs)', icon: FileText, color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-500/10' },
    ];

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                <h1 className="text-2xl font-bold mb-1 flex items-center gap-2 text-foreground">
                    <FileText className="w-6 h-6 text-primary" />
                    Test Center
                </h1>
                <p className="text-sm mb-6 text-muted-foreground">Generate & take practice tests</p>

                {generateError && (
                    <div role="alert" className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                        {generateError}
                    </div>
                )}

                {/* Quick Generate */}
                <div className="mb-8">
                    <h2 className="section-title flex items-center gap-2 mb-4">
                        <Plus className="w-4 h-4 text-emerald-500" />
                        Generate New Test
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        {testTypes.map((tt) => (
                            <button key={tt.type} onClick={() => generateTest(tt.type)}
                                disabled={generating}>
                                <Card className="p-5 text-left group cursor-pointer hover:shadow-md transition-shadow h-full">
                                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${tt.bg}`}>
                                        <tt.icon className={`w-5 h-5 ${tt.color}`} />
                                    </div>
                                    <div className="font-medium text-sm mb-1 text-foreground">{tt.label}</div>
                                    <div className="text-xs text-muted-foreground">{tt.desc}</div>
                                </Card>
                            </button>
                        ))}
                    </div>

                    {/* Subject-wise tests */}
                    {subjects.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                            {subjects.map(s => (
                                <Button key={s.id} variant="outline" size="sm" onClick={() => generateTest('subject', s.id)}
                                    disabled={generating}>
                                    {s.name}
                                </Button>
                            ))}
                        </div>
                    )}
                </div>

                {/* The student's own generated tests */}
                {!loading && myTests.length > 0 && (
                    <div className="mb-8">
                        <h2 className="section-title flex items-center gap-2 mb-4">
                            <Sparkles className="w-4 h-4 text-violet-500" />
                            Your Practice Tests
                        </h2>
                        <div className="grid md:grid-cols-2 gap-4">
                            {(showAllMine ? myTests : myTests.slice(0, PRACTICE_PREVIEW)).map(renderTestCard)}
                        </div>
                        {!showAllMine && (myTests.length > PRACTICE_PREVIEW || nextPage.mine) && (
                            <div className="mt-4 flex justify-center">
                                <Button variant="outline" size="sm" onClick={() => setShowAllMine(true)}>
                                    Show all your practice tests
                                </Button>
                            </div>
                        )}
                        {showAllMine && nextPage.mine && (
                            <div className="mt-4 flex justify-center">
                                <Button variant="outline" size="sm" onClick={() => loadMore('mine')} disabled={loadingMore !== null}>
                                    {loadingMore === 'mine' ? 'Loading…' : 'Load more'}
                                </Button>
                            </div>
                        )}
                    </div>
                )}

                {/* Test List (official library) */}
                <div>
                    <h2 className="section-title flex items-center gap-2 mb-4">
                        <Award className="w-4 h-4 text-amber-500" />
                        Available Tests
                    </h2>
                    {loading ? (
                        <div className="grid md:grid-cols-2 gap-4">
                            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-40 rounded-xl" />)}
                        </div>
                    ) : loadError && libraryTests.length === 0 ? (
                        <Card role="alert" className="p-8 text-center text-muted-foreground">
                            <p className="mb-3">Couldn&apos;t load tests. Check your connection and try again.</p>
                            <Button variant="outline" size="sm" onClick={() => { setLoading(true); setReloadKey(k => k + 1); }}>
                                Retry
                            </Button>
                        </Card>
                    ) : libraryTests.length === 0 ? (
                        <Card className="p-8 text-center text-muted-foreground">
                            {/* Generated tests are listed under "Your Practice Tests", never here. */}
                            No library tests for this exam yet.
                            {myTests.length === 0 && ' Generate a practice test above to get started.'}
                        </Card>
                    ) : (
                        <>
                            <div className="grid md:grid-cols-2 gap-4">
                                {libraryTests.map(renderTestCard)}
                            </div>
                            {nextPage.library && (
                                <div className="mt-4 flex justify-center">
                                    <Button variant="outline" size="sm" onClick={() => loadMore('library')} disabled={loadingMore !== null}>
                                        {loadingMore === 'library' ? 'Loading…' : 'Load more tests'}
                                    </Button>
                                </div>
                            )}
                        </>
                    )}
                </div>
                </div>
            </div>
        </div>
    );
}
