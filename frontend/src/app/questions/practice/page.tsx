/**
 * questions/practice/page.tsx — Immersive fullscreen year-wise practice mode.
 * One-question-at-a-time view without sidebar/header for distraction-free study.
 * Loads questions filtered by year, supports answer selection, AI explanation,
 * and a compact question navigation palette.
 *
 * The list payload carries no correct answer / explanation for students
 * (QuestionListSerializer withholds them), so the answer is revealed from
 * the POST /questions/<id>/attempt/ response, completed from the question
 * detail endpoint when needed. A year can hold hundreds (NEET PG recall:
 * thousands) of rows, so pages are fetched on demand by following `next`.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { Suspense, useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { useExamTrack } from '@/components/ExamTrackProvider';
import { questionsAPI, aiAPI } from '@/lib/api';
import { analytics } from '@/lib/analytics';
import { usePaywall } from '@/lib/paywall/paywallContext';
import { FormattedText, FormattedOptionText, resolveImageTokensForMarkdown } from '@/components/FormattedText';
import { resolveImageTokens, type QuestionImageLike } from '@/lib/imageTokens';
import { cleanOptionText, extractAnalysisFromJson, sanitizeQuestionText, sanitizeOptionText } from '@/lib/textCleanup';
import {
    aiFailureNotice, appendUniqueById, classifyAiFailure, classifyReveal, errorStatus, examLabelFromParam,
    examTypeFromParam, examTypeLabel, hasBlankAnswerKey, mergeRevealWithDetail, readPage, retryTimeSpent,
    revealFromAttempt, revealNeedsDetail, upgradeRequiredFeature, type AnswerReveal,
} from '@/components/question/practiceData';
import {
    BookOpen, ChevronLeft, ChevronRight, Loader2, Brain, Sparkles,
    CheckCircle, X, Bookmark, ArrowLeft, Target, Lightbulb, Flag,
    AlertTriangle, RefreshCw, Lock, Info
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

// Rows per list request. The backend caps page_size; when it ignores the
// parameter it sends its default page instead, which the `next`-link
// paging below handles the same way.
const PRACTICE_PAGE_SIZE = 100;
// Fetch the next page once the student is this close to the loaded end.
const PREFETCH_MARGIN = 5;

/** Per-question answer state after a pick. */
type RevealState =
    | { status: 'loading' }
    | { status: 'ready'; data: AnswerReveal; saveFailed: boolean; explanationLocked: boolean }
    | { status: 'locked' }
    // The server answered but the question has no answer key: nothing to
    // retry (a retry would re-post the attempt and record another mistake).
    | { status: 'no-key'; explanation: string; saveFailed: boolean }
    // `timeSpent` is what a Retry re-sends (0 when the first POST may have landed).
    | { status: 'error'; picked: string; timeSpent: number };

export default function PracticePage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="text-center space-y-3">
                    <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
                    <p className="text-sm text-muted-foreground font-medium">Loading Practice Session...</p>
                </div>
            </div>
        }>
            <PracticeContent />
        </Suspense>
    );
}

function PracticeContent() {
    const { ready } = useRequireAuth();
    const { activeTrack } = useExamTrack();
    const { show: showPaywall } = usePaywall();
    const router = useRouter();
    const searchParams = useSearchParams();
    const year = searchParams.get('year');
    // `?exam=` (or `?exam_type=`) is matched case-insensitively and may be a
    // slug (neet-pg), an enum value (neet_pg / NEET_PG) or a label
    // (NEET PG). Unknown values fall back to the student's track, then CMS.
    const rawExam = searchParams.get('exam') || searchParams.get('exam_type');
    const resolvedExamType = examTypeFromParam(rawExam) || examTypeFromParam(activeTrack) || 'cms';
    // Human-readable label for the top-bar badge so NEET PG doesn't show
    // as a slug.
    const currentExamLabel = examTypeLabel(resolvedExamType);

    // Where "Exit Practice" / "Back" lead: the bank this session came from.
    const bankHref = (() => {
        const yearQuery = year ? `year=${encodeURIComponent(year)}` : '';
        if (resolvedExamType === 'neet_pg') return `/questions/neet-pg/practice${yearQuery ? `?${yearQuery}` : ''}`;
        if (resolvedExamType === 'ini_cet') return `/questions/inicet/practice${yearQuery ? `?${yearQuery}` : ''}`;
        const query = [
            resolvedExamType !== 'cms' ? `exam=${encodeURIComponent(resolvedExamType)}` : '',
            yearQuery,
        ].filter(Boolean).join('&');
        return `/questions${query ? `?${query}` : ''}`;
    })();

    const [questions, setQuestions] = useState<any[]>([]);
    const [totalCount, setTotalCount] = useState(0);
    const [nextPage, setNextPage] = useState<number | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
    const [loadMoreFailed, setLoadMoreFailed] = useState(false);
    const [loading, setLoading] = useState(true);
    const [currentIdx, setCurrentIdx] = useState(0);
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const [reveals, setReveals] = useState<Record<number, RevealState>>({});
    const [showAnswer, setShowAnswer] = useState(false);
    const [aiExplanation, setAiExplanation] = useState<any>(null);
    const [aiLoading, setAiLoading] = useState(false);
    // Short notice for a failed AI request (503 ai_unavailable, rate limit, …).
    const [aiError, setAiError] = useState<{ title: string; message: string } | null>(null);
    const [tokenError, setTokenError] = useState(false);
    const [showPalette, setShowPalette] = useState(false);
    // Bookmark state the student toggled this session (server value otherwise).
    const [bookmarkState, setBookmarkState] = useState<Record<number, boolean>>({});
    const [loadError, setLoadError] = useState<string | null>(null);

    // Used to cancel in-flight AI explanation requests when the student
    // navigates to a different question before the response arrives.
    // See `fetchAiExplanation` below.
    const aiAbortRef = useRef<(() => void) | null>(null);
    // Mirrors `currentQ.id` so async resolvers can check whether the active
    // question has changed since they fired (race-condition guard).
    const currentQIdRef = useRef<number | null>(null);
    // Bumped whenever the year / exam changes so page responses from the
    // previous session are discarded.
    const loadSeq = useRef(0);

    const [flagOpen, setFlagOpen] = useState(false);
    const [flagCategory, setFlagCategory] = useState('wrong_answer');
    const [flagComment, setFlagComment] = useState('');
    const [flagSubmitting, setFlagSubmitting] = useState(false);
    const [flagSuccess, setFlagSuccess] = useState(false);
    const [flagError, setFlagError] = useState<string | null>(null);

    useEffect(() => {
        if (!ready) return;
        // replace, not push: a history entry for this redirect made Back
        // return here and immediately bounce to the bank again.
        if (!year) { router.replace(bankHref); return; }
        const seq = ++loadSeq.current;
        setLoading(true);
        setLoadError(null);
        setQuestions([]);
        setTotalCount(0);
        setNextPage(null);
        setLoadMoreFailed(false);
        // A loadMore still in flight belongs to the old session; its
        // seq-guarded finally won't clear this.
        setLoadingMore(false);
        setCurrentIdx(0);
        setAnswers({});
        setReveals({});
        setShowAnswer(false);
        questionsAPI.list({ year, exam_type: resolvedExamType, page: 1, page_size: PRACTICE_PAGE_SIZE }).then(res => {
            if (seq !== loadSeq.current) return;
            const page = readPage<any>(res.data);
            setQuestions(page.items);
            setTotalCount(page.count ?? page.items.length);
            setNextPage(page.hasNext ? 2 : null);
        }).catch(() => {
            if (seq !== loadSeq.current) return;
            setLoadError('Failed to load questions. Check your connection and try again.');
            setQuestions([]);
        }).finally(() => {
            if (seq === loadSeq.current) setLoading(false);
        });
        // bankHref is derived from year / exam, which are already deps.
    }, [ready, router, year, resolvedExamType]);

    // Fetch the next page of this year's questions (follows the API's
    // `next` link one page at a time).
    const loadMore = useCallback(() => {
        if (nextPage === null || loadingMore || !year) return;
        const seq = loadSeq.current;
        const pageNum = nextPage;
        setLoadingMore(true);
        setLoadMoreFailed(false);
        questionsAPI.list({ year, exam_type: resolvedExamType, page: pageNum, page_size: PRACTICE_PAGE_SIZE }).then(res => {
            if (seq !== loadSeq.current) return;
            const page = readPage<any>(res.data);
            setQuestions(prev => appendUniqueById(prev, page.items));
            if (page.count !== null) setTotalCount(page.count);
            setNextPage(page.hasNext ? pageNum + 1 : null);
        }).catch(err => {
            if (seq !== loadSeq.current) return;
            // 404 = the page no longer exists (rows were removed): that's the end.
            if (errorStatus(err) === 404) setNextPage(null);
            else setLoadMoreFailed(true);
        }).finally(() => {
            if (seq === loadSeq.current) setLoadingMore(false);
        });
    }, [nextPage, loadingMore, year, resolvedExamType]);

    // Keep the next page ready before the student reaches the loaded end.
    useEffect(() => {
        if (nextPage === null || loadingMore || loadMoreFailed) return;
        if (currentIdx >= questions.length - PREFETCH_MARGIN) loadMore();
    }, [currentIdx, questions.length, nextPage, loadingMore, loadMoreFailed, loadMore]);

    // Detect slug-level fallbacks: medical-officer maps to cms because that
    // track isn't yet populated in our DB. Surface a warning so students
    // know they're seeing a different exam's questions.
    const slug = rawExam;
    const isSlugFallback = examLabelFromParam(rawExam) === 'Medical Officer';
    const examType = resolvedExamType;

    const currentQ = questions[currentIdx];
    const totalQ = Math.max(totalCount, questions.length);
    const answeredCount = Object.keys(answers).length;
    // Keep the ref in sync with the actively-shown question so async
    // resolvers can detect that the user has moved on.
    useEffect(() => {
        currentQIdRef.current = currentQ?.id ?? null;
        // Whenever the active question changes, any in-flight AI request is
        // now stale — cancel it so its `.then` / `.catch` bails out and
        // doesn't leak state across questions.
        return () => {
            if (aiAbortRef.current) {
                aiAbortRef.current();
                aiAbortRef.current = null;
            }
        };
    }, [currentQ?.id]);
    // Resolve `[[img:N]]` tokens in the question text against the question's
    // image list so public practice pages render real `<img>` tags instead of
    // the raw token. Cached per `(id, imageCount)` for cheap re-renders.
    //
    // Bug fix 2026-08-01: prefer the backend-filtered `stem_images`
    // (excludes `role='explanation'`) so admin-uploaded explanation
    // figures don't render inline next to the stem before the student
    // attempts the question. Fall back to filtering `images` ourselves
    // for legacy rows that pre-date the `stem_images` field. The
    // explanation / mnemonic panels below still use the full `images`
    // list (rendered only after `showAnswer`) so `[[img:N]]` tokens
    // inside explanation text resolve correctly.
    const qId = currentQ?.id ?? null;
    const qText = currentQ?.question_text ?? '';
    const qImages = (() => {
        const stem = (currentQ as any)?.stem_images;
        if (Array.isArray(stem)) return stem;
        const all = currentQ?.images;
        return Array.isArray(all) ? all.filter((img: any) => img?.role !== 'explanation') : [];
    })();
    const resolvedQuestionText = useMemo(() => {
        if (!currentQ) return '';
        const cleaned = sanitizeQuestionText(qText);
        const imgs: QuestionImageLike[] = (qImages as QuestionImageLike[] | undefined) ?? [];
        return resolveImageTokens(
            cleaned,
            imgs,
            `q${currentQ.id}:v${imgs.length}`,
        );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [qId, qText, qImages, currentQ]);

    // Reset the per-question timer whenever a new question is shown.
    const questionShownAt = useRef<number>(Date.now());
    useEffect(() => {
        questionShownAt.current = Date.now();
    }, [currentQ?.id]);

    // Grade the pick on the server and reveal the real answer. The attempt
    // response carries `is_correct` + `correct_answer` (and, for entitled
    // users, the explanation); anything missing comes from the detail
    // endpoint. Free-plan users hitting a premium question get the paywall.
    const revealAnswer = async (questionId: number, opt: string, timeSpent: number) => {
        setReveals(prev => ({ ...prev, [questionId]: { status: 'loading' } }));
        let reveal: AnswerReveal = { correctAnswer: '', isCorrect: null };
        let attemptOk = false;
        // A 2xx response said the question has no answer key at all.
        let serverHasNoKey = false;
        let retryTime = timeSpent;
        try {
            // Log attempt (time spent feeds study-time tracking)
            const res = await questionsAPI.attempt(questionId, {
                selected_answer: opt,
                time_spent_seconds: timeSpent,
            });
            reveal = revealFromAttempt(opt, res.data);
            attemptOk = true;
            serverHasNoKey = hasBlankAnswerKey(res.data);
        } catch (err) {
            const feature = upgradeRequiredFeature(err);
            if (feature) {
                // The server refused to grade this question on the free
                // plan: undo the pick so it can be answered after upgrading.
                setAnswers(prev => {
                    const next = { ...prev };
                    delete next[questionId];
                    return next;
                });
                setReveals(prev => ({ ...prev, [questionId]: { status: 'locked' } }));
                if (currentQIdRef.current === questionId) setShowAnswer(false);
                showPaywall(feature);
                return;
            }
            // A lost response may still have been recorded: don't send the
            // same time again on Retry.
            retryTime = retryTimeSpent(err, timeSpent);
        }

        let gated = false;
        if (revealNeedsDetail(reveal)) {
            try {
                const res = await questionsAPI.get(questionId);
                reveal = mergeRevealWithDetail(opt, reveal, res.data);
                // A redacted detail payload (answer fields nulled) is a paywall, not an error.
                if (res.data?.answer_locked === true) gated = true;
                else if (hasBlankAnswerKey(res.data)) serverHasNoKey = true;
            } catch (err) {
                const status = errorStatus(err);
                gated = !!upgradeRequiredFeature(err) || status === 402 || status === 403 || status === 404;
            }
        }

        let next: RevealState;
        switch (classifyReveal({ reveal, attemptOk, serverHasNoKey, gated })) {
            case 'ready':
                next = {
                    status: 'ready',
                    data: reveal,
                    saveFailed: !attemptOk,
                    explanationLocked: gated && !reveal.explanation,
                };
                break;
            case 'locked':
                next = { status: 'locked' };
                break;
            case 'no-key':
                next = { status: 'no-key', explanation: reveal.explanation || '', saveFailed: !attemptOk };
                break;
            default:
                next = { status: 'error', picked: opt, timeSpent: retryTime };
        }
        setReveals(prev => ({ ...prev, [questionId]: next }));
    };

    const handleSelectOption = (opt: string) => {
        if (!currentQ || answers[currentQ.id]) return;
        const questionId = currentQ.id;
        setAnswers(prev => ({ ...prev, [questionId]: opt }));
        setShowAnswer(true);
        void revealAnswer(
            questionId,
            opt,
            Math.max(0, Math.round((Date.now() - questionShownAt.current) / 1000)),
        );
    };

    const goToQuestion = useCallback((idx: number) => {
        if (idx < 0 || idx >= questions.length) return;
        setCurrentIdx(idx);
        setShowAnswer(!!answers[questions[idx]?.id]);
        setAiExplanation(null);
        setAiLoading(false);
        setAiError(null);
        setTokenError(false);
        setShowPalette(false);
        // The report form belongs to the question it was opened on.
        setFlagOpen(false);
    }, [answers, questions]);

    const handleNext = () => goToQuestion(currentIdx + 1);
    const handlePrev = () => goToQuestion(currentIdx - 1);

    const currentReveal = currentQ ? reveals[currentQ.id] : undefined;
    const revealData = currentReveal?.status === 'ready' ? currentReveal.data : undefined;

    const fetchAiExplanation = () => {
        if (!currentQ || aiLoading || !revealData) return;
        setAiLoading(true);
        setAiExplanation(null);
        setTokenError(false);
        setAiError(null);
        // Capture the question we're explaining so a quick navigation
        // doesn't let an older request resolve into the newer question's UI
        // (race condition that previously leaked state across questions).
        const reqQuestionId = currentQ.id;
        let cancelled = false;
        aiAbortRef.current = () => { cancelled = true; };
        // `question_id` lets the server use the stored question (its own
        // answer key, stored explanation, cached analysis) and check the
        // student's entitlement; the text fields are a fallback only.
        const payload: Parameters<typeof aiAPI.explainAfterAnswer>[0] = {
            question_id: currentQ.id,
            question_text: sanitizeQuestionText(currentQ.question_text),
            options: {
                A: sanitizeOptionText(currentQ.option_a || currentQ.option_A || ''),
                B: sanitizeOptionText(currentQ.option_b || currentQ.option_B || ''),
                C: sanitizeOptionText(currentQ.option_c || currentQ.option_C || ''),
                D: sanitizeOptionText(currentQ.option_d || currentQ.option_D || ''),
            },
            correct_answer: revealData.correctAnswer,
            selected_answer: answers[currentQ.id] || '',
            subject: currentQ.subject_name || '',
            topic: currentQ.topic_name || '',
        };
        aiAPI.explainAfterAnswer(payload).then(res => {
            if (cancelled || reqQuestionId !== currentQIdRef.current) return;
            setAiExplanation(res.data);
            setAiLoading(false);
        }).catch(err => {
            if (cancelled || reqQuestionId !== currentQIdRef.current) return;
            const failure = classifyAiFailure(err);
            if (failure === 'upgrade') {
                // Premium question on the free plan: the paywall, not an AI
                // outage (the api.ts interceptor opens it too; showing it
                // twice is a no-op).
                showPaywall(upgradeRequiredFeature(err) || 'PYQ answers');
            } else if (failure === 'tokens') {
                setTokenError(true);
            } else {
                // 503 ai_unavailable → "AI is unavailable right now" (never
                // charged); a throttle 429 is not an empty token wallet.
                setAiError(aiFailureNotice(failure, err));
            }
            setAiLoading(false);
        });
    };

    const isBookmarked = (q: any) => bookmarkState[q.id] ?? !!q.is_bookmarked;

    const handleBookmark = () => {
        if (!currentQ) return;
        const questionId = currentQ.id;
        const wasBookmarked = isBookmarked(currentQ);
        questionsAPI.bookmark(questionId).then(res => {
            // The endpoint toggles and reports the new state.
            const on = typeof res.data?.bookmarked === 'boolean' ? res.data.bookmarked : !wasBookmarked;
            setBookmarkState(prev => ({ ...prev, [questionId]: on }));
        }).catch(err => console.error(err));
    };

    const handleFlagSubmit = () => {
        if (!currentQ || !flagComment.trim()) return;
        setFlagSubmitting(true);
        setFlagError(null);
        questionsAPI.submitFeedback({
            question: currentQ.id,
            category: flagCategory,
            comment: flagComment.trim(),
        }).then(() => {
            setFlagSuccess(true);
            setTimeout(() => { setFlagOpen(false); setFlagSuccess(false); setFlagComment(''); setFlagError(null); }, 2000);
        }).catch(() => {
            setFlagError('Unable to submit feedback right now. Please try again.');
        }).finally(() => {
            setFlagSubmitting(false);
        });
    };

    // Keyboard shortcuts. Re-binds whenever the active question or the
    // answers map changes so the closure always sees the up-to-date
    // `currentQ` / `answers` (avoids stale-closure bugs that previously
    // let the wrong option get recorded after a "Next" press).
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
            if (e.key === 'ArrowRight' || e.key === 'n') handleNext();
            if (e.key === 'ArrowLeft' || e.key === 'p') handlePrev();
            if (['a', 'b', 'c', 'd'].includes(e.key.toLowerCase()) && !answers[currentQ?.id]) {
                handleSelectOption(e.key.toUpperCase());
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [handleNext, handlePrev, handleSelectOption, answers, currentQ?.id]);

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="text-center space-y-3">
                    <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
                    <p className="text-sm text-muted-foreground font-medium">Loading {year} PYQs...</p>
                </div>
            </div>
        );
    }

    if (questions.length === 0 && loadError) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <Card className="max-w-md p-8 text-center space-y-4">
                    <AlertTriangle className="w-12 h-12 text-destructive mx-auto" />
                    <h2 className="text-lg font-bold">Failed to Load</h2>
                    <p className="text-sm text-muted-foreground">{loadError}</p>
                    <div className="flex gap-3 justify-center">
                        <Button onClick={() => window.location.reload()}>
                            <RefreshCw className="w-4 h-4 mr-2" /> Retry
                        </Button>
                        <Button variant="outline" onClick={() => router.push(bankHref)}>
                            <ArrowLeft className="w-4 h-4 mr-2" /> Back
                        </Button>
                    </div>
                </Card>
            </div>
        );
    }

    if (questions.length === 0) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <Card className="max-w-md p-8 text-center space-y-4">
                    <BookOpen className="w-12 h-12 text-muted-foreground mx-auto" />
                    <h2 className="text-lg font-bold">No Questions Found</h2>
                    <p className="text-sm text-muted-foreground">No {currentExamLabel} questions available for year {year}.</p>
                    <Button onClick={() => router.push(bankHref)}>
                        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Question Bank
                    </Button>
                </Card>
            </div>
        );
    }

    const selectedAnswer = answers[currentQ?.id] || null;
    // The colours / verdict only appear once the server has graded the pick.
    const answerShown = showAnswer && !!revealData;
    const correctLetter = revealData?.correctAnswer || '';
    const isCorrect = revealData ? (revealData.isCorrect ?? selectedAnswer === correctLetter) : false;
    const explanationImages = (revealData?.images ?? currentQ.images) as any;
    const atLoadedEnd = currentIdx >= questions.length - 1;

    // 🚩 Flag Wrong Answer — under the answer analysis, and on questions
    // without an answer key (so the missing key can be reported).
    const flagSection = (
        <>
            <div className="flex justify-end mt-4">
                <button onClick={() => { setFlagOpen(!flagOpen); setFlagSuccess(false); setFlagError(null); }}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                    <Flag className="w-3.5 h-3.5" /> Flag Issue
                </button>
            </div>
            {flagOpen && (
                <div className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl mt-2 space-y-3 animate-fadeInUp">
                    <h5 className="text-sm font-bold flex items-center gap-2 text-red-500">
                        <Flag className="w-4 h-4" /> Report an Issue
                    </h5>
                    {flagSuccess ? (
                        <p className="text-sm text-emerald-500 font-medium">✓ Thanks! Your feedback has been submitted. You'll earn 2 tokens if accepted.</p>
                    ) : (
                        <>
                            {flagError && <p className="text-sm text-red-500">{flagError}</p>}
                            <select className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                                value={flagCategory} onChange={e => setFlagCategory(e.target.value)}>
                                <option value="wrong_answer">Wrong Answer</option>
                                <option value="discrepancy">Discrepancy in Options</option>
                                <option value="out_of_syllabus">Out of Syllabus</option>
                                <option value="typo">Typo/Formatting Issue</option>
                                <option value="explanation_needed">Better Explanation Needed</option>
                                <option value="other">Other</option>
                            </select>
                            <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-15 resize-none"
                                placeholder="Describe the issue (e.g., correct answer should be B because...)"
                                value={flagComment} onChange={e => setFlagComment(e.target.value)}
                                maxLength={500} />
                            <div className="text-right text-[10px] text-muted-foreground">{flagComment.length}/500</div>
                            <div className="flex gap-2">
                                <Button size="sm" onClick={handleFlagSubmit} disabled={flagSubmitting || !flagComment.trim()}>
                                    {flagSubmitting ? 'Submitting...' : 'Submit'}
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => { setFlagOpen(false); setFlagError(null); }}>Cancel</Button>
                            </div>
                        </>
                    )}
                </div>
            )}
        </>
    );

    return (
        <div className="min-h-screen bg-background flex flex-col">
            {isSlugFallback && (
                <Card className="m-4 border-amber-300 bg-amber-50 dark:bg-amber-900/20">
                    <CardContent className="py-3 text-sm text-amber-900 dark:text-amber-100">
                        Practice session for <strong>{slug}</strong> isn't yet populated in our bank.
                        Showing <strong>{examType?.toUpperCase()}</strong> questions as a fallback.
                    </CardContent>
                </Card>
            )}
            {/* Top Bar */}
            <div className="sticky top-0 z-50 bg-card/95 backdrop-blur-md border-b border-border/60 px-4 py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button onClick={() => router.push(bankHref)} className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
                        <ArrowLeft className="w-4 h-4" /> Exit Practice
                    </button>
                    <div className="h-5 w-px bg-border/60" />
                    <Badge variant="secondary" className="text-xs font-bold">📖 {currentExamLabel} {year} PYQ Practice</Badge>
                </div>

                <div className="flex items-center gap-4">
                    <div className="hidden md:flex items-center gap-2 text-xs">
                        <span className="text-muted-foreground font-medium">Progress:</span>
                        <span className="font-bold text-primary">{answeredCount}/{totalQ}</span>
                        <Progress value={totalQ ? (answeredCount / totalQ) * 100 : 0} className="h-1.5 w-24" />
                    </div>
                    <button
                        onClick={() => setShowPalette(!showPalette)}
                        className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border border-border/80 hover:bg-muted/50 transition-colors cursor-pointer"
                    >
                        <Target className="w-3.5 h-3.5" />
                        Q {currentIdx + 1}/{totalQ}
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex relative">
                {/* Question Area */}
                <div className="flex-1 overflow-y-auto p-4 md:p-8 lg:px-16 xl:px-24">
                    <div className="max-w-3xl mx-auto space-y-6">
                        {/* Question Number + Meta */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-extrabold text-primary bg-primary/10 px-2.5 py-1 rounded-lg">Q{currentIdx + 1}</span>
                                <Badge variant="secondary" className="text-xs">{currentQ.subject_name}</Badge>
                                {currentQ.topic_name && <Badge variant="outline" className="text-xs">{currentQ.topic_name}</Badge>}
                                {currentQ.difficulty && <Badge variant="outline" className="text-xs capitalize">{currentQ.difficulty}</Badge>}
                            </div>
                            <div className="flex items-center gap-2">
                                <button onClick={handleBookmark} className="p-1.5 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer" title="Bookmark">
                                    <Bookmark className={`w-4 h-4 ${isBookmarked(currentQ) ? 'text-amber-500 fill-amber-500' : 'text-muted-foreground'}`} />
                                </button>
                            </div>
                        </div>

                        {/* Question Text */}
                        <div className="glass-card rounded-2xl border border-primary/30 shadow-lg p-6">
                            <div className="text-base font-medium leading-relaxed">
                                <FormattedText text={resolvedQuestionText} />
                            </div>
                        </div>

                        {/* Options */}
                        <div className="space-y-3">
                            {['A', 'B', 'C', 'D'].map(opt => {
                                const key = `option_${opt.toLowerCase()}`;
                                const rawOption = currentQ[key] || currentQ[`option_${opt}`];
                                const optionText = sanitizeOptionText(rawOption);
                                if (!optionText) return null;
                                const isCorrectOpt = correctLetter === opt;
                                const isSelected = selectedAnswer === opt;
                                const isWrong = isSelected && !isCorrectOpt && answerShown;

                                return (
                                    <button
                                        key={opt}
                                        className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all text-left cursor-pointer ${
                                            answerShown
                                                ? (isCorrectOpt ? 'border-emerald-500 bg-emerald-500/5 shadow-sm' : isWrong ? 'border-red-500/50 bg-red-500/5 opacity-80' : 'border-border/60 bg-muted/20 opacity-70')
                                                : (isSelected ? 'border-primary bg-primary/5 ring-2 ring-primary/40' : 'border-border/70 hover:border-primary/40 hover:bg-muted/30')
                                        }`}
                                        onClick={() => handleSelectOption(opt)}
                                    >
                                        <div className={`w-9 h-9 shrink-0 flex items-center justify-center rounded-full text-sm font-bold transition-colors ${
                                            answerShown
                                                ? (isCorrectOpt ? 'bg-emerald-500 text-white' : isWrong ? 'bg-red-500 text-white' : 'bg-muted text-muted-foreground')
                                                : (isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')
                                        }`}>{opt}</div>
                                        <span className="flex-1 text-sm font-medium">
                                            <FormattedOptionText
                                                text={cleanOptionText(String(optionText))}
                                                images={qImages}
                                            />
                                        </span>
                                        {answerShown && isCorrectOpt && <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 shrink-0">✓ Correct</span>}
                                        {isWrong && <span className="text-xs font-bold text-red-600 dark:text-red-400 shrink-0">✗ Wrong</span>}
                                    </button>
                                );
                            })}
                        </div>

                        {!showAnswer && !selectedAnswer && currentReveal?.status !== 'locked' && (
                            <p className="text-xs text-center py-2 text-muted-foreground">👆 Select an option to reveal the answer • Use A/B/C/D keys for quick selection</p>
                        )}

                        {/* Premium question on the free plan */}
                        {currentReveal?.status === 'locked' && (
                            <Card className="border-amber-300 bg-amber-50/80 dark:bg-amber-950/30 dark:border-amber-800/60">
                                <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                                    <Lock className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
                                    <p className="flex-1 text-sm text-amber-900 dark:text-amber-200">
                                        This is a premium question. Upgrade to see its answer and explanation.
                                    </p>
                                    <Button size="sm" onClick={() => showPaywall('PYQ answers')}>Upgrade</Button>
                                </CardContent>
                            </Card>
                        )}

                        {/* Waiting for the server to grade the pick */}
                        {showAnswer && currentReveal?.status === 'loading' && (
                            <div className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground">
                                <Loader2 className="w-4 h-4 animate-spin" /> Checking your answer…
                            </div>
                        )}

                        {showAnswer && currentReveal?.status === 'error' && (
                            <Card className="border-red-200 bg-red-50 dark:bg-red-950/20 dark:border-red-900/40">
                                <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                                    <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0" />
                                    <p className="flex-1 text-sm text-red-700 dark:text-red-300">
                                        Couldn't check your answer. Check your connection and try again.
                                    </p>
                                    <Button size="sm" variant="outline" onClick={() => {
                                        if (currentReveal.status !== 'error') return;
                                        void revealAnswer(currentQ.id, currentReveal.picked, currentReveal.timeSpent);
                                    }}>
                                        <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Retry
                                    </Button>
                                </CardContent>
                            </Card>
                        )}

                        {/* Graded by the server, but there is no answer key to show. */}
                        {showAnswer && currentReveal?.status === 'no-key' && (
                            <div className="space-y-3 animate-fadeInUp">
                                <Card className="border-border bg-muted/40">
                                    <CardContent className="p-4 space-y-2">
                                        <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
                                            <Info className="w-4 h-4 text-muted-foreground shrink-0" />
                                            Answer key not available for this question.
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            Your pick can&apos;t be graded until the key is added. Use “Flag Issue” to let us know.
                                        </p>
                                        {currentReveal.explanation && (
                                            <div className="rounded-lg bg-card p-3 text-sm leading-relaxed text-foreground prose prose-sm max-w-none">
                                                <FormattedText text={resolveImageTokensForMarkdown(extractAnalysisFromJson(String(currentReveal.explanation)), explanationImages)} />
                                            </div>
                                        )}
                                        {currentReveal.saveFailed && (
                                            <p className="text-xs text-amber-700 dark:text-amber-300">
                                                Your answer couldn&apos;t be saved to your progress — check your connection.
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>
                                {flagSection}
                            </div>
                        )}

                        {/* Answer Analysis */}
                        {answerShown && revealData && (
                            <div className="space-y-4 animate-fadeInUp">
                                {/* Result Banner — light/dark readable palette.
                                    The previous emerald/red palette washed out the
                                    explanation body in light mode. Now uses stronger
                                    border + opaque inner panel so body text inherits
                                    foreground contrast. */}
                                <Card className={isCorrect
                                    ? 'border-emerald-300 bg-emerald-50/80 dark:bg-emerald-950/30 dark:border-emerald-800/60'
                                    : 'border-red-300 bg-red-50/80 dark:bg-red-950/30 dark:border-red-800/60'}
                                >
                                    <CardContent className="p-4 space-y-2">
                                        <h4 className={`text-sm font-bold flex items-center gap-2 ${isCorrect ? 'text-emerald-800 dark:text-emerald-300' : 'text-red-800 dark:text-red-300'}`}>
                                            <CheckCircle className="w-4 h-4" />
                                            {isCorrect ? 'Correct!' : `Incorrect — Answer: ${correctLetter}`}
                                        </h4>
                                        {revealData.explanation && (
                                            <div className="rounded-lg bg-white/80 dark:bg-slate-900/40 p-3 text-sm leading-relaxed text-foreground prose prose-sm max-w-none">
                                                <FormattedText text={resolveImageTokensForMarkdown(extractAnalysisFromJson(String(revealData.explanation ?? '')), explanationImages)} />
                                            </div>
                                        )}
                                        {currentReveal?.status === 'ready' && currentReveal.explanationLocked && (
                                            <p className="text-xs text-muted-foreground">
                                                <button type="button" onClick={() => showPaywall('PYQ answers')} className="font-semibold text-primary hover:underline">
                                                    Upgrade
                                                </button>{' '}
                                                to read the full explanation.
                                            </p>
                                        )}
                                        {currentReveal?.status === 'ready' && currentReveal.saveFailed && (
                                            <p className="text-xs text-amber-700 dark:text-amber-300">
                                                Your answer couldn't be saved to your progress — check your connection.
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Mnemonic */}
                                {revealData.mnemonic && !aiExplanation?.mnemonic && (
                                    <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50/50 dark:bg-amber-950/10 dark:border-amber-900/30">
                                        <Lightbulb className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                                        <div>
                                            <h5 className="text-sm font-bold text-amber-700 dark:text-amber-400">🧠 Memory Trick</h5>
                                            <p className="text-sm leading-relaxed mt-1"><FormattedText text={resolveImageTokensForMarkdown(String(revealData.mnemonic ?? ''), explanationImages)} /></p>
                                        </div>
                                    </div>
                                )}

                                {flagSection}

                                {/* Generate AI Analysis button */}
                                {!aiExplanation && !aiLoading && !tokenError && (
                                    <button onClick={() => {
                                        // Consent-gated analytics (the direct window.gtag
                                        // call fired before consent was given).
                                        analytics.aiExplanationOpen(currentQ.id, String(currentQ.subject_name || ''));
                                        // The GA4 "ai_explain_request" conversion.
                                        analytics.aiExplainRequest(currentQ.id, resolvedExamType, 'practice');
                                        fetchAiExplanation();
                                    }}
                                        className="w-full rounded-2xl border border-blue-200 bg-blue-50/50 dark:bg-blue-900/10 dark:border-blue-800/50 p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:bg-blue-50 dark:hover:bg-blue-900/20">
                                        <Brain className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                                        <div className="text-left">
                                            <span className="text-sm font-bold block text-blue-700 dark:text-blue-300">Generate AI Analysis</span>
                                            <span className="text-xs text-muted-foreground">Mnemonics, explanations, exam tips & textbook references</span>
                                        </div>
                                    </button>
                                )}

                                {/* AI Loading */}
                                {aiLoading && (
                                    <div className="flex items-center justify-center gap-3 p-6 rounded-xl border border-blue-200 bg-blue-50/30 dark:bg-blue-900/10">
                                        <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                                        <span className="text-sm font-medium text-blue-600 dark:text-blue-400">Analyzing question with AI...</span>
                                    </div>
                                )}

                                {/* Token Error */}
                                {tokenError && (
                                    <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20">
                                        <CardContent className="p-4 text-center">
                                            <p className="text-sm font-bold text-amber-700 dark:text-amber-400">Daily AI tokens exhausted</p>
                                            <p className="text-xs text-muted-foreground mt-1">Get more tokens or wait for daily refill.</p>
                                        </CardContent>
                                    </Card>
                                )}

                                {/* AI Error (the Generate button above stays as the retry) */}
                                {aiError && (
                                    <Card role="status" className="border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/40">
                                        <CardContent className="p-3 text-center">
                                            <p className="text-sm font-bold text-amber-800 dark:text-amber-300">{aiError.title}</p>
                                            <p className="text-xs mt-1 text-muted-foreground">{aiError.message}</p>
                                        </CardContent>
                                    </Card>
                                )}

                                {/* AI Explanation Panels */}
                                {aiExplanation && (
                                    <div className="space-y-3 animate-fadeInUp">
                                        {aiExplanation.why_correct && (
                                            <Card className="border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5 mb-2"><CheckCircle className="w-3.5 h-3.5" /> Why Correct</h5>
                                                <FormattedText text={String(aiExplanation.why_correct)} />
                                            </CardContent></Card>
                                        )}
                                        {aiExplanation.mnemonic && (
                                            <Card className="border-amber-200 bg-amber-50/50 dark:bg-amber-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-amber-700 dark:text-amber-400 flex items-center gap-1.5 mb-2"><Lightbulb className="w-3.5 h-3.5" /> AI Mnemonic</h5>
                                                <FormattedText text={String(aiExplanation.mnemonic)} />
                                            </CardContent></Card>
                                        )}
                                        {aiExplanation.textbook_reference && (
                                            <Card className="border-blue-200 bg-blue-50/50 dark:bg-blue-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-blue-700 dark:text-blue-400 flex items-center gap-1.5 mb-2"><Bookmark className="w-3.5 h-3.5" /> Textbook Reference</h5>
                                                <div className="text-sm leading-relaxed">
                                                    {typeof aiExplanation.textbook_reference === 'string'
                                                        ? <FormattedText text={String(aiExplanation.textbook_reference)} />
                                                        : (
                                                            <div className="space-y-0.5">
                                                                {aiExplanation.textbook_reference.book && <p className="font-semibold">{aiExplanation.textbook_reference.book}</p>}
                                                                {aiExplanation.textbook_reference.chapter && <p className="text-muted-foreground">Ch: {aiExplanation.textbook_reference.chapter}</p>}
                                                                {aiExplanation.textbook_reference.page && <p className="text-muted-foreground">Pg: {aiExplanation.textbook_reference.page}</p>}
                                                            </div>
                                                        )
                                                    }
                                                </div>
                                            </CardContent></Card>
                                        )}
                                        {aiExplanation.exam_tip && (
                                            <Card className="border-purple-200 bg-purple-50/50 dark:bg-purple-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-purple-700 dark:text-purple-400 flex items-center gap-1.5 mb-2"><Sparkles className="w-3.5 h-3.5" /> Exam Tip</h5>
                                                <FormattedText text={String(aiExplanation.exam_tip)} />
                                            </CardContent></Card>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Navigation */}
                        <div className="flex items-center justify-between pt-4 pb-8 border-t border-border/40">
                            <Button variant="outline" size="sm" onClick={handlePrev} disabled={currentIdx <= 0}>
                                <ChevronLeft className="w-4 h-4 mr-1" /> Previous
                            </Button>
                            <span className="text-xs text-muted-foreground font-medium">
                                Question {currentIdx + 1} of {totalQ}
                            </span>
                            {atLoadedEnd && nextPage !== null && loadMoreFailed ? (
                                <Button variant="outline" size="sm" onClick={loadMore}>
                                    <RefreshCw className="w-4 h-4 mr-1" /> Load more
                                </Button>
                            ) : (
                                <Button variant="outline" size="sm" onClick={handleNext} disabled={atLoadedEnd}>
                                    {atLoadedEnd && loadingMore
                                        ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Loading</>
                                        : <>Next <ChevronRight className="w-4 h-4 ml-1" /></>}
                                </Button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Question Palette Overlay */}
                {showPalette && (
                    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center" onClick={() => setShowPalette(false)}>
                        <div className="bg-card rounded-2xl border border-border/80 shadow-2xl p-6 max-w-md w-full max-h-[80vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-sm font-bold">Question Palette — {currentExamLabel} {year} PYQs</h3>
                                <button onClick={() => setShowPalette(false)} aria-label="Close question palette" className="p-1 rounded-lg hover:bg-muted cursor-pointer">
                                    <X className="w-4 h-4" aria-hidden="true" />
                                </button>
                            </div>
                            <div className="grid grid-cols-8 gap-1.5">
                                {questions.map((q, i) => {
                                    const hasAnswer = !!answers[q.id];
                                    const isCurrent = i === currentIdx;
                                    return (
                                        <button
                                            key={q.id}
                                            onClick={() => goToQuestion(i)}
                                            className={`w-8 h-8 rounded-lg text-[10px] font-bold flex items-center justify-center transition-all cursor-pointer ${
                                                isCurrent ? 'bg-primary text-primary-foreground ring-2 ring-primary/50' :
                                                hasAnswer ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30' :
                                                'bg-muted/30 text-muted-foreground border border-border/40 hover:bg-muted/60'
                                            }`}
                                        >
                                            {i + 1}
                                        </button>
                                    );
                                })}
                            </div>
                            {nextPage !== null && (
                                <div className="mt-3 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                                    <span>Showing {questions.length} of {totalQ}</span>
                                    <Button variant="outline" size="sm" onClick={loadMore} disabled={loadingMore}>
                                        {loadingMore ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Load more'}
                                    </Button>
                                </div>
                            )}
                            <div className="flex items-center gap-4 mt-4 pt-3 border-t border-border/40 text-[10px] text-muted-foreground">
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-primary" /> Current</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/20 border border-emerald-500/30" /> Answered</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-muted/30 border border-border/40" /> Not Attempted</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
