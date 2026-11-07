/**
 * tests/[id]/page.tsx — Test-taking and review page.
 * Modes: (1) Test mode — timed MCQ session with question grid and auto-submit.
 * (2) Review mode — question-by-question review with correct answers,
 * AI-powered deep analysis (mnemonics, explanations, tips), and navigation.
 * Handles token consumption for AI features with 429 error handling.
 */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable react-hooks/exhaustive-deps */
/* eslint-disable @next/next/no-img-element */
'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { testsAPI, aiAPI, questionsAPI, extractApiErrorMessage, getApiErrorCode } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { Send, CheckCircle, Eye, ChevronLeft, ChevronRight, AlertTriangle, Loader2, Brain, Sparkles, BookMarked, Target, Lightbulb, GraduationCap, Zap, BookOpen, ArrowRight, Flag, MessageSquare, Play, ImageIcon, ZoomIn, Lock } from 'lucide-react';
import { PremiumVideoPlayer } from '@/components/ui/PremiumVideoPlayer';
import { FormattedText } from '@/components/FormattedText';
import { decodeMojiB, extractAnalysisFromJson } from '@/lib/textCleanup';
import ImageViewer from '@/components/image/ImageViewer';
import FigureImage from '@/components/question/FigureImage';
import { figureSrc } from '@/lib/figureSrc';
import { usePaywall } from '@/lib/paywall/paywallContext';

interface QuestionImage {
    id: number;
    file_url?: string | null;
    url?: string | null;
    caption?: string | null;
    // Neutral description shown before the answer (review rows, questions/image_context.py).
    alt_text?: string | null;
    role?: string | null;
    modality?: string | null;
    modality_subtype?: string | null;
    page_number?: number;
    image_index_in_page?: number;
    has_diagram?: boolean;
    has_table?: boolean;
    width?: number;
    height?: number;
}

interface Question {
    id: number;
    question_text: string;
    option_a: string;
    option_b: string;
    option_c: string;
    option_d: string;
    subject_name: string;
    topic_name: string;
    year?: number;
    correct_answer?: string;
    explanation?: string;
    video_url?: string;
    video_status?: string;
    video_thumbnail?: string;
    video_subtitles_url?: string;
    video_duration?: number;
    images?: QuestionImage[];
    // Bug 2026-08-01 admin-uploaded explanation image shown next to
    // the question stem before any attempt. Backend now returns a
    // role-filtered `stem_images` list; mirror the field here so the
    // typecheck passes.
    stem_images?: QuestionImage[];
    is_image_based?: boolean;
}

interface TestData {
    title: string;
    time_limit_minutes: number;
    num_questions: number;
    negative_marking: boolean;
    exam_type?: string;
}

const EXAM_LABELS: Record<string, string> = {
    cms: 'UPSC CMS',
    neet_pg: 'NEET PG',
    ini_cet: 'INI-CET',
    usmle: 'USMLE',
    fmge: 'FMGE',
};

// Must match QuestionFeedback.CATEGORY_CHOICES (backend/questions/models.py);
// any other value is rejected with a 400.
const FEEDBACK_CATEGORIES: [string, string][] = [
    ['wrong_answer', 'Wrong Answer'],
    ['discrepancy', 'Discrepancy in Options'],
    ['out_of_syllabus', 'Out of Syllabus'],
    ['typo', 'Typo/Formatting Issue'],
    ['explanation_needed', 'Better Explanation Needed'],
    ['other', 'Other'],
];

// In-progress answers are kept in localStorage per attempt, so a reload or a
// network blip resumes the attempt with its answers instead of wiping them.
const ATTEMPT_STORAGE_PREFIX = 'crack_test_attempt_';
const ATTEMPT_STORAGE_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;

interface SavedAttemptState {
    answers: Record<string, string>;
    marked: number[];                  // question ids
    visited: number[];                 // question ids
    timeSpent: Record<string, number>; // question id -> seconds
    currentQuestionId: number | null;
    savedAt: number;
}

function readSavedAttempt(attemptId: number): SavedAttemptState | null {
    try {
        const raw = window.localStorage.getItem(`${ATTEMPT_STORAGE_PREFIX}${attemptId}`);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed as SavedAttemptState : null;
    } catch {
        return null;
    }
}

function writeSavedAttempt(attemptId: number, state: SavedAttemptState) {
    try {
        window.localStorage.setItem(`${ATTEMPT_STORAGE_PREFIX}${attemptId}`, JSON.stringify(state));
    } catch { /* storage full or blocked: answers stay in memory */ }
}

function clearSavedAttempt(attemptId: number) {
    try {
        window.localStorage.removeItem(`${ATTEMPT_STORAGE_PREFIX}${attemptId}`);
    } catch { /* ignore */ }
}

function pruneSavedAttempts() {
    try {
        const now = Date.now();
        for (let i = window.localStorage.length - 1; i >= 0; i--) {
            const key = window.localStorage.key(i);
            if (!key || !key.startsWith(ATTEMPT_STORAGE_PREFIX)) continue;
            let savedAt = 0;
            try { savedAt = Number(JSON.parse(window.localStorage.getItem(key) || '{}').savedAt) || 0; } catch { /* corrupt: prune */ }
            if (now - savedAt > ATTEMPT_STORAGE_MAX_AGE_MS) window.localStorage.removeItem(key);
        }
    } catch { /* ignore */ }
}

interface PremiumGate {
    feature: string;
    message: string;
}

// A 402 `upgrade_required` (a test with premium questions on a free plan).
// The api.ts interceptor has already opened the upgrade modal; this keeps a
// prompt on the page after it is dismissed.
function premiumGateFrom(err: any): PremiumGate | null {
    if (err?.response?.status !== 402 || getApiErrorCode(err) !== 'upgrade_required') return null;
    const data = err.response.data || {};
    return {
        feature: typeof data.feature === 'string' && data.feature ? data.feature : 'Mock Tests',
        message: typeof data.message === 'string' ? data.message : '',
    };
}

const AI_UNAVAILABLE_NOTICE = 'AI is unavailable right now. Please try again in a little while.';

// ─── Review media ────────────────────────────────────────────────────
// The exam payload (/start/) carries no answer media for anyone: no
// explanation figures, no explanation video. After submit, /review/ rows
// carry them (tests_engine/views.py _review_media): `stem_images` for every
// row, `explanation_images` (signed URLs) and `video_url` / `video_status` /
// `video_thumbnail` / `video_subtitles_url` only on rows whose answer the
// student may see (`answer_locked` rows get [] and null).

const IMAGE_TOKEN_RE = /\[\[img:(\d+)\]\]/g;

/** Ids of the [[img:N]] tokens in `text` (figures FormattedText shows inline). */
function inlineImageIds(text: string | null | undefined): Set<number> {
    const ids = new Set<number>();
    for (const match of (text || '').matchAll(IMAGE_TOKEN_RE)) ids.add(Number(match[1]));
    return ids;
}

/** The figures of one review question: the review row's lists, the exam
 *  payload's stem figures for an older review payload, and explanation
 *  figures only from the review row of an unlocked question. */
function reviewFigures(rq: Question | undefined, rd: any): { stem: QuestionImage[]; explanation: QuestionImage[] } {
    const stem: QuestionImage[] = Array.isArray(rd?.stem_images)
        ? rd.stem_images
        : Array.isArray(rq?.stem_images) && rq.stem_images.length > 0
            ? rq.stem_images
            : (rq?.images || []).filter((img) => img.role !== 'explanation');
    const explanation: QuestionImage[] = rd?.answer_locked === true || !Array.isArray(rd?.explanation_images)
        ? []
        : rd.explanation_images;
    return { stem, explanation };
}

function figureAlt(img: QuestionImage, fallback: string): string {
    return (img.alt_text || img.caption || '').trim() || fallback;
}

/** Thumbnails that open the zoom viewer. */
function FigureGrid({ figures, fallbackAlt, onZoom, showCaptions = false }: {
    figures: QuestionImage[];
    fallbackAlt: string;
    onZoom: (img: QuestionImage) => void;
    showCaptions?: boolean;
}) {
    if (figures.length === 0) return null;
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {figures.map((img) => (
                <figure key={img.id} className="min-w-0">
                    <button
                        type="button"
                        onClick={() => onZoom(img)}
                        aria-label={`Zoom: ${figureAlt(img, fallbackAlt)}`}
                        className="relative group block w-full rounded-lg overflow-hidden border border-slate-200 bg-white transition-all hover:shadow-lg hover:border-(--accent-primary) focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                        <FigureImage
                            src={figureSrc(img)}
                            alt={figureAlt(img, fallbackAlt)}
                            loading="lazy"
                            className="w-full h-auto object-contain bg-white max-h-105"
                        />
                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-linear-to-t from-black/60 to-transparent transition-opacity flex items-end p-3">
                            <span className="text-white text-xs flex items-center gap-1">
                                <ZoomIn className="w-3.5 h-3.5" /> Tap to zoom
                            </span>
                        </div>
                    </button>
                    {showCaptions && img.caption && (
                        <figcaption className="mt-1 text-xs text-muted-foreground break-words">{img.caption}</figcaption>
                    )}
                </figure>
            ))}
        </div>
    );
}

// Result-card fields derived from a /review/ payload (used when the submit
// response was lost and the server reports the attempt as already submitted).
function resultFromReview(review: any): Record<string, any> | null {
    if (!review || typeof review !== 'object') return null;
    const correct = Number(review.correct) || 0;
    const incorrect = Number(review.incorrect) || 0;
    const unanswered = Number(review.unanswered) || 0;
    return {
        correct_count: correct,
        incorrect_count: incorrect,
        unanswered_count: unanswered,
        accuracy: review.accuracy ?? 0,
        score: review.score ?? 0,
        total_marks: review.total_marks ?? (correct + incorrect + unanswered),
        is_late: review.is_late === true,
    };
}

export default function TakeTestPage() {
    const { ready } = useRequireAuth();
    const { show: showPaywall } = usePaywall();
    const router = useRouter();
    const params = useParams();
    const testId = Number(params.id);

    const [test, setTest] = useState<TestData | null>(null);
    const [questions, setQuestions] = useState<Question[]>([]);
    const [attemptId, setAttemptId] = useState<number | null>(null);
    const [currentIdx, setCurrentIdx] = useState(0);
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const [marked, setMarked] = useState<Set<number>>(new Set());
    const [timeLeft, setTimeLeft] = useState(0);
    const [submitted, setSubmitted] = useState(false);
    const [result, setResult] = useState<Record<string, any> | null>(null);
    const [reviewData, setReviewData] = useState<any[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    // /start/ answered 402: a premium test on a free plan.
    const [premiumGate, setPremiumGate] = useState<PremiumGate | null>(null);
    // /submit/ answered 402 (e.g. the plan ended during the test): the
    // answers stay on this device and the attempt stays open.
    const [submitLocked, setSubmitLocked] = useState<PremiumGate | null>(null);
    // Bumped by "Try again" on the load-error card to re-run the start call
    // (safe: start resumes the active attempt instead of creating another).
    const [reloadKey, setReloadKey] = useState(0);
    // An earlier attempt of this test that the server completed while this
    // device never got the result (its in-progress answers are still saved
    // here): offered as "View result" instead of being lost.
    const [lostAttemptId, setLostAttemptId] = useState<number | null>(null);
    const [lostAttemptLoading, setLostAttemptLoading] = useState(false);
    const [showConfirm, setShowConfirm] = useState(false);
    // Submit failures are shown inline (with Retry) instead of through
    // `error`, which replaces the whole exam with "Failed to Load Test"
    // and threw away the student's answers.
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const submittingRef = useRef(false);
    // Set when a resumed attempt's time had already run out: it is then
    // submitted straight away with the answers saved on this device.
    const [expiredOnLoad, setExpiredOnLoad] = useState(false);
    const [autoSubmitPending, setAutoSubmitPending] = useState(false);
    // True when the result shown is the one the server already had (an
    // earlier submit went through but its response was lost).
    const [storedResult, setStoredResult] = useState(false);
    const [reviewMode, setReviewMode] = useState(false);
    const [reviewIdx, setReviewIdx] = useState(0);
    const [reviewAiExplanations, setReviewAiExplanations] = useState<Record<number, any>>({});
    const [reviewAiLoading, setReviewAiLoading] = useState(false);
    const [reviewTokenError, setReviewTokenError] = useState(false);
    // Per review index: the AI analysis is premium (402) / unavailable (503,
    // network, throttled) for that question.
    const [reviewAiLocked, setReviewAiLocked] = useState<Record<number, boolean>>({});
    const [reviewAiUnavailable, setReviewAiUnavailable] = useState<Record<number, string>>({});
    const [flagOpen, setFlagOpen] = useState(false);
    const [flagCategory, setFlagCategory] = useState('wrong_answer');
    const [flagComment, setFlagComment] = useState('');
    const [flagSubmitting, setFlagSubmitting] = useState(false);
    const [flagSuccess, setFlagSuccess] = useState(false);
    const [flagError, setFlagError] = useState<string | null>(null);
    const [zoomImg, setZoomImg] = useState<any>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    // Wall-clock end of the attempt (ms). The countdown is recomputed from it
    // on every tick, so background-tab timer throttling or a sleeping laptop
    // cannot stretch the paper past the server's clock (which flags late
    // submissions).
    const deadlineRef = useRef<number | null>(null);
    const startTimes = useRef<Record<number, number>>({});
    const timeSpent = useRef<Record<number, number>>({});
    const doSubmitRef = useRef<() => void>(() => {});

    // Pagination states to keep 120 question palette compact
    const [palettePage, setPalettePage] = useState(0);
    const [reviewPage, setReviewPage] = useState(0);

    useEffect(() => {
        setPalettePage(Math.floor(currentIdx / 30));
    }, [currentIdx]);

    useEffect(() => {
        setReviewPage(Math.floor(reviewIdx / 30));
    }, [reviewIdx]);

    useEffect(() => {
        if (!ready || !testId) return;
        setError(null);
        setPremiumGate(null);
        setLoading(true);
        testsAPI.start(testId).then(res => {
            const data = res.data;
            const qs: Question[] = Array.isArray(data.questions) ? data.questions : [];
            const attempt = Number(data.attempt_id);

            // The clock runs from the attempt's server-side start, so a
            // reload resumes the remaining time instead of a fresh timer.
            const limitSeconds = Number(data.time_limit_seconds ?? (Number(data.test?.time_limit_minutes) || 0) * 60) || 0;
            let remaining = limitSeconds;
            if (typeof data.remaining_seconds === 'number') {
                remaining = Math.max(0, Math.floor(data.remaining_seconds));
            } else if (data.started_at) {
                const startedMs = Date.parse(data.started_at);
                if (Number.isFinite(startedMs)) {
                    remaining = Math.max(0, limitSeconds - Math.floor((Date.now() - startedMs) / 1000));
                }
            }

            // Restore answers saved on this device for this attempt.
            pruneSavedAttempts();
            const saved = readSavedAttempt(attempt);
            // A successful submit clears its saved answers, so saved answers
            // of the attempt the server last completed mean its result was
            // lost on the way back (e.g. the connection dropped on submit).
            // Offered on every load (also when this reload resumed the fresh
            // attempt) until "View result" or "Dismiss" clears them.
            const lastCompleted = Number(data.last_completed_attempt_id) || null;
            setLostAttemptId(lastCompleted && lastCompleted !== attempt && readSavedAttempt(lastCompleted) ? lastCompleted : null);
            const indexById = new Map(qs.map((q, i) => [q.id, i]));
            const restoredAnswers: Record<number, string> = {};
            const restoredMarked = new Set<number>();
            let startIdx = 0;
            const now = Date.now();
            startTimes.current = {};
            timeSpent.current = {};
            if (saved) {
                for (const [key, value] of Object.entries(saved.answers || {})) {
                    const qid = Number(key);
                    if (indexById.has(qid) && typeof value === 'string' && /^[A-E]$/.test(value)) {
                        restoredAnswers[qid] = value;
                    }
                }
                for (const qid of saved.marked || []) {
                    const idx = indexById.get(Number(qid));
                    if (idx !== undefined) restoredMarked.add(idx);
                }
                for (const qid of saved.visited || []) {
                    const idx = indexById.get(Number(qid));
                    if (idx !== undefined) startTimes.current[idx] = now;
                }
                for (const [key, seconds] of Object.entries(saved.timeSpent || {})) {
                    const idx = indexById.get(Number(key));
                    if (idx !== undefined && Number.isFinite(Number(seconds))) timeSpent.current[idx] = Math.max(0, Number(seconds));
                }
                const savedIdx = saved.currentQuestionId != null ? indexById.get(Number(saved.currentQuestionId)) : undefined;
                if (savedIdx !== undefined) startIdx = savedIdx;
            }
            startTimes.current[startIdx] = now;

            setTest(data.test);
            setQuestions(qs);
            setAttemptId(attempt);
            setAnswers(restoredAnswers);
            setMarked(restoredMarked);
            setCurrentIdx(startIdx);
            deadlineRef.current = limitSeconds > 0 ? Date.now() + remaining * 1000 : null;
            setTimeLeft(remaining);
            if (limitSeconds > 0 && remaining <= 0 && qs.length > 0) {
                setExpiredOnLoad(true);
                setAutoSubmitPending(true);
            }
        }).catch(err => {
            const gate = premiumGateFrom(err);
            if (gate) {
                setPremiumGate(gate);
                return;
            }
            setError(extractApiErrorMessage(err.response?.data || err.message, 'Failed to start the test. Please try again.'));
        }).finally(() => setLoading(false));
    }, [ready, testId, reloadKey]);

    // Persist in-progress state for this attempt (cleared after submit).
    useEffect(() => {
        if (!attemptId || submitted || questions.length === 0) return;
        const idOf = (idx: number) => questions[idx]?.id;
        const spent: Record<string, number> = {};
        for (const [idx, seconds] of Object.entries(timeSpent.current)) {
            const qid = idOf(Number(idx));
            if (qid !== undefined) spent[String(qid)] = seconds;
        }
        writeSavedAttempt(attemptId, {
            answers: Object.fromEntries(Object.entries(answers).map(([qid, value]) => [String(qid), value])),
            marked: Array.from(marked).map(idOf).filter((qid): qid is number => qid !== undefined),
            visited: Object.keys(startTimes.current).map(i => idOf(Number(i))).filter((qid): qid is number => qid !== undefined),
            timeSpent: spent,
            currentQuestionId: idOf(currentIdx) ?? null,
            savedAt: Date.now(),
        });
    }, [attemptId, submitted, questions, answers, marked, currentIdx]);

    // Timer — uses refs to avoid stale closures; each tick reads the
    // wall-clock deadline instead of counting ticks.
    useEffect(() => {
        if (timeLeft > 0 && !submitted) {
            timerRef.current = setInterval(() => {
                const deadline = deadlineRef.current;
                if (deadline === null) return;
                const next = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
                setTimeLeft(next);
                if (next <= 0) doSubmitRef.current();
            }, 1000);
        }
        return () => { if (timerRef.current) clearInterval(timerRef.current); };

    }, [submitted, timeLeft > 0]);

    const formatTime = (s: number) => {
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
    };

    const selectAnswer = (option: string) => {
        if (submitted) return;
        setAnswers(prev => ({ ...prev, [questions[currentIdx].id]: option }));
    };

    const goTo = useCallback((idx: number) => {
        // Record time spent on current question
        const now = Date.now();
        if (startTimes.current[currentIdx]) {
            const elapsed = Math.round((now - startTimes.current[currentIdx]) / 1000);
            timeSpent.current[currentIdx] = (timeSpent.current[currentIdx] || 0) + elapsed;
        }
        startTimes.current[idx] = now;
        setCurrentIdx(idx);
    }, [currentIdx]);

    const doSubmit = useCallback(async () => {
        // In-flight guard: the confirm button and the timer's auto-submit
        // could previously both fire while a submit was pending.
        if (!attemptId || submitted || submittingRef.current) return;
        submittingRef.current = true;
        setSubmitting(true);
        setSubmitError(null);
        setSubmitLocked(null);
        if (timerRef.current) clearInterval(timerRef.current);

        // Record final time for current question
        const now = Date.now();
        if (startTimes.current[currentIdx]) {
            const elapsed = Math.round((now - startTimes.current[currentIdx]) / 1000);
            timeSpent.current[currentIdx] = (timeSpent.current[currentIdx] || 0) + elapsed;
        }

        const answerList = questions.map((q, i) => ({
            question_id: q.id,
            selected_answer: answers[q.id] || '',
            time_taken_seconds: timeSpent.current[i] || 0,
        }));

        try {
            const res = await testsAPI.submit(testId, { attempt_id: attemptId, answers: answerList });
            clearSavedAttempt(attemptId);
            setResult(res.data);
            setSubmitted(true);
            setShowConfirm(false);
            // Fetch full review data with correct answers & explanations
            try {
                const reviewRes = await testsAPI.review(testId, attemptId);
                setReviewData(reviewRes.data.questions || []);
            } catch { /* review fetch is non-critical */ }
        } catch (err: any) {
            const data = err?.response?.data;
            const gate = premiumGateFrom(err);
            if (gate) {
                // Not scored: the upgrade prompt (modal + banner) replaces the
                // error toast; the answers stay saved on this device.
                setSubmitLocked(gate);
                setShowConfirm(false);
                return;
            }
            const alreadySubmitted = err?.response?.status === 400 && (
                data?.code === 'already_submitted' || /already submitted/i.test(String(data?.error || ''))
            );
            if (alreadySubmitted) {
                // The server already scored this attempt (an earlier submit
                // went through but its response was lost). Retrying can never
                // succeed, so show the stored result and the review instead.
                let stored: Record<string, any> | null = data?.result && typeof data.result === 'object' ? data.result : null;
                try {
                    const reviewRes = await testsAPI.review(testId, attemptId);
                    setReviewData(reviewRes.data.questions || []);
                    if (!stored) stored = resultFromReview(reviewRes.data);
                } catch { /* fall through to the error below if nothing usable */ }
                if (stored) {
                    clearSavedAttempt(attemptId);
                    setResult(stored);
                    setStoredResult(true);
                    setSubmitted(true);
                    setShowConfirm(false);
                    return;
                }
            }
            console.error('Submit failed:', err);
            // Surface the error so the user can recover instead of being stuck.
            const message = extractApiErrorMessage(data, '') || 'Failed to submit test. Please check your connection and try again.';
            setSubmitError(message);
            setShowConfirm(false);
        } finally {
            submittingRef.current = false;
            setSubmitting(false);
        }
    }, [attemptId, submitted, currentIdx, questions, answers, testId]);

    // Keep ref in sync so timer always calls latest doSubmit
    useEffect(() => { doSubmitRef.current = doSubmit; }, [doSubmit]);

    // A resumed attempt whose time had already run out is submitted at once
    // (as the timer would have), with the answers saved on this device.
    // Declared after the ref sync above so it calls the current doSubmit.
    useEffect(() => {
        if (!autoSubmitPending || !attemptId || submitted || questions.length === 0) return;
        setAutoSubmitPending(false);
        doSubmitRef.current();
    }, [autoSubmitPending, attemptId, submitted, questions.length]);

    // NOTE: AI explanation is NO LONGER auto-fetched.
    // Students must click "Generate AI Analysis" to save API tokens.

    // Show the stored result of the attempt whose submit response was lost.
    const viewLostResult = async () => {
        if (!lostAttemptId || lostAttemptLoading) return;
        setLostAttemptLoading(true);
        try {
            const reviewRes = await testsAPI.review(testId, lostAttemptId);
            const stored = resultFromReview(reviewRes.data);
            if (!stored) return;
            if (timerRef.current) clearInterval(timerRef.current);
            clearSavedAttempt(lostAttemptId);
            setReviewData(reviewRes.data.questions || []);
            setResult(stored);
            setStoredResult(true);
            setSubmitted(true);
            setLostAttemptId(null);
        } catch {
            /* keep the notice: the button stays available for a retry */
        } finally {
            setLostAttemptLoading(false);
        }
    };

    const dismissLostResult = () => {
        if (lostAttemptId) clearSavedAttempt(lostAttemptId);
        setLostAttemptId(null);
    };

    const handleSubmit = () => setShowConfirm(true);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="animate-pulse text-xl gradient-text">Loading Test...</div>
            </div>
        );
    }

    if (premiumGate) {
        return (
            <div className="min-h-screen flex flex-col bg-background">
                <div className="sticky top-0 z-50 px-6 py-3 flex items-center justify-between"
                    style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                    <div className="font-bold text-lg gradient-text">UPSC CMS SIMULATOR</div>
                </div>
                <div className="flex-1 flex items-center justify-center p-4 sm:p-8">
                    <div className="glass-card p-6 sm:p-8 max-w-md w-full text-center border-border/80 bg-card/85 shadow-md">
                        <Lock className="w-12 h-12 mx-auto mb-4 text-primary" aria-hidden="true" />
                        <h1 className="text-xl font-bold mb-2 text-foreground">This test is part of Premium</h1>
                        <p className="text-sm text-muted-foreground mb-6">
                            {premiumGate.message || 'Subscribe to take this test, with every answer and explanation unlocked.'}
                        </p>
                        <div className="flex flex-col gap-3 sm:flex-row">
                            <button onClick={() => router.push('/tests')} className="btn-secondary w-full inline-flex items-center justify-center">
                                Back to Test Center
                            </button>
                            <button onClick={() => showPaywall(premiumGate.feature)} className="btn-primary w-full justify-center">
                                <Lock className="w-4 h-4" aria-hidden="true" /> Unlock with Premium
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex flex-col bg-background">
                <div className="sticky top-0 z-50 px-6 py-3 flex items-center justify-between"
                    style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                    <div className="font-bold text-lg gradient-text">UPSC CMS SIMULATOR</div>
                </div>
                <div className="flex-1 flex items-center justify-center p-8">
                    <div className="glass-card p-8 max-w-md w-full text-center border-border/80 bg-card/85 shadow-md">
                        <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-destructive" />
                        <h3 className="text-xl font-bold mb-2 text-foreground">Failed to Load Test</h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            {error}
                        </p>
                        <div className="flex flex-col gap-3 sm:flex-row">
                            <button onClick={() => setReloadKey(k => k + 1)} className="btn-secondary w-full inline-flex items-center justify-center">
                                Try again
                            </button>
                            <button onClick={() => router.push('/tests')} className="btn-primary w-full justify-center">
                                Back to Test Center
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (!loading && questions.length === 0) {
        return (
            <div className="min-h-screen flex flex-col bg-background">
                <div className="sticky top-0 z-50 px-6 py-3 flex items-center justify-between"
                    style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                    <div className="font-bold text-lg gradient-text">UPSC CMS SIMULATOR</div>
                </div>
                <div className="flex-1 flex items-center justify-center p-8">
                    <div className="glass-card p-8 max-w-md w-full text-center border-border/80 bg-card/85 shadow-md">
                        <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-amber-500" />
                        <h3 className="text-xl font-bold mb-2 text-foreground">No Questions Found</h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            This test has no questions assigned to it or failed to load. Please contact the administrator.
                        </p>
                        <div className="flex gap-3">
                            <button onClick={() => router.push('/tests')} className="btn-primary w-full justify-center">
                                Back to Test Center
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // ─── REVIEW MODE ────────────────────────────────────
    if (submitted && result && reviewMode) {
        const rq = questions[reviewIdx];
        // Match review data by question_id, not by index (order may differ)
        const rd = reviewData ? reviewData.find((r: any) => r.question_id === rq?.id) : null;
        const userAns = rd?.selected_answer || answers[rq?.id];
        // Free plan, non-showcase question: the server returns right / wrong
        // only (no answer key, explanation or mnemonic).
        const answerLocked = rd?.answer_locked === true;
        const correctAns = rd?.correct_answer || rq?.correct_answer;
        const explanation = answerLocked ? '' : (rd?.explanation || rq?.explanation);
        // Figures and the explanation video come from the review row (the
        // exam payload has none of the answer media).
        const figures = reviewFigures(rq, rd);
        const explanationText = explanation ? extractAnalysisFromJson(String(explanation)) : '';
        const stemInlineIds = inlineImageIds(rq?.question_text);
        const explanationInlineIds = inlineImageIds(explanationText);
        const stemGallery = figures.stem.filter((img) => !stemInlineIds.has(img.id));
        const explanationGallery = figures.explanation.filter((img) => !explanationInlineIds.has(img.id));
        const zoomFigures = [...stemGallery, ...explanationGallery];
        const reviewVideoUrl = !answerLocked && rd?.video_status === 'completed' && rd?.video_url ? String(rd.video_url) : '';
        const aiExp = reviewAiExplanations[reviewIdx];
        // The AI analysis explains the answer, so it is locked with it; the
        // server can also refuse it (402) for this question.
        const aiLocked = answerLocked || reviewAiLocked[reviewIdx] === true;
        const aiUnavailable = reviewAiUnavailable[reviewIdx];

        const fetchAiExplanation = (idx: number) => {
            if (reviewAiExplanations[idx] || reviewTokenError || reviewAiLocked[idx]) return;
            const q = questions[idx];
            if (!q) return;
            const rrd = reviewData ? reviewData.find((r: any) => r.question_id === q.id) : null;
            setReviewAiLoading(true);
            setReviewAiUnavailable(prev => {
                if (!(idx in prev)) return prev;
                const next = { ...prev };
                delete next[idx];
                return next;
            });
            // question_id lets the server explain the stored question (and
            // apply the answer entitlement) instead of trusting this payload.
            const payload = {
                question_id: q.id,
                question_text: q.question_text,
                options: { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d },
                correct_answer: rrd?.correct_answer || q.correct_answer || '',
                selected_answer: rrd?.selected_answer || answers[q.id] || '',
                subject: rrd?.subject || q.subject_name || '',
                topic: rrd?.topic || q.topic_name || '',
            };
            aiAPI.explainAfterAnswer(payload).then(res => {
                setReviewAiExplanations(prev => ({ ...prev, [idx]: res.data }));
            }).catch((err) => {
                if (err?.response?.status === 429 && err?.response?.data?.error === 'insufficient_tokens') {
                    setReviewTokenError(true);
                } else if (premiumGateFrom(err)) {
                    // The api.ts interceptor opened the upgrade modal; the
                    // locked card replaces the button. Nothing was charged.
                    setReviewAiLocked(prev => ({ ...prev, [idx]: true }));
                } else {
                    // 503 ai_unavailable (never charged), throttling, network.
                    setReviewAiUnavailable(prev => ({ ...prev, [idx]: AI_UNAVAILABLE_NOTICE }));
                }
            }).finally(() => setReviewAiLoading(false));
        };

        return (
            <>
            <div className="min-h-screen bg-background">
                {/* Sticky Header */}
                <div className="sticky top-0 z-50 px-4 md:px-6 py-3 flex items-center justify-between" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                    <div className="flex items-center gap-3">
                        <span className="font-bold text-base gradient-text">📖 REVIEW MODE</span>
                        <span className="hidden sm:inline text-xs px-2 py-1 rounded-full" style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)' }}>{test?.title} — {questions.length} Questions</span>
                    </div>
                    <div className="flex items-center gap-2">
                        {/* Paginated question nav dots */}
                        <div className="hidden md:flex items-center gap-2">
                            {/* Page Tabs */}
                            {questions.length > 30 && (
                                <div className="flex gap-1 border-r pr-2 border-glass-border">
                                    {Array.from({ length: Math.ceil(questions.length / 30) }).map((_, pIdx) => (
                                        <button
                                            key={pIdx}
                                            onClick={() => setReviewPage(pIdx)}
                                            className={`text-[10px] font-bold px-2 py-1 rounded transition-colors ${
                                                reviewPage === pIdx
                                                    ? 'bg-primary text-primary-foreground'
                                                    : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                                            }`}
                                        >
                                            {pIdx * 30 + 1}-{Math.min((pIdx + 1) * 30, questions.length)}
                                        </button>
                                    ))}
                                </div>
                            )}
                            <div className="flex items-center gap-1 max-w-125">
                                {questions.slice(reviewPage * 30, (reviewPage + 1) * 30).map((q, localIdx) => {
                                    const i = reviewPage * 30 + localIdx;
                                    const qrd = reviewData?.find((r: any) => r.question_id === q.id);
                                    const isCorrect = qrd?.is_correct === true;
                                    const isWrong = qrd?.is_correct === false;
                                    return (
                                        <button key={i} onClick={() => setReviewIdx(i)}
                                            className="w-7 h-7 rounded-full text-xs font-bold transition-all flex items-center justify-center shrink-0"
                                            style={{
                                                background: i === reviewIdx ? 'var(--accent-primary)' : isCorrect ? 'rgba(16,185,129,0.15)' : isWrong ? 'rgba(239,68,68,0.15)' : 'var(--bg-card)',
                                                color: i === reviewIdx ? 'white' : isCorrect ? '#10b981' : isWrong ? '#ef4444' : 'var(--text-secondary)',
                                                border: i === reviewIdx ? '2px solid var(--accent-primary)' : '1px solid transparent',
                                                transform: i === reviewIdx ? 'scale(1.15)' : 'scale(1)',
                                            }}>
                                            {i + 1}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <button onClick={() => setReviewMode(false)} className="btn-secondary text-sm ml-2">← Back to Results</button>
                    </div>
                </div>

                <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-4">
                    {/* ═══ QUESTION CARD ═══ */}
                    <div className="glass-card overflow-hidden animate-fadeInUp">
                        {/* Result Banner */}
                        <div className="px-5 py-3 flex items-center justify-between" style={{
                            background: rd?.is_correct ? 'rgba(16,185,129,0.06)' : rd?.is_correct === false ? 'rgba(239,68,68,0.06)' : 'rgba(245,158,11,0.06)',
                            borderBottom: `2px solid ${rd?.is_correct ? '#10b981' : rd?.is_correct === false ? '#ef4444' : '#f59e0b'}`
                        }}>
                            <div className="flex items-center gap-3">
                                <div className="text-2xl">{rd?.is_correct ? '✅' : rd?.is_correct === false ? '❌' : '⏭️'}</div>
                                <div>
                                    <div className="font-bold text-sm">Q{reviewIdx + 1} of {questions.length}</div>
                                    <div className="text-xs" style={{ color: rd?.is_correct ? '#10b981' : rd?.is_correct === false ? '#ef4444' : '#f59e0b' }}>
                                        {rd?.is_correct ? 'Correct! Great job 🎉' : rd?.is_correct === false ? (answerLocked ? 'Incorrect' : 'Incorrect — Study the explanation below carefully') : (answerLocked ? 'Skipped' : 'Skipped — Review what you missed')}
                                    </div>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {rq?.subject_name && <span className="review-tag review-tag-cyan">{rq.subject_name}</span>}
                                {(rd?.topic || rq?.topic_name) && <span className="review-tag review-tag-purple">{rd?.topic || rq?.topic_name}</span>}
                                {rd?.difficulty && <span className={`review-tag ${rd.difficulty === 'hard' ? 'review-tag-red' : rd.difficulty === 'medium' ? 'review-tag-amber' : 'review-tag-green'}`}>{rd.difficulty}</span>}
                                {rd?.year ? <span className="review-tag review-tag-pink">PYQ {rd.year}</span> : null}
                            </div>
                        </div>

                        {/* Question Text — rendered with markdown for proper bold/list formatting */}
                        <div className="p-5 md:p-6">
                            <div className="text-base md:text-lg font-medium leading-relaxed mb-6" style={{ color: 'var(--text-primary)' }}>
                                <FormattedText text={rq?.question_text || ''} images={figures.stem} />
                            </div>

                            {/* Question figures (those not already shown inline in the stem) */}
                            {stemGallery.length > 0 && (
                                <div className="mb-6">
                                    <FigureGrid figures={stemGallery} fallbackAlt="Question figure" onZoom={setZoomImg} />
                                </div>
                            )}

                            {/* Concept Tags */}
                            {rd?.concept_tags && rd.concept_tags.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mb-4">
                                    {rd.concept_tags.map((tag: string, i: number) => (
                                        <span key={i} className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: 'rgba(99,102,241,0.08)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.15)' }}>{tag}</span>
                                    ))}
                                </div>
                            )}

                            {/* Options */}
                            <div className="space-y-2.5">
                                {['A', 'B', 'C', 'D'].map(opt => {
                                    const optText = rq?.[`option_${opt.toLowerCase()}` as keyof Question] || rq?.[`option_${opt}` as keyof Question];
                                    if (!optText) return null;
                                    const isUserPick = userAns === opt;
                                    // Locked rows carry no answer key: only the
                                    // student's own pick is marked right or wrong.
                                    const isCorrect = correctAns === opt || (answerLocked && isUserPick && rd?.is_correct === true);
                                    const isWrong = isUserPick && !isCorrect;
                                    return (
                                        <div key={opt} className={`review-option ${isCorrect ? 'review-option-correct' : isWrong ? 'review-option-wrong' : ''}`}>
                                            <div className={`review-option-dot ${isCorrect ? 'correct' : isWrong ? 'wrong' : ''}`}>{opt}</div>
                                            <div className="flex-1 text-sm font-medium">{String(optText).replace(/\s*\*+\s*$/, '').trim()}</div>
                                            {isCorrect && <span className="review-option-label correct">✓ Correct Answer</span>}
                                            {isWrong && <span className="review-option-label wrong">✗ Your Answer</span>}
                                            {isUserPick && isCorrect && <span className="review-option-label correct">✓ Your Answer</span>}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Flag Question Button */}
                            <div className="flex justify-end mt-4">
                                <button onClick={() => { setFlagOpen(!flagOpen); setFlagSuccess(false); setFlagError(null); }}
                                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                                    <Flag className="w-3.5 h-3.5" /> Report Issue
                                </button>
                            </div>
                            {flagOpen && (
                                <div className="glass-card p-4 mt-3 space-y-3 animate-fadeInUp">
                                    <h5 className="text-sm font-bold flex items-center gap-2" style={{ color: '#ef4444' }}>
                                        <Flag className="w-4 h-4" /> Report an Issue with this Question
                                    </h5>
                                    {flagSuccess ? (
                                        <p className="text-sm text-emerald-500 font-medium">✓ Thanks! Your feedback has been submitted.</p>
                                    ) : (
                                        <>
                                            {flagError && <p role="alert" className="text-sm text-red-500">{flagError}</p>}
                                            <select className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                                                aria-label="Issue category"
                                                value={flagCategory} onChange={e => setFlagCategory(e.target.value)}>
                                                {FEEDBACK_CATEGORIES.map(([value, label]) => (
                                                    <option key={value} value={value}>{label}</option>
                                                ))}
                                            </select>
                                            <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-15 resize-none"
                                                placeholder="Describe the issue (e.g., question text is incomplete, options are cut off...)"
                                                value={flagComment} onChange={e => setFlagComment(e.target.value)} />
                                            <div className="flex gap-2">
                                                <button
                                                    className="btn-primary text-xs px-3 py-1.5"
                                                    onClick={() => {
                                                        if (!flagComment.trim() || !rq) return;
                                                        setFlagSubmitting(true);
                                                        setFlagError(null);
                                                        questionsAPI.submitFeedback({
                                                            question: rq.id,
                                                            category: flagCategory,
                                                            comment: flagComment.trim(),
                                                        }).then(() => {
                                                            setFlagSuccess(true);
                                                            setTimeout(() => { setFlagOpen(false); setFlagSuccess(false); setFlagComment(''); setFlagError(null); }, 2000);
                                                        }).catch((err: any) => {
                                                            setFlagError(
                                                                extractApiErrorMessage(err?.response?.data, '')
                                                                || 'Unable to submit feedback right now. Please try again.'
                                                            );
                                                        })
                                                        .finally(() => setFlagSubmitting(false));
                                                    }}
                                                    disabled={flagSubmitting || !flagComment.trim()}>
                                                    {flagSubmitting ? 'Submitting...' : 'Submit'}
                                                </button>
                                                <button className="btn-secondary text-xs px-3 py-1.5" onClick={() => { setFlagOpen(false); setFlagError(null); }}>Cancel</button>
                                            </div>
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* VIDEO PLAYER — from the review row (entitled viewers only) */}
                    {reviewVideoUrl && (
                        <div className="explanation-card explanation-card-indigo animate-fadeInUp mt-4 mb-4 overflow-hidden">
                            <div className="p-1">
                                <h4 className="explanation-card-title indigo px-4 py-2"><Play className="w-4 h-4" /> AI Video Explanation</h4>
                                <PremiumVideoPlayer
                                    src={reviewVideoUrl}
                                    subtitlesSrc={rd?.video_subtitles_url || undefined}
                                    poster={rd?.video_thumbnail || undefined}
                                    className="w-full max-h-125"
                                />
                                <p className="px-4 py-2 text-xs">
                                    <a href={reviewVideoUrl} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                                        Open the video in a new tab
                                    </a>
                                </p>
                            </div>
                        </div>
                    )}

                    {/* ═══ DB EXPLANATION (always show first if available) ═══ */}
                    {explanationText && (
                        <div className="explanation-card explanation-card-green animate-fadeInUp">
                            <div className="explanation-card-accent green"></div>
                            <div className="p-5 pl-6">
                                <h4 className="explanation-card-title green"><CheckCircle className="w-4 h-4" /> Answer Explanation</h4>
                                <div className="text-sm leading-relaxed mt-2 prose prose-sm max-w-none" style={{ color: 'var(--text-secondary)' }}>
                                    <FormattedText text={explanationText} images={[...figures.stem, ...figures.explanation]} />
                                </div>
                                {explanationGallery.length > 0 && (
                                    <div className="mt-4">
                                        <h5 className="mb-2 text-xs font-semibold text-foreground flex items-center gap-1.5"><ImageIcon className="w-3.5 h-3.5" aria-hidden="true" /> Explanation figures</h5>
                                        <FigureGrid figures={explanationGallery} fallbackAlt="Explanation figure" onZoom={setZoomImg} showCaptions />
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                    {/* Explanation figures of a question without a written explanation */}
                    {!explanationText && explanationGallery.length > 0 && (
                        <div className="explanation-card explanation-card-green animate-fadeInUp">
                            <div className="explanation-card-accent green"></div>
                            <div className="p-5 pl-6">
                                <h4 className="explanation-card-title green"><ImageIcon className="w-4 h-4" aria-hidden="true" /> Explanation figures</h4>
                                <div className="mt-3">
                                    <FigureGrid figures={explanationGallery} fallbackAlt="Explanation figure" onZoom={setZoomImg} showCaptions />
                                </div>
                            </div>
                        </div>
                    )}

                    {/* DB Mnemonic */}
                    {rd?.mnemonic && !aiExp?.mnemonic && (
                        <div className="mnemonic-card animate-fadeInUp">
                            <div className="flex items-start gap-3">
                                <div className="mnemonic-icon">💡</div>
                                <div>
                                    <h5 className="text-sm font-bold mb-1" style={{ color: '#f59e0b' }}>Memory Trick</h5>
                                    <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{String(rd.mnemonic)}</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ═══ LOCKED ANSWER (free plan, non-showcase question) ═══ */}
                    {aiLocked && !aiExp && (
                        <div className="glass-card p-5 flex flex-col gap-3 sm:flex-row sm:items-center">
                            <Lock className="w-6 h-6 shrink-0 text-primary" aria-hidden="true" />
                            <div className="flex-1">
                                <p className="text-sm font-bold text-foreground">
                                    {answerLocked ? 'Answer and explanation are part of Premium' : 'AI analysis of this question is part of Premium'}
                                </p>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    {answerLocked
                                        ? 'You can see whether your answer was right. Upgrade to unlock the correct answers, explanations and AI analysis.'
                                        : 'Upgrade to get the AI analysis of every question.'}
                                </p>
                            </div>
                            <button onClick={() => showPaywall('PYQ answers')} className="btn-primary justify-center text-sm shrink-0">
                                Unlock answers
                            </button>
                        </div>
                    )}

                    {/* ═══ AI UNAVAILABLE (503 / network) — short notice, nothing charged ═══ */}
                    {aiUnavailable && !aiLocked && !aiExp && !reviewAiLoading && !reviewTokenError && (
                        <div role="status" className="glass-card p-4 flex flex-col gap-3 sm:flex-row sm:items-center">
                            <AlertTriangle className="w-5 h-5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                            <p className="flex-1 text-sm text-muted-foreground">{aiUnavailable}</p>
                            <button onClick={() => fetchAiExplanation(reviewIdx)} className="btn-secondary justify-center text-sm shrink-0">
                                Try again
                            </button>
                        </div>
                    )}

                    {/* ═══ AI GENERATE BUTTON — only triggers on click to save API tokens ═══ */}
                    {!aiLocked && !aiUnavailable && !aiExp && !reviewAiLoading && !reviewTokenError && (
                        <button onClick={() => fetchAiExplanation(reviewIdx)}
                            className="w-full glass-card p-5 flex items-center justify-center gap-3 cursor-pointer transition-all hover:scale-[1.01] group"
                            style={{ background: 'rgba(6,182,212,0.04)' }}>
                            <Brain className="w-6 h-6 group-hover:animate-pulse" style={{ color: 'var(--accent-primary)' }} />
                            <div className="text-left">
                                <span className="text-sm font-bold block" style={{ color: 'var(--accent-primary)' }}>Generate AI Analysis</span>
                                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Click to get mnemonics, explanations, exam tips & more</span>
                            </div>
                        </button>
                    )}

                    {/* Token depleted error */}
                    {reviewTokenError && !aiExp && !aiLocked && (
                        <div className="token-depleted-banner">
                            <div className="flex items-start gap-3">
                                <Zap className="w-5 h-5 mt-0.5 shrink-0" style={{ color: '#ef4444' }} />
                                <div>
                                    <h5 className="text-sm font-bold" style={{ color: '#ef4444' }}>AI Tokens Exhausted</h5>
                                    <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                        Your daily/weekly free tokens have been used up. Purchase more tokens to continue using AI features.
                                    </p>
                                    <Link href="/tokens" className="btn-primary text-xs mt-3 inline-flex">
                                        <Zap className="w-3 h-3" /> Buy Tokens
                                    </Link>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ═══ AI LOADING ═══ */}
                    {reviewAiLoading && !aiExp && (
                        <div className="glass-card p-6 flex items-center gap-4 animate-pulse" style={{ borderColor: 'rgba(6,182,212,0.3)' }}>
                            <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                            <div>
                                <span className="text-sm font-bold" style={{ color: 'var(--accent-primary)' }}>🧠 AI is preparing your personalized study material...</span>
                                <span className="text-xs block mt-1" style={{ color: 'var(--text-secondary)' }}>Generating mnemonics, topic deep-dive, exam tips & more</span>
                            </div>
                        </div>
                    )}

                    {/* ═══ AI DEEP ANALYSIS ═══ */}
                    {aiExp && (
                        <div className="space-y-3 animate-fadeInUp">
                            {/* Section Header */}
                            <div className="flex items-center gap-2 px-1">
                                <Brain className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                <span className="font-bold text-sm gradient-text tracking-wide">AI-POWERED DEEP ANALYSIS</span>
                                <div className="flex-1 h-px" style={{ background: 'linear-gradient(to right, var(--glass-border), transparent)' }}></div>
                            </div>

                            {/* 🎯 MNEMONIC — Always first, always prominent */}
                            {aiExp.mnemonic && (
                                <div className="mnemonic-card animate-fadeInUp">
                                    <div className="flex items-start gap-3">
                                        <div className="mnemonic-icon">💡</div>
                                        <div className="flex-1">
                                            <h5 className="text-sm font-bold mb-2" style={{ color: '#f59e0b' }}>🧠 Memory Trick — Never Forget This!</h5>
                                            <p className="text-sm font-medium leading-relaxed" style={{ color: 'var(--text-primary)' }}>{aiExp.mnemonic}</p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Core Concept + Why Correct + Why Wrong */}
                            <div className="glass-card overflow-hidden">
                                {aiExp.core_concept && (
                                    <div className="px-5 py-3 flex items-center gap-2" style={{ background: 'rgba(6,182,212,0.05)', borderBottom: '1px solid var(--glass-border)' }}>
                                        <Target className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                                        <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--accent-primary)' }}>Core Concept</span>
                                        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{aiExp.core_concept}</span>
                                    </div>
                                )}
                                {aiExp.why_correct && (
                                    <div className="p-5">
                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: '#10b981' }}>
                                            <CheckCircle className="w-3.5 h-3.5" /> Why {correctAns} is Correct
                                        </h5>
                                        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{(() => { let t = (aiExp.why_correct || '').trim(); if (t.startsWith('```')) t = t.replace(/^```\w*\n?/, ''); if (t.endsWith('```')) t = t.slice(0, -3); t = t.trim(); if (t.startsWith('{')) { try { const p = JSON.parse(t); if (p.why_correct) return p.why_correct; } catch {} } if (t.toLowerCase().startsWith('json')) t = t.slice(4).trim(); return t; })()}</p>
                                    </div>
                                )}
                                {aiExp.why_wrong && Object.keys(aiExp.why_wrong).length > 0 && (
                                    <div className="px-5 pb-5 space-y-2">
                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#ef4444' }}>❌ Why Other Options Are Wrong</h5>
                                        {Object.entries(aiExp.why_wrong).map(([k, v]) => (
                                            <div key={k} className="flex gap-2.5 text-sm p-2.5 rounded-lg" style={{ background: 'rgba(239,68,68,0.04)' }}>
                                                <span className="font-bold shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs" style={{ background: 'rgba(239,68,68,0.12)', color: '#ef4444' }}>{k}</span>
                                                <span style={{ color: 'var(--text-secondary)' }}>{String(v)}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* 📖 TOPIC DEEP DIVE — The learning section */}
                            {aiExp.topic_deep_dive && (
                                <div className="explanation-card explanation-card-indigo animate-fadeInUp">
                                    <div className="explanation-card-accent indigo"></div>
                                    <div className="p-5 pl-6">
                                        <h4 className="explanation-card-title indigo"><BookOpen className="w-4 h-4" /> 📖 Topic Deep Dive — Learn the Bigger Picture</h4>
                                        <p className="text-sm leading-relaxed mt-2" style={{ color: 'var(--text-secondary)', lineHeight: '1.75' }}>{aiExp.topic_deep_dive}</p>
                                    </div>
                                </div>
                            )}

                            {/* ⚡ HIGH YIELD + KEY DIFFERENTIATORS — Side by side */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {aiExp.high_yield_points?.length > 0 && (
                                    <div className="glass-card p-4">
                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5" style={{ color: '#ec4899' }}>
                                            <Zap className="w-3.5 h-3.5" /> ⚡ High Yield Points
                                        </h5>
                                        <ul className="space-y-2">
                                            {aiExp.high_yield_points.map((p: string, i: number) => (
                                                <li key={i} className="text-xs flex gap-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                                    <span className="mt-0.5 shrink-0" style={{ color: '#ec4899' }}>▸</span>
                                                    <span>{p}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {aiExp.key_differentiators?.length > 0 && (
                                    <div className="glass-card p-4">
                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-3 flex items-center gap-1.5" style={{ color: '#f59e0b' }}>
                                            <ArrowRight className="w-3.5 h-3.5" /> ⚖️ Key Differentiators
                                        </h5>
                                        <ul className="space-y-2">
                                            {aiExp.key_differentiators.map((d: string, i: number) => (
                                                <li key={i} className="text-xs leading-relaxed px-3 py-2 rounded-lg" style={{ background: 'rgba(245,158,11,0.05)', color: 'var(--text-secondary)', borderLeft: '2px solid rgba(245,158,11,0.3)' }}>
                                                    {d}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>

                            {/* 📚 Reference + 💎 Clinical Pearl + 🎓 Exam Tip — 3 cols */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                {aiExp.textbook_reference?.book && (
                                    <div className="glass-card p-4 flex items-start gap-2.5">
                                        <BookMarked className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#8b5cf6' }} />
                                        <div>
                                            <h6 className="text-xs font-bold mb-1" style={{ color: '#8b5cf6' }}>📚 Textbook</h6>
                                            <p className="text-xs font-semibold">{aiExp.textbook_reference.book}</p>
                                            {aiExp.textbook_reference.chapter && <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>Ch: {aiExp.textbook_reference.chapter}</p>}
                                            {aiExp.textbook_reference.page && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Pg: {aiExp.textbook_reference.page}</p>}
                                        </div>
                                    </div>
                                )}
                                {aiExp.clinical_pearl && (
                                    <div className="glass-card p-4 flex items-start gap-2.5">
                                        <Sparkles className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#10b981' }} />
                                        <div>
                                            <h6 className="text-xs font-bold mb-1" style={{ color: '#10b981' }}>💎 Clinical Pearl</h6>
                                            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{aiExp.clinical_pearl}</p>
                                        </div>
                                    </div>
                                )}
                                {aiExp.exam_tip && (
                                    <div className="glass-card p-4 flex items-start gap-2.5">
                                        <GraduationCap className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#f59e0b' }} />
                                        <div>
                                            <h6 className="text-xs font-bold mb-1" style={{ color: '#f59e0b' }}>🎓 Exam Strategy</h6>
                                            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{aiExp.exam_tip}</p>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* ⚡ QUICK REVISION BOX — Highlighted */}
                            {aiExp.quick_revision && (
                                <div className="quick-revision-card animate-fadeInUp">
                                    <div className="absolute top-0 left-0 w-full h-1" style={{ background: 'var(--gradient-primary)' }}></div>
                                    <h5 className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--accent-primary)' }}>
                                        <Lightbulb className="w-3.5 h-3.5" /> 📝 Quick Revision — Read Before Exam
                                    </h5>
                                    <p className="text-sm leading-relaxed font-medium" style={{ color: 'var(--text-primary)', lineHeight: '1.7' }}>{aiExp.quick_revision}</p>
                                </div>
                            )}

                            {/* 🔗 Related Concepts */}
                            {aiExp.around_concepts?.length > 0 && (
                                <div className="glass-card p-4">
                                    <h5 className="text-xs font-bold uppercase tracking-wider mb-2.5 flex items-center gap-1.5" style={{ color: '#6366f1' }}>🔗 Related Concepts (Often Asked Together)</h5>
                                    <div className="flex flex-wrap gap-2">
                                        {aiExp.around_concepts.map((c: string, i: number) => (
                                            <span key={i} className="text-xs px-3 py-1.5 rounded-full font-medium" style={{ background: 'rgba(99,102,241,0.08)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.15)' }}>{c}</span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* 📊 PYQ Intelligence */}
                            {(aiExp.pyq_frequency || aiExp.similar_pyq) && (
                                <div className="glass-card p-4">
                                    <h5 className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: '#ec4899' }}>
                                        <Target className="w-3.5 h-3.5" /> 📊 PYQ Intelligence
                                    </h5>
                                    {aiExp.pyq_frequency && <p className="text-sm mb-1.5" style={{ color: 'var(--text-secondary)' }}>📈 <strong style={{ color: '#ec4899' }}>Frequency:</strong> {decodeMojiB(aiExp.pyq_frequency)}</p>}
                                    {aiExp.similar_pyq && <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>📋 <strong style={{ color: '#818cf8' }}>Similar Questions:</strong> {decodeMojiB(aiExp.similar_pyq)}</p>}
                                </div>
                            )}

                            {/* Retry button if AI failed */}
                            {!aiExp.mnemonic && !aiExp.why_correct && (
                                <button onClick={() => { setReviewAiExplanations(prev => { const next = {...prev}; delete next[reviewIdx]; return next; }); fetchAiExplanation(reviewIdx); }}
                                    className="btn-secondary w-full justify-center text-sm">
                                    <Brain className="w-4 h-4" /> Retry AI Analysis
                                </button>
                            )}
                        </div>
                    )}

                    {/* ═══ NAVIGATION ═══ */}
                    <div className="flex items-center justify-between py-4 sticky bottom-0 bg-background">
                        <button onClick={() => setReviewIdx(Math.max(0, reviewIdx - 1))} disabled={reviewIdx <= 0}
                            className="btn-secondary px-5 py-2.5" style={{ opacity: reviewIdx <= 0 ? 0.4 : 1 }}>
                            <ChevronLeft className="w-4 h-4" /> Previous
                        </button>
                        <div className="text-center">
                            <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{reviewIdx + 1}</span>
                            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}> / {questions.length}</span>
                        </div>
                        <button onClick={() => setReviewIdx(Math.min(questions.length - 1, reviewIdx + 1))} disabled={reviewIdx >= questions.length - 1}
                            className="btn-primary px-5 py-2.5" style={{ opacity: reviewIdx >= questions.length - 1 ? 0.4 : 1 }}>
                            Next <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
            {zoomImg && (
                <ImageViewer
                    // The figures this review question shows (question side, then explanation).
                    images={zoomFigures.map(img => ({
                        id: img.id,
                        file_url: figureSrc(img),
                        caption: img.caption,
                        modality: img.modality,
                        modality_subtype: img.modality_subtype,
                        page_number: img.page_number,
                        image_index_in_page: img.image_index_in_page,
                        has_diagram: img.has_diagram,
                        has_table: img.has_table,
                        width: img.width,
                        height: img.height,
                    }))}
                    startIndex={Math.max(0, zoomFigures.findIndex(i => i.id === zoomImg.id))}
                    open={!!zoomImg}
                    onClose={() => setZoomImg(null)}
                />
            )}
            </>
        );
    }

    // ─── RESULTS SCREEN ─────────────────────────────────
    if (submitted && result) {
        const resultNote = [
            storedResult
                ? 'This attempt had already been submitted, so your saved result is shown.'
                : expiredOnLoad
                    ? 'Time had run out on this attempt, so it was submitted with the answers saved on this device.'
                    : '',
            // The server flags submits past the time limit (plus a short grace).
            result.is_late === true
                ? 'It was submitted after the time limit, so it earns no XP and does not count towards the leaderboard.'
                : '',
        ].filter(Boolean).join(' ');
        return (
            <div className="min-h-screen flex items-center justify-center p-4 sm:p-8 bg-background">
                <div className="glass-card p-5 sm:p-8 max-w-lg w-full text-center animate-fadeInUp">
                    <CheckCircle className="w-16 h-16 mx-auto mb-4" style={{ color: '#10b981' }} aria-hidden="true" />
                    <h1 className="text-2xl font-bold mb-2">Test Completed!</h1>
                    <p className={resultNote ? 'mb-3' : 'mb-6'} style={{ color: 'var(--text-secondary)' }}>{test?.title}</p>
                    {resultNote && (
                        <p role="status" className="mb-6 text-sm rounded-lg px-3 py-2 bg-amber-500/10 text-amber-700 dark:text-amber-300">
                            {resultNote}
                        </p>
                    )}

                    <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-6">
                        <div className="stat-card text-center">
                            <div className="text-2xl font-bold" style={{ color: '#10b981' }}>{String(result.correct_count)}</div>
                            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Correct</div>
                        </div>
                        <div className="stat-card text-center">
                            <div className="text-2xl font-bold" style={{ color: '#ef4444' }}>{String(result.incorrect_count)}</div>
                            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Incorrect</div>
                        </div>
                        <div className="stat-card text-center">
                            <div className="text-2xl font-bold" style={{ color: '#f59e0b' }}>{String(result.unanswered_count)}</div>
                            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Unanswered</div>
                        </div>
                    </div>

                    <div className="text-4xl font-bold gradient-text mb-2">{String(result.accuracy)}%</div>
                    <div className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
                        Score: {String(result.score)} / {String(result.total_marks)}
                    </div>

                    <div className="flex gap-3">
                        <button onClick={() => { setReviewIdx(0); setReviewMode(true); }} className="btn-primary flex-1 justify-center">
                            <Eye className="w-4 h-4" /> Review Answers
                        </button>
                    </div>
                    <div className="flex gap-3 mt-3">
                        <button onClick={() => router.push('/tests')} className="btn-secondary flex-1">Back to Tests</button>
                        <button onClick={() => router.push('/dashboard')} className="btn-secondary flex-1">Dashboard</button>
                    </div>
                </div>
            </div>
        );
    }

    const currentQ = questions[currentIdx];
    if (!currentQ) return null;

    const handleSaveAndNext = () => goTo(Math.min(questions.length - 1, currentIdx + 1));

    const handleMarkAndNext = () => {
        setMarked(prev => { const next = new Set(prev); next.add(currentIdx); return next; });
        goTo(Math.min(questions.length - 1, currentIdx + 1));
    };

    const handleClear = () => {
        setAnswers(prev => { const next = { ...prev }; delete next[currentQ.id]; return next; });
    };

    const examLabel = EXAM_LABELS[test?.exam_type || 'cms'] || EXAM_LABELS.cms;
    const answeredCount = Object.keys(answers).length;
    // Legend counts mirror the palette colours, so they add up to the total:
    // answered (green), marked and unanswered (purple), visited and
    // unanswered (red), never opened (grey). Every visited question has a
    // startTimes entry, including the current one.
    const visitedCount = Object.keys(startTimes.current).length;
    const markedCount = Array.from(marked).filter(i => questions[i] && !answers[questions[i].id]).length;
    const notVisitedCount = Math.max(0, questions.length - visitedCount);
    const notAnsweredVisitedCount = Math.max(0, visitedCount - answeredCount - markedCount);
    // Everything unanswered, visited or not (Submit dialog).
    const notAnsweredCount = questions.length - answeredCount;

    return (
        <div className="min-h-screen flex flex-col bg-background lg:overflow-hidden lg:h-screen">
            {/* Confirm Dialog */}
            {submitError && !showConfirm && (
                <div role="alert" className="fixed bottom-4 left-1/2 z-100 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 rounded-xl border border-destructive/40 bg-card p-4 shadow-lg">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 shrink-0 text-destructive" aria-hidden="true" />
                        <div className="flex-1 text-sm">
                            <p className="font-semibold text-foreground">Your test was not submitted</p>
                            <p className="text-muted-foreground">{submitError} Your answers are still here.</p>
                        </div>
                    </div>
                    <div className="mt-3 flex justify-end gap-2">
                        <button onClick={() => setSubmitError(null)} className="btn-secondary">Dismiss</button>
                        <button onClick={doSubmit} disabled={submitting} className="btn-primary justify-center disabled:opacity-60">
                            {submitting ? 'Submitting…' : 'Retry submit'}
                        </button>
                    </div>
                </div>
            )}

            {submitLocked && !showConfirm && (
                <div role="alert" className="fixed bottom-4 left-1/2 z-100 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 rounded-xl border border-primary/40 bg-card p-4 shadow-lg">
                    <div className="flex items-start gap-3">
                        <Lock className="w-5 h-5 shrink-0 text-primary" aria-hidden="true" />
                        <div className="flex-1 text-sm">
                            <p className="font-semibold text-foreground">Premium is needed to submit this test</p>
                            <p className="text-muted-foreground">
                                {submitLocked.message || 'This test includes questions from the premium question bank.'} Your answers are saved on this device.
                            </p>
                        </div>
                    </div>
                    <div className="mt-3 flex justify-end gap-2">
                        <button onClick={() => setSubmitLocked(null)} className="btn-secondary">Dismiss</button>
                        <button onClick={() => showPaywall(submitLocked.feature)} className="btn-primary justify-center">
                            Unlock with Premium
                        </button>
                    </div>
                </div>
            )}

            {lostAttemptId && !submitError && !submitLocked && !showConfirm && (
                <div role="status" className="fixed bottom-4 left-1/2 z-100 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 rounded-xl border border-amber-500/40 bg-card p-4 shadow-lg">
                    <div className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                        <div className="flex-1 text-sm">
                            <p className="font-semibold text-foreground">Your last attempt was submitted</p>
                            <p className="text-muted-foreground">Its result did not reach this device. You can still see it.</p>
                        </div>
                    </div>
                    <div className="mt-3 flex justify-end gap-2">
                        <button onClick={dismissLostResult} className="btn-secondary">Dismiss</button>
                        <button onClick={viewLostResult} disabled={lostAttemptLoading} className="btn-primary justify-center disabled:opacity-60">
                            {lostAttemptLoading ? 'Loading…' : 'View result'}
                        </button>
                    </div>
                </div>
            )}

            {showConfirm && (
                <div className="fixed inset-0 z-100 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
                    <div role="dialog" aria-modal="true" aria-labelledby="submit-test-title" className="glass-card p-8 max-w-sm w-full mx-4 text-center animate-fadeInUp">
                        <AlertTriangle className="w-12 h-12 mx-auto mb-4" style={{ color: '#f59e0b' }} aria-hidden="true" />
                        <h3 id="submit-test-title" className="text-xl font-bold mb-2">Submit Test?</h3>
                        <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                            You have answered <strong style={{ color: 'var(--text-primary)' }}>{answeredCount}</strong> of <strong style={{ color: 'var(--text-primary)' }}>{questions.length}</strong> questions.
                        </p>
                        {notAnsweredCount > 0 && (
                            <p className="text-sm mb-6" style={{ color: '#f59e0b' }}>
                                {notAnsweredCount} question{notAnsweredCount > 1 ? 's' : ''} unanswered!
                            </p>
                        )}
                        <div className="flex gap-3">
                            <button onClick={() => setShowConfirm(false)} disabled={submitting} className="btn-secondary flex-1">Go Back</button>
                            <button onClick={doSubmit} disabled={submitting} className="btn-primary flex-1 justify-center disabled:opacity-60" style={{ background: '#10b981' }}>
                                <Send className="w-4 h-4" aria-hidden="true" /> {submitting ? 'Submitting…' : 'Confirm'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Top Bar — one row on phones: the title chip is hidden there
                (the test card in the right rail shows it) and nothing wraps. */}
            <div className="sticky top-0 z-50 px-3 sm:px-6 py-3 flex items-center justify-between gap-3"
                style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                <div className="flex items-center gap-4 min-w-0">
                    <div className="font-bold text-base sm:text-lg gradient-text whitespace-nowrap">{examLabel.toUpperCase()} SIMULATOR</div>
                    <div className="hidden sm:block truncate max-w-[40vw] text-sm px-3 py-1 rounded-full" style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)' }}>{test?.title}</div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                    <div className={`flex items-center gap-2 font-mono text-lg sm:text-xl font-bold whitespace-nowrap px-2 sm:px-4 py-2 rounded-lg ${timeLeft < 300 ? 'animate-pulse' : ''}`}
                        style={{ background: timeLeft < 300 ? 'rgba(239,68,68,0.15)' : 'var(--bg-card)', color: timeLeft < 300 ? '#ef4444' : 'var(--text-primary)' }}>
                        ⏱ {formatTime(timeLeft)}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col lg:flex-row max-w-400 mx-auto w-full p-4 gap-4 lg:h-[calc(100vh-70px)] lg:overflow-hidden">

                {/* Left: Question */}
                <div className="flex-1 glass-card flex flex-col lg:h-full lg:overflow-hidden">
                    <div className="px-6 py-3 flex justify-between items-center shrink-0" style={{ borderBottom: '1px solid var(--glass-border)', background: 'var(--bg-secondary)' }}>
                        <span className="font-bold text-lg">Question {currentIdx + 1}</span>
                        <div className="flex gap-2 text-sm">
                            <span className="badge" style={{ background: 'rgba(6,182,212,0.1)', color: 'var(--accent-primary)' }}>{currentQ.subject_name}</span>
                            {currentQ.topic_name && <span className="badge" style={{ background: 'rgba(139,92,246,0.1)', color: 'var(--accent-secondary)' }}>{currentQ.topic_name}</span>}
                            {currentQ.year ? <span className="badge" style={{ background: 'rgba(236,72,153,0.1)', color: '#ec4899' }}>PYQ {currentQ.year}</span> : null}
                        </div>
                    </div>

                    <div className="p-8 flex-1 overflow-y-auto" style={{ minHeight: '300px' }}>
                        <div className="text-lg leading-relaxed font-medium mb-10 pb-6" style={{ borderBottom: '1px solid var(--glass-border)' }}>
                            <FormattedText text={currentQ.question_text} />
                        </div>
                        {/* Images — prefer the backend-filtered `stem_images`
                            (excludes role='explanation') so admin-uploaded
                            explanation figures do not appear next to the
                            question stem before the student attempts it.
                            Falls back to filtering `images` ourselves for
                            legacy rows. The full `images` array is still
                            passed to `<FormattedText>` for `[[img:N]]`
                            token resolution. */}
                        {((Array.isArray(currentQ?.stem_images) && currentQ.stem_images.length > 0)
                          || (Array.isArray(currentQ?.images) && currentQ.images.some((img: any) => img.role !== 'explanation'))) && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
                                {(Array.isArray(currentQ?.stem_images) && currentQ.stem_images.length > 0
                                    ? currentQ.stem_images
                                    : (currentQ?.images || []).filter((img: any) => img.role !== 'explanation')
                                ).map(img => (
                                    <button
                                        key={img.id}
                                        type="button"
                                        onClick={() => setZoomImg(img)}
                                        className="relative group rounded-lg overflow-hidden border border-slate-200 bg-white transition-all hover:shadow-lg hover:border-(--accent-primary) focus:outline-none"
                                    >
                                        <FigureImage
                                            src={figureSrc(img)}
                                            alt={img.caption || `Question figure`}
                                            loading="lazy"
                                            className="w-full h-auto object-contain bg-white max-h-105"
                                        />
                                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-linear-to-t from-black/60 to-transparent transition-opacity flex items-end p-3">
                                            <span className="text-white text-xs flex items-center gap-1">
                                                <ZoomIn className="w-3.5 h-3.5" /> Tap to zoom
                                            </span>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                        <div className="space-y-3 max-w-3xl">
                            {['A', 'B', 'C', 'D'].map(opt => {
                                const optionText = currentQ[`option_${opt.toLowerCase()}` as keyof Question] || currentQ[`option_${opt}` as keyof Question];
                                if (!optionText) return null;
                                const isSelected = answers[currentQ.id] === opt;
                                return (
                                    <div key={opt}
                                        className="flex items-center gap-4 p-4 rounded-xl cursor-pointer transition-all border-2"
                                        style={{
                                            borderColor: isSelected ? 'var(--accent-primary)' : 'var(--glass-border)',
                                            background: isSelected ? 'rgba(6,182,212,0.08)' : 'var(--bg-secondary)',
                                        }}
                                        onClick={() => selectAnswer(opt)}>
                                        <div className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm shrink-0"
                                            style={{ background: isSelected ? 'var(--accent-primary)' : 'var(--bg-card)', color: isSelected ? 'white' : 'var(--text-secondary)' }}>
                                            {opt}
                                        </div>
                                        <div className="font-medium">{String(optionText)}</div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Wraps to two rows on phones ([Clear, Mark & Next] then
                        [Prev, Save & Next]) instead of squeezing four buttons. */}
                    <div className="px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-3 shrink-0" style={{ borderTop: '1px solid var(--glass-border)', background: 'var(--bg-secondary)' }}>
                        <div className="flex gap-3">
                            <button onClick={handleClear} className="btn-secondary text-sm">Clear</button>
                            <button onClick={handleMarkAndNext} className="text-sm px-4 py-2 rounded-lg font-semibold transition-colors whitespace-nowrap"
                                style={{ background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)' }}>
                                Mark & Next
                            </button>
                        </div>
                        <div className="flex gap-3 ml-auto">
                            <button onClick={() => goTo(Math.max(0, currentIdx - 1))} disabled={currentIdx === 0} className="btn-secondary text-sm inline-flex items-center gap-2">
                                <ChevronLeft className="w-4 h-4" /> Prev
                            </button>
                            <button onClick={handleSaveAndNext} className="btn-primary text-sm whitespace-nowrap">
                                Save & Next <ChevronRight className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right Sidebar */}
                <div className="w-full lg:w-72 flex flex-col gap-4 lg:h-full lg:overflow-hidden shrink-0">
                    <div className="glass-card p-4 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                            {test?.title.charAt(0)}
                        </div>
                        <div>
                            <div className="font-bold text-sm">{test?.title}</div>
                            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{examLabel} Mock</div>
                        </div>
                    </div>

                    <div className="glass-card p-4">
                        <div className="font-bold text-sm mb-3">Legend</div>
                        <div className="grid grid-cols-2 gap-y-3 gap-x-2 text-xs font-semibold">
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs" style={{ background: '#10b981' }}>{answeredCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Answered</span></div>
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs" style={{ background: '#ef4444' }}>{notAnsweredVisitedCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Not Answered</span></div>
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-xs" style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)', border: '1px solid var(--glass-border)' }}>{notVisitedCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Not Visited</span></div>
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs" style={{ background: '#8b5cf6' }}>{markedCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Marked</span></div>
                        </div>
                    </div>

                    <div className="glass-card p-4 flex-1 flex flex-col min-h-55 lg:overflow-hidden">
                        <div className="font-bold text-sm mb-3 flex justify-between items-center shrink-0">
                            <span>Question Palette</span>
                            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{questions.length} Qs</span>
                        </div>
                        <div className="flex flex-col gap-2 shrink-0">
                            {/* Page Tabs */}
                            {questions.length > 30 && (
                                <div className="flex flex-wrap gap-1 border-b pb-2 border-glass-border">
                                    {Array.from({ length: Math.ceil(questions.length / 30) }).map((_, pIdx) => (
                                        <button
                                            key={pIdx}
                                            onClick={() => setPalettePage(pIdx)}
                                            className={`text-[9px] font-bold px-1.5 py-1 rounded transition-colors flex-1 text-center ${
                                                palettePage === pIdx
                                                    ? 'bg-primary text-primary-foreground'
                                                    : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                                            }`}
                                        >
                                            {pIdx * 30 + 1}-{Math.min((pIdx + 1) * 30, questions.length)}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div className="flex-1 overflow-y-auto pr-1">
                            <div className="grid grid-cols-6 sm:grid-cols-10 lg:grid-cols-6 gap-1.5 pt-1.5 pb-1">
                                {questions.slice(palettePage * 30, (palettePage + 1) * 30).map((q, localIdx) => {
                                    const i = palettePage * 30 + localIdx;
                                    const answered = !!answers[q.id];
                                    const isMarked = marked.has(i);
                                    const isCurrent = i === currentIdx;
                                    let bg = 'var(--bg-card)'; let color = 'var(--text-secondary)'; let border = 'var(--glass-border)';
                                    if (answered) { bg = '#10b981'; color = 'white'; border = '#059669'; }
                                    else if (isMarked) { bg = '#8b5cf6'; color = 'white'; border = '#7c3aed'; }
                                    else if (startTimes.current[i]) { bg = '#ef4444'; color = 'white'; border = '#dc2626'; }
                                    return (
                                        <button key={i} onClick={() => goTo(i)}
                                            className="w-full aspect-square rounded flex items-center justify-center text-[11px] font-bold transition-all"
                                            style={{ background: bg, color, border: `2px solid ${border}`, outline: isCurrent ? '2px solid var(--accent-primary)' : 'none', outlineOffset: '2.5px', transform: isCurrent ? 'scale(1.05)' : 'none' }}>
                                            {i + 1}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <div className="mt-4 pt-4 shrink-0" style={{ borderTop: '1px solid var(--glass-border)' }}>
                            <button onClick={handleSubmit}
                                className="w-full py-3 rounded-lg font-bold text-lg flex justify-center items-center gap-2 transition-colors active:scale-98"
                                style={{ background: '#10b981', color: 'white' }}>
                                <Send className="w-5 h-5" /> Submit Test
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {zoomImg && (
                <ImageViewer
                    images={(questions[currentIdx]?.images || []).map(img => ({
                        id: img.id,
                        file_url: figureSrc(img),
                        caption: img.caption,
                        modality: img.modality,
                        modality_subtype: img.modality_subtype,
                        page_number: img.page_number,
                        image_index_in_page: img.image_index_in_page,
                        has_diagram: img.has_diagram,
                        has_table: img.has_table,
                        width: img.width,
                        height: img.height,
                    }))}
                    startIndex={questions[currentIdx]?.images?.findIndex(i => i.id === zoomImg.id) || 0}
                    open={!!zoomImg}
                    onClose={() => setZoomImg(null)}
                />
            )}
        </div>
    );
}
