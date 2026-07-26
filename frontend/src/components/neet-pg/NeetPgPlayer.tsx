/**
 * NeetPgPlayer — dedicated premium medical question player for NEET PG.
 *
 * Independent of the UPSC CMS practice page. Key differentiators:
 *   - Medical teal/emerald colour palette (vs. CMS blue).
 *   - Image-first design: large image viewer panel + AIIMS-style preamble.
 *   - AI assistant panel docked on the right (desktop) / collapsible (mobile).
 *   - Related PYQs sidebar with sha-normalised similarity groups.
 *   - Sticky answer palette + exam progress bar.
 *   - Greek letters, sub/superscripts, micro (µ) all preserved via
 *     FormattedText (react-markdown).
 *
 * Routing: `/questions/neet-pg/practice?year=2025&subject=Anatomy`
 *          optional ?bookmarked=1 or ?q=<id> to jump to a single question.
 */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable react-hooks/exhaustive-deps */
/* eslint-disable @next/next/no-img-element */
'use client';
import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
    ChevronLeft, ChevronRight, Loader2, Brain, Sparkles,
    CheckCircle2, X as XIcon, Bookmark, BookmarkCheck, ArrowLeft,
    Target, Lightbulb, Flag, FlagOff, Image as ImageIcon,
    ZoomIn, ZoomOut, Maximize2, Stethoscope, Pill, FlaskConical,
    AlertTriangle, Eye, EyeOff, Pin, PinOff, Highlighter,
    Clock, ChevronDown, ChevronUp, Activity, HeartPulse,
    BookOpen, LayoutGrid, Filter,
} from 'lucide-react';
import { questionsAPI, aiAPI } from '@/lib/api';
import { FormattedText } from '@/components/FormattedText';
import { cleanOptionText, extractAnalysisFromJson, extractLeakedOptions, isLikelyGarbled, nonPlaceholderExplanation, safeDisplayText, sanitizeQuestionText, sanitizeOptionText } from '@/lib/textCleanup';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import AiTutorPanel from '@/components/ai/AiTutorPanel';
import ImageViewer from '@/components/image/ImageViewer';

interface Option { label: string; text: string; }
interface QuestionImage {
    id: number;
    page_number: number;
    image_index_in_page: number;
    file_url: string | null;
    mime: string;
    width: number;
    height: number;
    modality: string;
    modality_subtype: string;
    caption: string;
    has_diagram: boolean;
    has_table: boolean;
}
interface Question {
    id: number;
    question_text: string;
    option_a?: string | null;
    option_b?: string | null;
    option_c?: string | null;
    option_d?: string | null;
    correct_answer?: string | null;
    year?: number;
    difficulty?: string;
    is_image_based?: boolean;
    explanation?: string;
    subject?: { id?: number; name?: string } | string | null;
    topic?: string;
    is_high_yield?: boolean;
    is_clinical_case?: boolean;
    times_asked?: number;
    exam_type?: string;
    pdf_filename?: string;
    // PHASE 2 (2026-07-25): extended fields surfaced by QuestionDetailSerializer.
    // All optional — the player works fine when these are absent.
    concept_explanation?: string;
    mnemonic?: string;
    book_name?: string;
    chapter?: string;
    page_number?: string | number;
    reference_text?: string;
    textbook_references?: Array<Record<string, unknown>>;
    ai_explanation?: string;
    ai_mnemonic?: string;
    ai_references?: Array<Record<string, unknown>>;
    concept_keywords?: string[];
    learning_technique?: string;
    is_verified_by_admin?: boolean;
    verified_by?: string;
    verified_at?: string;
    effective_explanation?: string;
    effective_mnemonic?: string;
    effective_references?: Array<Record<string, unknown>>;
}
interface PlayerState {
    index: number;
    selected: string | null;
    showAnswer: boolean;
    flagged: boolean;
    bookmarked: boolean;
    notes: string;
    aiLoading: boolean;
    aiExplanation: string | null;
    aiError: string | null;
}

const SCORE_CORRECT = 4;
const SCORE_WRONG = -1;

// PHASE 5 — Similar PYQ reason labels (2026-07-25). Each item in the
// "Similar PYQs" sidebar carries a `similarity_reason` from the API.
// We render a coloured badge + a tooltip so the user understands WHY
// each question is being recommended.
const SIM_REASON_LABEL: Record<string, string> = {
    curated: 'Curated',
    same_concept: 'Same concept',
    same_image: 'Same image',
    same_topic: 'Same topic',
    same_subject: 'Same subject',
};
const SIM_REASON_TITLE: Record<string, string> = {
    curated: 'Listed in the curated "similar questions" set by an admin',
    same_concept: 'Tests the same underlying medical concept (concept_id match)',
    same_image: 'Shares the same diagram or photo (sha256 fingerprint match)',
    same_topic: 'Tests the same topic but a different concept',
    same_subject: 'Tests the same subject — broader fallback',
};

function difficultyTone(d?: string): 'easy' | 'medium' | 'hard' | 'unknown' {
    const s = (d || '').toLowerCase();
    if (s.includes('easy')) return 'easy';
    if (s.includes('hard')) return 'hard';
    if (s.includes('med') || s.includes('mod')) return 'medium';
    return 'unknown';
}

const TONE: Record<'easy' | 'medium' | 'hard' | 'unknown', string> = {
    easy: 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-300',
    medium: 'bg-amber-100 text-amber-700 ring-1 ring-amber-300',
    hard: 'bg-rose-100 text-rose-700 ring-1 ring-rose-300',
    unknown: 'bg-slate-100 text-slate-700 ring-1 ring-slate-300',
};

export default function NeetPgPlayer({
    questions,
    initialIndex = 0,
    title = 'NEET PG Practice',
    onExit,
    hasMore = false,
    loadingMore = false,
    onLoadMore,
    rateLimited = false,
    onRetry,
}: {
    questions: Question[];
    initialIndex?: number;
    title?: string;
    onExit?: () => void;
    /** PRODUCTION-INCIDENT FIX (2026-07-25): the page only fetches the
     *  first 20 questions up-front. When the user reaches near the end
     *  of `questions` (or jumps via the palette past `questions.length`)
     *  the player calls `onLoadMore()` to fetch the next page from the
     *  parent. This stops the previous "fetch 200 pages sequentially"
     *  loop that triggered 429s on production. */
    hasMore?: boolean;
    loadingMore?: boolean;
    onLoadMore?: () => Promise<void> | void;
    /** True when the parent has been rate-limited (HTTP 429). When true,
     *  the Next button shows a retry UI instead of silently failing. */
    rateLimited?: boolean;
    onRetry?: () => void;
}) {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [state, setState] = useState<PlayerState>({
        index: Math.min(Math.max(initialIndex, 0), Math.max(questions.length - 1, 0)),
        selected: null,
        showAnswer: false,
        flagged: false,
        bookmarked: false,
        notes: '',
        aiLoading: false,
        aiExplanation: null,
        aiError: null,
    });
    const [images, setImages] = useState<QuestionImage[]>([]);
    const [paletteOpen, setPaletteOpen] = useState(false);
    const [zoomImg, setZoomImg] = useState<QuestionImage | null>(null);
    const [aiPanelOpen, setAiPanelOpen] = useState(true);
    const [relatedOpen, setRelatedOpen] = useState(true);
    const [related, setRelated] = useState<{ id: number; question_text: string; year?: number; similarity?: number }[]>([]);
    const [score, setScore] = useState({ correct: 0, wrong: 0, flagged: 0 });
    const [pinImagePanel, setPinImagePanel] = useState(true);
    const startedAt = useRef<number>(Date.now());

    const current = questions[state.index];
    const total = questions.length;
    const isLast = state.index >= total - 1;
    const isFirst = state.index <= 0;
    const progress = total ? Math.round(((state.index + 1) / total) * 100) : 0;

    /* Load images + AI for current question */
    useEffect(() => {
        setState(s => ({ ...s, selected: null, showAnswer: false, aiExplanation: null, aiError: null }));
        startedAt.current = Date.now();
        if (!current) { setImages([]); setRelated([]); return; }

        let cancelled = false;
        (async () => {
            try {
                const imgs = await questionsAPI.getImages(current.id);
                if (!cancelled) setImages((imgs.data as QuestionImage[]) || []);
            } catch { if (!cancelled) setImages([]); }
            try {
                const sim = await questionsAPI.getSimilar(current.id);
                if (!cancelled) {
                    const data = (sim.data as any)?.results ?? (sim.data as any) ?? [];
                    setRelated(Array.isArray(data) ? data.slice(0, 8) : []);
                }
            } catch { if (!cancelled) setRelated([]); }
        })();
        return () => { cancelled = true; };
    }, [current?.id]);

    // PRODUCTION-INCIDENT FIX (2026-07-25): when the user is within
    // 5 of the end of what's loaded AND the parent has signalled
    // there's more, fire onLoadMore. This keeps the Next button working
    // without ever pre-fetching the full 200-page backlog.
    useEffect(() => {
        if (!onLoadMore) return;
        if (!hasMore) return;
        if (loadingMore) return;
        if (rateLimited) return;
        if (state.index >= questions.length - 5) {
            onLoadMore();
        }
    }, [state.index, questions.length, hasMore, loadingMore, rateLimited, onLoadMore]);

    /* AI explanation loader */
    const fetchAi = useCallback(async () => {
        if (!current) return;
        setState(s => ({ ...s, aiLoading: true, aiError: null }));
        try {
            const r = await aiAPI.explainQuestion(current.id, {
                selected_answer: state.selected || '',
                question_text: current.question_text,
                correct_answer: current.correct_answer,
                subject: typeof current.subject === 'object' ? current.subject?.name : current.subject,
                topic: current.topic,
            });
            const text = (r as any)?.explanation || (r as any)?.text || (r as any)?.markdown || '';
            setState(s => ({ ...s, aiLoading: false, aiExplanation: text || null }));
        } catch (e: any) {
            setState(s => ({ ...s, aiLoading: false, aiError: e?.message || 'AI failed' }));
        }
    }, [current?.id, current?.question_text, current?.correct_answer, current?.subject, current?.topic, state.selected]);

    const submitAttempt = useCallback(async (choice: string) => {
        if (!current) return;
        setState(s => ({ ...s, selected: choice, showAnswer: true }));
        const correct = (current.correct_answer || '').toUpperCase().trim();
        const isRight = choice.toUpperCase().trim() === correct;
        setScore(s => ({ ...s, correct: s.correct + (isRight ? 1 : 0), wrong: s.wrong + (isRight ? 0 : 1) }));
        try {
            await questionsAPI.attempt(current.id, { selected_answer: choice });
        } catch { /* offline-tolerant */ }
    }, [current?.id]);

    const goNext = useCallback(() => {
        if (state.index < questions.length - 1) {
            setState(s => ({ ...s, index: s.index + 1 }));
            setPaletteOpen(false);
            return;
        }
        // We're at the end of what's loaded. If the parent signalled
        // more pages are available, trigger the next fetch. Otherwise
        // wrap to the start of the loaded list.
        if (hasMore && onLoadMore && !loadingMore && !rateLimited) {
            onLoadMore();
        }
        setPaletteOpen(false);
    }, [state.index, questions.length, hasMore, onLoadMore, loadingMore, rateLimited]);

    const goPrev = useCallback(() => {
        if (isFirst) return;
        setState(s => ({ ...s, index: s.index - 1 }));
    }, [isFirst]);

    /* Keyboard shortcuts */
    useEffect(() => {
        const h = (e: KeyboardEvent) => {
            if ((e.target as HTMLElement)?.tagName?.match(/INPUT|TEXTAREA|SELECT/)) return;
            if (e.key === 'ArrowRight') goNext();
            else if (e.key === 'ArrowLeft') goPrev();
            else if (['a', 'b', 'c', 'd', 'A', 'B', 'C', 'D'].includes(e.key)) {
                const c = e.key.toUpperCase();
                if (state.selected == null) submitAttempt(c);
            } else if (e.key === '?') setPaletteOpen(o => !o);
            else if (e.key === 'f' || e.key === 'F') {
                setState(s => ({ ...s, flagged: !s.flagged }));
            } else if (e.key === 'b' || e.key === 'B') {
                setState(s => ({ ...s, bookmarked: !s.bookmarked }));
            }
        };
        window.addEventListener('keydown', h);
        return () => window.removeEventListener('keydown', h);
    }, [goNext, goPrev, submitAttempt, state.selected]);

    /* Bookmark with API */
    const toggleBookmark = useCallback(async () => {
        if (!current) return;
        setState(s => ({ ...s, bookmarked: !s.bookmarked }));
        try { await questionsAPI.bookmark(current.id); } catch { /* offline-tolerant */ }
    }, [current?.id]);

    /* Exit handler */
    const handleExit = () => {
        if (onExit) onExit();
        else router.push('/questions?exam=neet-pg');
    };

    if (!total) {
        // Empty state lives in the parent route — render a quiet placeholder
        // here so we never pre-commit the empty branch on the server.
        return null;
    }

    // ──────────────────────────────────────────────────────────────────
    // Defence-in-depth (2026-07-26): many NEET PG recall rows were
    // imported with the entire PDF block (stem + options + answer key +
    // explanation) stuffed into `question_text` and the dedicated
    // `option_a..d` columns left empty. When that happens, we have to
    // parse the leaked options out of the stem at render time so the
    // student can still solve the question. `extractLeakedOptions` also
    // captures a leaked "Answer: X" line so we can grade the attempt.
    // ──────────────────────────────────────────────────────────────────
    const rawOptionCols = {
        A: sanitizeOptionText((current as any).option_a),
        B: sanitizeOptionText((current as any).option_b),
        C: sanitizeOptionText((current as any).option_c),
        D: sanitizeOptionText((current as any).option_d),
    };
    const hasColumnOptions = !!(rawOptionCols.A && rawOptionCols.B && rawOptionCols.C && rawOptionCols.D);
    const leaked = !hasColumnOptions ? extractLeakedOptions(current.question_text) : null;
    const optionLabels: string[] = hasColumnOptions
        ? ['A', 'B', 'C', 'D']
        : (leaked?.optionLabels?.length ? leaked.optionLabels : ['A', 'B', 'C', 'D']);
    const optionTexts: Record<'A' | 'B' | 'C' | 'D', string> = hasColumnOptions
        ? rawOptionCols
        : (leaked?.options ?? { A: '', B: '', C: '', D: '' });
    const correctAnswer = ((current.correct_answer || leaked?.correctAnswer || '') as string).toUpperCase().trim();
    const displayStem = hasColumnOptions
        ? sanitizeQuestionText(current.question_text) || ''
        : (leaked?.stem ?? sanitizeQuestionText(current.question_text) ?? '');

    return (
        // `main-content` honours the `body.sidebar-hidden` toggle (see globals.css).
        // The global `.main-content` rule already applies a 260px desktop
        // margin-left to clear the fixed sidebar; on mobile the sidebar is a
        // drawer so no offset is needed.
        <div className="main-content min-h-screen bg-linear-to-br from-teal-50/40 via-white to-emerald-50/40 dark:from-slate-900 dark:via-slate-950 dark:to-slate-900">
            {/* Header */}
            <header className="sticky top-0 z-30 backdrop-blur-xl bg-white/85 dark:bg-slate-900/85 border-b border-teal-100 dark:border-slate-800 shadow-sm">
                <div className="max-w-400 mx-auto px-4 py-3 flex items-center gap-3">
                    <button
                        onClick={handleExit}
                        aria-label="Exit practice"
                        className="p-2 rounded-lg hover:bg-teal-50 transition-colors"
                    >
                        <ArrowLeft className="w-5 h-5 text-teal-700" />
                    </button>
                    <div className="flex items-center gap-2 min-w-0">
                        <Stethoscope className="w-5 h-5 text-teal-600 shrink-0" />
                        <h1 className="text-base sm:text-lg font-bold text-slate-800 truncate">{title}</h1>
                    </div>
                    <div className="ml-auto flex items-center gap-2">
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 font-semibold">
                            Q {state.index + 1} / {total}{hasMore ? '+' : ''}
                        </Badge>
                        <Badge variant="secondary" className="font-semibold">
                            <Activity className="w-3 h-3 mr-1 inline" />
                            Score: {score.correct * SCORE_CORRECT + score.wrong * SCORE_WRONG}
                        </Badge>
                    </div>
                </div>
                <Progress value={progress} className="h-1 rounded-none bg-teal-100" />
            </header>

            <main className="max-w-400 mx-auto px-4 py-6 grid grid-cols-12 gap-4">
                {/* Left: Question + Options — must be order-1 on ALL viewports so
                    students on phones (390px) see the question stem + options
                    ABOVE the AI Tutor / Related PYQs sidebar. The earlier
                    `order-2 lg:order-1` combination buried the question below
                    the fold on mobile, effectively making the product
                    unusable on phones. */}
                <section className={cn(
                    'col-span-12 lg:col-span-7 xl:col-span-8',
                    'order-1',
                )}>
                    {/* Question card */}
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl shadow-teal-900/5 dark:shadow-black/30 border border-teal-100/60 dark:border-slate-800 overflow-hidden">
                        {/* Top badges */}
                        <div className="px-6 py-3 bg-linear-to-r from-teal-50/40 via-emerald-50/30 to-white dark:from-slate-800/60 dark:via-slate-800/40 dark:to-slate-900 border-b border-teal-100 dark:border-slate-800 flex flex-wrap items-center gap-2 text-xs">
                            {current.subject && (
                                <Badge className="bg-teal-600 text-white font-semibold border-teal-700">
                                    <Pill className="w-3 h-3 mr-1" />
                                    {typeof current.subject === 'object' ? current.subject.name : current.subject}
                                </Badge>
                            )}
                            {current.year ? (
                                <Badge variant="outline" className="border-teal-300 text-teal-800 font-semibold">
                                    <Clock className="w-3 h-3 mr-1" /> NEET PG {current.year}
                                </Badge>
                            ) : null}
                            <Badge className={cn('font-semibold border-0', TONE[difficultyTone(current.difficulty)])}>
                                {difficultyTone(current.difficulty).toUpperCase()}
                            </Badge>
                            {current.is_high_yield && (
                                <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300 font-semibold">
                                    <FlaskConical className="w-3 h-3 mr-1" /> High-Yield
                                </Badge>
                            )}
                            {current.is_clinical_case && (
                                <Badge className="bg-purple-100 text-purple-800 border-purple-300 font-semibold">
                                    <HeartPulse className="w-3 h-3 mr-1" /> Clinical Case
                                </Badge>
                            )}
                            {(current.is_image_based || images.length > 0) && (
                                <Badge className="bg-sky-100 text-sky-800 border-sky-300 font-semibold">
                                    <ImageIcon className="w-3 h-3 mr-1" /> Image-based
                                </Badge>
                            )}
                            {current.topic && (
                                <Badge variant="secondary" className="font-semibold">
                                    <Target className="w-3 h-3 mr-1" /> {current.topic}
                                </Badge>
                            )}
                            <div className="ml-auto flex items-center gap-1">
                                <button
                                    onClick={() => setState(s => ({ ...s, flagged: !s.flagged }))}
                                    aria-pressed={state.flagged}
                                    title="Flag for review (F)"
                                    className={cn(
                                        'p-2 rounded-lg transition-colors',
                                        state.flagged ? 'bg-amber-100 text-amber-700' : 'text-slate-400 hover:bg-slate-100',
                                    )}
                                >
                                    {state.flagged ? <Flag className="w-4 h-4" /> : <FlagOff className="w-4 h-4" />}
                                </button>
                                <button
                                    onClick={toggleBookmark}
                                    aria-pressed={state.bookmarked}
                                    title="Bookmark (B)"
                                    className={cn(
                                        'p-2 rounded-lg transition-colors',
                                        state.bookmarked ? 'bg-teal-100 text-teal-700' : 'text-slate-400 hover:bg-slate-100',
                                    )}
                                >
                                    {state.bookmarked ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        {/* Image viewer */}
                        {images.length > 0 && (
                            <div className="px-6 py-4 bg-slate-50 border-b border-slate-100">
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                                        <ImageIcon className="w-3.5 h-3.5" /> {images.length} {images.length === 1 ? 'Image' : 'Images'}
                                    </h3>
                                    <button
                                        onClick={() => setPinImagePanel(p => !p)}
                                        className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1"
                                        aria-pressed={pinImagePanel}
                                    >
                                        {pinImagePanel ? <Pin className="w-3.5 h-3.5" /> : <PinOff className="w-3.5 h-3.5" />}
                                        {pinImagePanel ? 'Pinned' : 'Unpinned'}
                                    </button>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {images.map(img => (
                                        <button
                                            key={img.id}
                                            type="button"
                                            onClick={() => setZoomImg(img)}
                                            className="relative group rounded-lg overflow-hidden border border-slate-200 bg-white hover:border-teal-400 transition-all hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                                        >
                                            {img.file_url ? (
                                                <img
                                                    src={img.file_url}
                                                    alt={img.caption || `Question ${current.id} image`}
                                                    loading="lazy"
                                                    className="w-full h-auto object-contain bg-white max-h-105"
                                                />
                                            ) : (
                                                <div className="aspect-video flex items-center justify-center text-slate-400">
                                                    <ImageIcon className="w-10 h-10" />
                                                </div>
                                            )}
                                            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-linear-to-t from-black/60 to-transparent transition-opacity flex items-end p-3">
                                                <span className="text-white text-xs flex items-center gap-1">
                                                    <ZoomIn className="w-3.5 h-3.5" /> Tap to zoom
                                                </span>
                                            </div>
                                            {img.modality && img.modality !== 'other' && (
                                                <div className="absolute top-2 left-2">
                                                    <Badge className="bg-white/90 text-slate-700 border-slate-300 text-[10px] uppercase">
                                                        {img.modality}
                                                    </Badge>
                                                </div>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Stem */}
                        <div className="px-6 py-6">
                            <div className="prose prose-slate dark:prose-invert max-w-none text-slate-800 dark:text-slate-100 leading-relaxed text-[15px]">
                                <FormattedText text={displayStem} />
                            </div>
                        </div>

                        {/* Options */}
                        <div className="px-6 pb-6">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                                Choose the correct option
                            </h3>
                            <div className="grid grid-cols-1 gap-3">
                                {(['A', 'B', 'C', 'D'] as const).map((key, idx) => {
                                    const raw = optionTexts[key];
                                    const cleanedRaw = sanitizeOptionText(raw);
                                    if (!cleanedRaw || !cleanedRaw.trim()) return null;
                                    const label = optionLabels[idx] || key;
                                    const isSelected = state.selected === key;
                                    const isCorrect = state.showAnswer && correctAnswer === key;
                                    const isWrong = state.showAnswer && isSelected && !isCorrect;
                                    return (
                                        <button
                                            key={key}
                                            type="button"
                                            disabled={state.showAnswer}
                                            onClick={() => submitAttempt(key)}
                                            className={cn(
                                                'group flex items-start gap-3 p-4 rounded-xl border text-left transition-all',
                                                'hover:shadow-md focus:outline-none focus:ring-2 focus:ring-teal-500',
                                                isCorrect && 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 ring-2 ring-emerald-300 dark:ring-emerald-700',
                                                isWrong && 'border-rose-400 bg-rose-50 dark:bg-rose-950/40',
                                                !isCorrect && !isWrong && isSelected && 'border-teal-500 bg-teal-50 dark:bg-teal-950/40',
                                                !isCorrect && !isWrong && !isSelected && 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-teal-300 dark:hover:border-teal-500',
                                            )}
                                            data-testid={`option-${key}`}
                                            aria-label={`Option ${label}`}
                                        >
                                            <span className={cn(
                                                'w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm shrink-0 transition-all',
                                                isCorrect ? 'bg-emerald-600 text-white' :
                                                    isWrong ? 'bg-rose-500 text-white' :
                                                        isSelected ? 'bg-teal-600 text-white' :
                                                            'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-200 group-hover:bg-teal-100 dark:group-hover:bg-teal-900 group-hover:text-teal-700 dark:group-hover:text-teal-300',
                                            )}>
                                                {isCorrect ? <CheckCircle2 className="w-4 h-4" /> :
                                                    isWrong ? <XIcon className="w-4 h-4" /> :
                                                        label}
                                            </span>
                                            <span className="flex-1 text-slate-800 dark:text-slate-100 text-[14px] leading-relaxed">
                                                <FormattedText text={cleanOptionText(cleanedRaw) || ''} />
                                            </span>
                                        </button>
                                    );
                                })}
                                {optionTexts.A && !optionTexts.B && (
                                    <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                                        Some options for this question are missing in the question bank. Submit what you can.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* PHASE 2 — Detailed explanations panel (2026-07-25).
                            Renders ALL available explanation fields from the
                            QuestionDetailSerializer: explanation,
                            concept_explanation, mnemonic, ai_explanation,
                            ai_mnemonic, ai_references, learning_technique,
                            textbook_references, book_name/chapter/page_number,
                            reference_text, and concept_keywords. Only the
                            sections with data are rendered — keeps the panel
                            clean when the AI enrichment hasn't run yet. */}
                        {state.showAnswer && (
                            <div
                                role="region"
                                aria-label="Detailed explanation"
                                className="border-t border-emerald-200 bg-linear-to-br from-emerald-50/60 via-white to-teal-50/40 px-6 py-5 space-y-4"
                            >
                                {/* Why correct answer */}
                                {(() => {
                                    // Order matters:
                                    //   1. The user's just-clicked AI output
                                    //      (state.aiExplanation).
                                    //   2. The serializer's effective_explanation,
                                    //      which already prefers admin overrides
                                    //      and parsed-JSON AI output.
                                    //   3. The plain `explanation` column.
                                    // The raw `ai_explanation` field is INTENTIONALLY
                                    // NOT in the chain — when an admin has run
                                    // `force-regenerate` the field contains a
                                    // placeholder string ("Regenerated AI
                                    // explanation placeholder.") that we never
                                    // want to render verbatim. Filter any
                                    // remaining placeholder through
                                    // nonPlaceholderExplanation() as a defence.
                                    const expText = nonPlaceholderExplanation(state.aiExplanation)
                                        || nonPlaceholderExplanation((current as { effective_explanation?: string }).effective_explanation)
                                        || nonPlaceholderExplanation(current.explanation);
                                    if (expText) {
                                        return (
                                            <section data-testid="expl-why-correct">
                                                <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-700 mb-2 flex items-center gap-1.5">
                                                    <Lightbulb className="w-4 h-4" /> Why the correct answer is right
                                                </h3>
                                                <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed">
                                                    <FormattedText text={extractAnalysisFromJson(expText)} />
                                                </div>
                                            </section>
                                        );
                                    }
                                    // Fallback for the recall batch where the explanation
                                    // field hasn't been populated yet. The student must
                                    // at least see the correct answer + a hint that the
                                    // AI explanation is in flight — never an empty panel.
                                    return (
                                        <section data-testid="expl-why-correct-fallback">
                                            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-700 mb-2 flex items-center gap-1.5">
                                                <Lightbulb className="w-4 h-4" /> Why the correct answer is right
                                            </h3>
                                            <div className="rounded-lg bg-emerald-50/60 border border-emerald-200 px-4 py-3 text-sm text-slate-700 leading-relaxed">
                                                The correct answer is <strong>option {correctAnswer || (optionLabels[0] || 'A')}</strong>.
                                                {' '}A detailed explanation is not yet available for this question — tap the AI Tutor button on the right to generate one instantly.
                                            </div>
                                        </section>
                                    );
                                })()}

                                {/* Concept deep-dive */}
                                {current.concept_explanation ? (
                                    <section data-testid="expl-concept">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-700 mb-2 flex items-center gap-1.5">
                                            <FlaskConical className="w-4 h-4" /> Concept deep-dive
                                        </h3>
                                        <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed">
                                            <FormattedText text={current.concept_explanation} />
                                        </div>
                                    </section>
                                ) : null}

                                {/* Mnemonic */}
                                {(current as any).effective_mnemonic || current.mnemonic || (current as any).ai_mnemonic ? (
                                    <section data-testid="expl-mnemonic" className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-amber-700 mb-1.5 flex items-center gap-1.5">
                                            <Pill className="w-4 h-4" /> Mnemonic
                                        </h3>
                                        <div className="text-sm text-amber-900 leading-relaxed whitespace-pre-wrap">
                                            {(current as any).effective_mnemonic || current.mnemonic || (current as any).ai_mnemonic}
                                        </div>
                                    </section>
                                ) : null}

                                {/* Clinical pearl / exam tip */}
                                {(current as any).learning_technique ? (
                                    <section data-testid="expl-clinical-pearl" className="rounded-lg bg-teal-50 border border-teal-200 px-4 py-3">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-teal-700 mb-1.5 flex items-center gap-1.5">
                                            <Stethoscope className="w-4 h-4" /> Clinical pearl / Exam tip
                                        </h3>
                                        <div className="text-sm text-teal-900 leading-relaxed">
                                            <FormattedText text={(current as any).learning_technique} />
                                        </div>
                                    </section>
                                ) : null}

                                {/* Textbook references */}
                                {(() => {
                                    const refs: Array<{ book?: string; chapter?: string; page?: string | number }> = [];
                                    const trefs = (current as any).textbook_references;
                                    if (Array.isArray(trefs)) {
                                        trefs.forEach((r: any) => refs.push(r));
                                    }
                                    const aRefs = (current as any).ai_references;
                                    if (Array.isArray(aRefs)) {
                                        aRefs.forEach((r: any) => {
                                            if (r && typeof r === 'object') refs.push(r);
                                        });
                                    }
                                    if (current.book_name || current.chapter || current.page_number || current.reference_text) {
                                        refs.push({
                                            book: current.book_name || undefined,
                                            chapter: current.chapter || undefined,
                                            page: current.page_number || undefined,
                                        });
                                    }
                                    if (!refs.length) return null;
                                    return (
                                        <section data-testid="expl-references">
                                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
                                                <BookOpen className="w-4 h-4" /> Textbook references
                                            </h3>
                                            <ul className="space-y-1.5 text-sm text-slate-700">
                                                {refs.slice(0, 6).map((r, idx) => (
                                                    <li key={idx} className="flex items-start gap-2">
                                                        <span className="text-teal-600 font-semibold">›</span>
                                                        <span>
                                                            {r.book && <strong>{r.book}</strong>}
                                                            {r.chapter && <span> — {r.chapter}</span>}
                                                            {r.page != null && r.page !== '' && <span> (p. {r.page})</span>}
                                                            {current.reference_text && (
                                                                <div className="text-xs text-slate-600 mt-0.5">{current.reference_text}</div>
                                                            )}
                                                        </span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </section>
                                    );
                                })()}

                                {/* Concept keywords (related concepts) */}
                                {Array.isArray((current as any).concept_keywords) && (current as any).concept_keywords.length ? (
                                    <section data-testid="expl-keywords">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
                                            <Activity className="w-4 h-4" /> Related concepts
                                        </h3>
                                        <div className="flex flex-wrap gap-1.5">
                                            {(current as any).concept_keywords.slice(0, 12).map((k: string, idx: number) => (
                                                <Badge key={idx} variant="outline" className="text-[11px] bg-white">
                                                    {k}
                                                </Badge>
                                            ))}
                                        </div>
                                    </section>
                                ) : null}

                                {/* Verification badge */}
                                {(current as any).is_verified_by_admin ? (
                                    <div className="flex items-center gap-2 text-xs text-emerald-700 pt-1">
                                        <CheckCircle2 className="w-4 h-4" />
                                        <span>Verified by {(current as any).verified_by || 'admin'}</span>
                                        {(current as any).verified_at && (
                                            <span className="text-slate-500">· {new Date((current as any).verified_at).toLocaleDateString()}</span>
                                        )}
                                    </div>
                                ) : null}

                                {/* ═══ Generate AI Analysis — inline button ═══ */}
                                {!state.aiExplanation && !state.aiLoading && !state.aiError && (
                                    <button
                                        onClick={() => {
                                            if (typeof window !== 'undefined' && (window as any).gtag) {
                                                (window as any).gtag('event', 'ai_explain_request', { source: 'neet_pg_practice' });
                                            }
                                            fetchAi();
                                        }}
                                        className="w-full rounded-2xl border border-blue-200 bg-blue-50/50 dark:bg-blue-900/10 dark:border-blue-800/50 p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:bg-blue-100 dark:hover:bg-blue-900/30 hover:shadow-md"
                                        data-testid="generate-ai-analysis"
                                    >
                                        <Brain className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                                        <div className="text-left">
                                            <span className="text-sm font-bold block text-blue-700 dark:text-blue-300">Generate AI Analysis</span>
                                            <span className="text-xs text-slate-500 dark:text-slate-400">Mnemonics, explanations, exam tips & textbook references</span>
                                        </div>
                                    </button>
                                )}

                                {/* AI Loading */}
                                {state.aiLoading && (
                                    <div className="flex items-center justify-center gap-3 p-6 rounded-xl border border-blue-200 bg-blue-50/30 dark:bg-blue-900/10">
                                        <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                                        <span className="text-sm font-medium text-blue-600 dark:text-blue-400">Analyzing question with AI…</span>
                                    </div>
                                )}

                                {/* AI Error */}
                                {state.aiError && (
                                    <div className="rounded-xl border border-rose-200 bg-rose-50/80 dark:bg-rose-950/20 p-4 text-center space-y-2">
                                        <p className="text-sm font-bold text-rose-700 dark:text-rose-400">{state.aiError}</p>
                                        <button
                                            onClick={fetchAi}
                                            className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-700 hover:underline"
                                        >
                                            <Sparkles className="w-3 h-3" /> Retry AI Analysis
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Notes */}
                        <details className="border-t border-slate-100 bg-slate-50/50 px-6 py-3">
                            <summary className="text-xs font-bold uppercase tracking-wider text-slate-500 cursor-pointer flex items-center gap-1.5 select-none">
                                <Highlighter className="w-3.5 h-3.5" /> Add personal note
                            </summary>
                            <textarea
                                value={state.notes}
                                onChange={(e) => setState(s => ({ ...s, notes: e.target.value }))}
                                placeholder="High-yield takeaway, mnemonic, revision priority…"
                                className="mt-3 w-full min-h-20 p-3 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-500"
                            />
                        </details>
                    </div>

                    {/* PRODUCTION-INCIDENT FIX (2026-07-25): rate-limited /
                        more-available footer. Shows clearly what's happening
                        so the spinner can't trap the user. */}
                    {(rateLimited || hasMore || loadingMore) && (
                        <div
                            role="status"
                            aria-live="polite"
                            className={cn(
                                'mt-4 px-4 py-3 rounded-xl border text-sm flex items-center gap-2',
                                rateLimited
                                    ? 'bg-rose-50 border-rose-200 text-rose-800'
                                    : 'bg-teal-50 border-teal-200 text-teal-800',
                            )}
                        >
                            {loadingMore ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                                    <span>Loading more questions…</span>
                                </>
                            ) : rateLimited ? (
                                <>
                                    <AlertTriangle className="w-4 h-4 shrink-0" />
                                    <span className="flex-1">
                                        Server rate-limited our requests. Click Retry to continue with a fresh batch.
                                    </span>
                                    {onRetry && (
                                        <button
                                            type="button"
                                            onClick={onRetry}
                                            className="px-3 py-1 rounded-md bg-rose-600 text-white text-xs font-semibold hover:bg-rose-700"
                                        >
                                            Retry
                                        </button>
                                    )}
                                </>
                            ) : (
                                <>
                                    <Activity className="w-4 h-4 shrink-0" />
                                    <span className="flex-1">
                                        {total} loaded. Click Next to fetch more.
                                    </span>
                                </>
                            )}
                        </div>
                    )}

                    {/* Sticky navigation bar */}
                    <div className="sticky bottom-0 z-20 mt-4 -mx-4 px-4">
                        <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-teal-900/10 dark:shadow-black/40 border border-teal-100 dark:border-slate-800 p-3 flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={goPrev}
                                disabled={isFirst}
                                className="border-teal-200 hover:bg-teal-50"
                            >
                                <ChevronLeft className="w-4 h-4 mr-1" /> Prev
                            </Button>
                            <div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setPaletteOpen(true)}
                                    className="border-teal-300 text-teal-700 hover:bg-teal-50"
                                    aria-label="Question palette"
                                >
                                    <LayoutGrid className="w-4 h-4 sm:mr-1 mr-0" />
                                    <span className="font-semibold hidden sm:inline">Palette</span>
                                    <span className="ml-1 text-xs opacity-70 hidden sm:inline">{state.index + 1}/{total}</span>
                                </Button>
                            </div>
                            <div>
                                <a
                                    href="/neet-pg"
                                    className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border border-teal-300 text-teal-700 hover:bg-teal-50 h-8 px-3"
                                >
                                    <Filter className="w-4 h-4 sm:mr-1 mr-0" />
                                    <span className="font-semibold hidden sm:inline">Filters</span>
                                </a>
                            </div>
                            <div className="ml-auto">
                                <Button
                                    size="sm"
                                    onClick={goNext}
                                    disabled={isLast && !hasMore}
                                    className="bg-teal-600 hover:bg-teal-700 text-white font-semibold"
                                >
                                    {loadingMore ? (
                                        <>
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Loading…
                                        </>
                                    ) : (
                                        <>
                                            Next <ChevronRight className="w-4 h-4 ml-1" />
                                        </>
                                    )}
                                </Button>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Right: AI panel + Related PYQs */}
                <aside className="col-span-12 lg:col-span-5 xl:col-span-4 order-1 lg:order-2 space-y-4">
                    {/* AI panel — Phase-6 AiTutorPanel (custom prompt, cache badge, progressive reveal, stop) */}
                    <AiTutorPanel
                        questionId={current.id}
                        questionText={current.question_text}
                        correctAnswer={current.correct_answer ?? undefined}
                        subject={typeof current.subject === 'object' ? (current.subject as any)?.name : (current.subject as any)}
                        topic={current.topic ?? null}
                        selectedAnswer={state.selected}
                    />

                    {/* Related PYQs sidebar */}
                    {related.length > 0 && (
                        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                            <button
                                onClick={() => setRelatedOpen(o => !o)}
                                className="w-full px-4 py-3 flex items-center justify-between text-left"
                                aria-expanded={relatedOpen}
                            >
                                <span className="flex items-center gap-2">
                                    <Target className="w-4 h-4 text-teal-600" />
                                    <span className="text-sm font-bold text-slate-800 dark:text-slate-100">Similar PYQs</span>
                                    <Badge variant="secondary" className="text-xs">{related.length}</Badge>
                                </span>
                                {relatedOpen ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                            </button>
                            {relatedOpen && (
                                <ul className="px-3 pb-3 space-y-2 max-h-105 overflow-y-auto" role="list">
                                    {related.map(r => {
                                        const reason = (r as any).similarity_reason as string | undefined;
                                        return (
                                            <li key={r.id} role="listitem">
                                                <a
                                                    href={`/questions/neet-pg/practice?q=${r.id}`}
                                                    className="block p-3 rounded-lg border border-slate-100 hover:border-teal-300 hover:bg-teal-50/30 transition-colors"
                                                    data-testid="similar-pyq-row"
                                                >
                                                    <div className="flex items-center justify-between text-xs text-slate-500 mb-1 gap-2">
                                                        <span>Q{r.id}</span>
                                                        <div className="flex items-center gap-1">
                                                            {reason && (
                                                                <Badge
                                                                    variant="outline"
                                                                    className={cn(
                                                                        'text-[10px] py-0 px-1.5 font-medium',
                                                                        reason === 'same_concept' || reason === 'curated'
                                                                            ? 'border-violet-300 text-violet-700 bg-violet-50'
                                                                            : reason === 'same_image'
                                                                                ? 'border-pink-300 text-pink-700 bg-pink-50'
                                                                                : reason === 'same_topic'
                                                                                    ? 'border-teal-300 text-teal-700 bg-teal-50'
                                                                                    : 'border-slate-300 text-slate-600 bg-slate-50',
                                                                    )}
                                                                    title={SIM_REASON_TITLE[reason] || ''}
                                                                >
                                                                    {SIM_REASON_LABEL[reason] || reason.replace(/_/g, ' ')}
                                                                </Badge>
                                                            )}
                                                            {r.year && <Badge variant="outline" className="text-[10px] py-0 px-1.5">{r.year}</Badge>}
                                                        </div>
                                                    </div>
                                                    <p className="text-xs text-slate-700 line-clamp-3">
                                                        {isLikelyGarbled(r.question_text || '')
                                                            ? <span className="italic text-slate-500">Question #{r.id}{r.year ? ` (${r.year})` : ''}</span>
                                                            : <FormattedText text={r.question_text || ''} />
                                                        }
                                                    </p>
                                                </a>
                                            </li>
                                        );
                                    })}
                                </ul>
                            )}
                        </div>
                    )}
                </aside>
            </main>

            {/* Question palette (sticky sheet) */}
            {paletteOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
                    onClick={() => setPaletteOpen(false)}
                    role="dialog"
                    aria-modal="true"
                >
                    <div
                        className="bg-white rounded-2xl border border-teal-200 shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="sticky top-0 bg-white/95 backdrop-blur z-10 px-6 py-4 border-b border-teal-100 flex items-center justify-between">
                            <h2 className="font-bold text-slate-800 flex items-center gap-2">
                                <Stethoscope className="w-5 h-5 text-teal-600" />
                                Question Palette — {title}
                            </h2>
                            <button
                                onClick={() => setPaletteOpen(false)}
                                className="p-2 rounded-lg hover:bg-slate-100"
                                aria-label="Close palette"
                            >
                                <XIcon className="w-4 h-4 text-slate-500" />
                            </button>
                        </div>
                        <div className="px-6 py-4 grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-2">
                            {questions.map((_, i) => (
                                <button
                                    key={i}
                                    onClick={() => { setState(s => ({ ...s, index: i })); setPaletteOpen(false); }}
                                    className={cn(
                                        'aspect-square rounded-lg text-sm font-bold transition-all',
                                        i === state.index ? 'bg-teal-600 text-white ring-2 ring-teal-300' :
                                            'bg-slate-100 text-slate-700 hover:bg-teal-100',
                                    )}
                                >
                                    {i + 1}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* Image viewer (Phase-7) — zoom / pan / fullscreen / annotations / side-by-side */}
            <ImageViewer
                images={images.map((img) => ({
                    id: img.id,
                    file_url: img.file_url,
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
                startIndex={zoomImg ? Math.max(0, images.findIndex((i) => i.id === zoomImg.id)) : 0}
                open={!!zoomImg}
                onClose={() => setZoomImg(null)}
            />
        </div>
    );
}
