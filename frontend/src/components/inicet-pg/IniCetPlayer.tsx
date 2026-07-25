/**
 * IniCetPlayer — dedicated premium medical question player for INI-CET.
 *
 * Material differences vs NeetPgPlayer:
 *   - Indigo / sky palette instead of teal/emerald.
 *   - INI-CET subject PDFs contain deep image-rich explanations; the player
 *     renders them in a sticky right-side rail and at full-bleed inside
 *     the explanation panel.
 *   - "View explanation image" jump target — clicking a thumbnail reveals
 *     the full-size explanation image (with pinch-zoom).
 *
 * Routing: `/questions/inicet/practice?subject=Anatomy&year=2024`
 *          optional `?q=<id>` to jump to a single question.
 *
 * Independent of NEET PG — decoupled for separate analytics + token metering.
 */
'use client';
import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
    ChevronLeft, ChevronRight, Loader2, Brain, Sparkles,
    CheckCircle2, X as XIcon, Bookmark, BookmarkCheck, ArrowLeft,
    Target, Lightbulb, Flag, FlagOff, Image as ImageIcon,
    ZoomIn, Stethoscope, Pill, FlaskConical,
    AlertTriangle, Pin, PinOff, Highlighter,
    Clock, ChevronDown, ChevronUp, Activity, HeartPulse, BookOpen, FileText,
} from 'lucide-react';
import { questionsAPI, aiAPI } from '@/lib/api';
import { FormattedText } from '@/components/FormattedText';
import { cleanOptionText, extractAnalysisFromJson, nonPlaceholderExplanation } from '@/lib/textCleanup';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import AiTutorPanel from '@/components/ai/AiTutorPanel';
import ImageViewer from '@/components/image/ImageViewer';

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
    role?: 'stem' | 'explanation' | 'option';  // INI-CET uses 3 distinct image roles
}

interface Question {
    id: number;
    question_text: string;
    option_a?: string | null;
    option_b?: string | null;
    option_c?: string | null;
    option_d?: string | null;
    option_e?: string | null;  // INI-CET may use 5 options
    correct_answer?: string | null;
    year?: number;
    difficulty?: string;
    is_image_based?: boolean;
    explanation?: string;
    subject?: { id?: number; name?: string } | string | null;
    topic?: string;
    // PHASE 2 (2026-07-25): extended fields surfaced by QuestionDetailSerializer.
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

const ROLE_LABEL: Record<string, string> = {
    stem: 'Image',
    explanation: 'Explanation',
    option: 'Option',
};

export default function IniCetPlayer({
    questions,
    initialIndex = 0,
    title = 'INI-CET Practice',
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
    /** PRODUCTION-INCIDENT FIX (2026-07-25): the parent only fetches
     *  the first 20 questions; when the user reaches near the end the
     *  player calls onLoadMore() to fetch the next page on demand. */
    hasMore?: boolean;
    loadingMore?: boolean;
    onLoadMore?: () => Promise<void> | void;
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
    const [pinImagePanel, setPinImagePanel] = useState(true);
    const [score, setScore] = useState({ correct: 0, wrong: 0, flagged: 0 });
    const startedAt = useRef<number>(Date.now());

    const current = questions[state.index];
    const total = questions.length;

    // Split images: stem vs explanation vs option
    const stemImages = useMemo(
        () => images.filter(i => (i.role || 'stem') === 'stem'),
        [images],
    );
    const explanationImages = useMemo(
        () => images.filter(i => i.role === 'explanation'),
        [images],
    );

    useEffect(() => {
        setState(s => ({ ...s, selected: null, showAnswer: false, aiExplanation: null, aiError: null }));
        startedAt.current = Date.now();
        if (!current) { setImages([]); return; }

        let cancelled = false;
        (async () => {
            try {
                const imgs = await questionsAPI.getImages(current.id);
                if (!cancelled) setImages((imgs.data as QuestionImage[]) || []);
            } catch { if (!cancelled) setImages([]); }
        })();
        return () => { cancelled = true; };
    }, [current?.id]);

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
        if (state.index < total - 1) {
            setState(s => ({ ...s, index: s.index + 1 }));
            setPaletteOpen(false);
            return;
        }
        if (hasMore && onLoadMore && !loadingMore && !rateLimited) {
            onLoadMore();
        }
        setPaletteOpen(false);
    }, [state.index, total, hasMore, onLoadMore, loadingMore, rateLimited]);
    const goPrev = useCallback(() => {
        if (state.index <= 0) return;
        setState(s => ({ ...s, index: s.index - 1 }));
    }, [state.index]);
    const isFirst = state.index <= 0;
    const isLast = state.index >= total - 1;
    const progress = total ? Math.round(((state.index + 1) / total) * 100) : 0;

    useEffect(() => {
        const h = (e: KeyboardEvent) => {
            if ((e.target as HTMLElement)?.tagName?.match(/INPUT|TEXTAREA|SELECT/)) return;
            if (e.key === 'ArrowRight') goNext();
            else if (e.key === 'ArrowLeft') goPrev();
            else if (['a', 'b', 'c', 'd', 'A', 'B', 'C', 'D', 'e', 'E'].includes(e.key)) {
                const c = e.key.toUpperCase();
                if (state.selected == null) submitAttempt(c);
            } else if (e.key === '?') setPaletteOpen(o => !o);
            else if (e.key === 'f' || e.key === 'F') setState(s => ({ ...s, flagged: !s.flagged }));
            else if (e.key === 'b' || e.key === 'B') setState(s => ({ ...s, bookmarked: !s.bookmarked }));
        };
        window.addEventListener('keydown', h);
        return () => window.removeEventListener('keydown', h);
    }, [goNext, goPrev, submitAttempt, state.selected]);

    // PRODUCTION-INCIDENT FIX (2026-07-25): auto-load the next page
    // when within 5 of the end of what's loaded. Prevents the Next
    // button from hitting an empty tail.
    useEffect(() => {
        if (!onLoadMore || !hasMore || loadingMore || rateLimited) return;
        if (state.index >= total - 5) {
            onLoadMore();
        }
    }, [state.index, total, hasMore, loadingMore, rateLimited, onLoadMore]);

    const toggleBookmark = useCallback(async () => {
        if (!current) return;
        setState(s => ({ ...s, bookmarked: !s.bookmarked }));
        try { await questionsAPI.bookmark(current.id); } catch { /* offline-tolerant */ }
    }, [current?.id]);

    const handleExit = () => {
        if (onExit) onExit();
        else router.push('/questions?exam=ini-cet');
    };

    if (!total) return null;

    const correctAnswer = (current.correct_answer || '').toUpperCase().trim();
    // INI-CET typically uses 4 options but some questions have 5 — render labels present in data.
    const optionLabels = (['A', 'B', 'C', 'D', 'E'] as const).filter(L => (current as any)[`option_${L.toLowerCase()}`]?.trim?.());

    return (
        // `main-content` honours the `body.sidebar-hidden` toggle (see globals.css).
        // The global `.main-content` rule already applies a 260px desktop
        // margin-left to clear the fixed sidebar; on mobile the sidebar is a
        // drawer so no offset is needed.
        <div className="main-content min-h-screen bg-gradient-to-br from-indigo-50/40 via-white to-sky-50/40">
            {/* Header */}
            <header className="sticky top-0 z-30 backdrop-blur-xl bg-white/85 border-b border-indigo-100 shadow-sm">
                <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center gap-3">
                    <button onClick={handleExit} aria-label="Exit practice" className="p-2 rounded-lg hover:bg-indigo-50 transition-colors">
                        <ArrowLeft className="w-5 h-5 text-indigo-700" />
                    </button>
                    <div className="flex items-center gap-2 min-w-0">
                        <BookOpen className="w-5 h-5 text-indigo-600 flex-shrink-0" />
                        <h1 className="text-base sm:text-lg font-bold text-slate-800 truncate">{title}</h1>
                    </div>
                    <div className="ml-auto flex items-center gap-2">
                        <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200 font-semibold">
                            Q {state.index + 1} / {total}{hasMore ? '+' : ''}
                        </Badge>
                        <Badge variant="secondary" className="font-semibold">
                            <Activity className="w-3 h-3 mr-1 inline" />
                            Score: {score.correct * SCORE_CORRECT + score.wrong * SCORE_WRONG}
                        </Badge>
                    </div>
                </div>
                <Progress value={progress} className="h-1 rounded-none bg-indigo-100" />
            </header>

            <main className="max-w-[1600px] mx-auto px-4 py-6 grid grid-cols-12 gap-4">
                {/* Left: Question + Options + Explanation */}
                <section className="col-span-12 lg:col-span-8 order-2 lg:order-1">
                    <div className="bg-white rounded-2xl shadow-xl shadow-indigo-900/5 border border-indigo-100/60 overflow-hidden">
                        <div className="px-6 py-3 bg-gradient-to-r from-indigo-50/40 via-sky-50/30 to-white border-b border-indigo-100 flex flex-wrap items-center gap-2 text-xs">
                            {current.subject && (
                                <Badge className="bg-indigo-600 text-white font-semibold border-indigo-700">
                                    <Pill className="w-3 h-3 mr-1" />
                                    {typeof current.subject === 'object' ? current.subject.name : current.subject}
                                </Badge>
                            )}
                            {current.year ? (
                                <Badge variant="outline" className="border-indigo-300 text-indigo-800 font-semibold">
                                    <Clock className="w-3 h-3 mr-1" /> INI-CET {current.year}
                                </Badge>
                            ) : null}
                            <Badge className={cn('font-semibold border-0', TONE[difficultyTone(current.difficulty)])}>
                                {difficultyTone(current.difficulty).toUpperCase()}
                            </Badge>
                            {(current.is_image_based || stemImages.length > 0) && (
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
                                    className={cn('p-2 rounded-lg transition-colors',
                                        state.flagged ? 'bg-amber-100 text-amber-700' : 'text-slate-400 hover:bg-slate-100')}
                                >
                                    {state.flagged ? <Flag className="w-4 h-4" /> : <FlagOff className="w-4 h-4" />}
                                </button>
                                <button
                                    onClick={toggleBookmark}
                                    aria-pressed={state.bookmarked}
                                    title="Bookmark (B)"
                                    className={cn('p-2 rounded-lg transition-colors',
                                        state.bookmarked ? 'bg-indigo-100 text-indigo-700' : 'text-slate-400 hover:bg-slate-100')}
                                >
                                    {state.bookmarked ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        {/* Stem images */}
                        {stemImages.length > 0 && (
                            <div className="px-6 py-4 bg-slate-50 border-b border-slate-100">
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                                        <ImageIcon className="w-3.5 h-3.5" /> {stemImages.length} {stemImages.length === 1 ? 'Image' : 'Images'}
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
                                    {stemImages.map(img => (
                                        <button
                                            key={img.id}
                                            type="button"
                                            onClick={() => setZoomImg(img)}
                                            className="relative group rounded-lg overflow-hidden border border-slate-200 bg-white hover:border-indigo-400 transition-all hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        >
                                            {img.file_url ? (
                                                <img
                                                    src={img.file_url}
                                                    alt={img.caption || `Question ${current.id} image`}
                                                    loading="lazy"
                                                    className="w-full h-auto object-contain bg-white max-h-[420px]"
                                                />
                                            ) : (
                                                <div className="aspect-video flex items-center justify-center text-slate-400">
                                                    <ImageIcon className="w-10 h-10" />
                                                </div>
                                            )}
                                            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-gradient-to-t from-black/60 to-transparent transition-opacity flex items-end p-3">
                                                <span className="text-white text-xs flex items-center gap-1">
                                                    <ZoomIn className="w-3.5 h-3.5" /> Tap to zoom
                                                </span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="px-6 py-6">
                            <div className="prose prose-slate max-w-none text-slate-800 leading-relaxed text-[15px]">
                                <FormattedText text={current.question_text || ''} />
                            </div>
                        </div>

                        <div className="px-6 pb-6">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">Choose the correct option</h3>
                            <div className="grid grid-cols-1 gap-3">
                                {optionLabels.map((label) => {
                                    const raw = (current as any)[`option_${label.toLowerCase()}`] as string;
                                    if (!raw || !raw.trim()) return null;
                                    const isSelected = state.selected === label;
                                    const isCorrect = state.showAnswer && correctAnswer === label;
                                    const isWrong = state.showAnswer && isSelected && !isCorrect;
                                    return (
                                        <button
                                            key={label}
                                            type="button"
                                            disabled={state.showAnswer}
                                            onClick={() => submitAttempt(label)}
                                            className={cn(
                                                'group flex items-start gap-3 p-4 rounded-xl border text-left transition-all',
                                                'hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-500',
                                                isCorrect && 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-300',
                                                isWrong && 'border-rose-400 bg-rose-50',
                                                !isCorrect && !isWrong && isSelected && 'border-indigo-500 bg-indigo-50',
                                                !isCorrect && !isWrong && !isSelected && 'border-slate-200 bg-white hover:border-indigo-300',
                                            )}
                                        >
                                            <span className={cn(
                                                'w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0 transition-all',
                                                isCorrect ? 'bg-emerald-600 text-white' :
                                                    isWrong ? 'bg-rose-500 text-white' :
                                                        isSelected ? 'bg-indigo-600 text-white' :
                                                            'bg-slate-100 text-slate-600 group-hover:bg-indigo-100 group-hover:text-indigo-700',
                                            )}>
                                                {isCorrect ? <CheckCircle2 className="w-4 h-4" /> :
                                                    isWrong ? <XIcon className="w-4 h-4" /> :
                                                        label}
                                            </span>
                                            <span className="flex-1 text-slate-800 text-[14px] leading-relaxed">
                                                <FormattedText text={cleanOptionText(raw) || ''} />
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* PHASE 2 — Detailed explanation panel (2026-07-25).
                            Renders all available explanation fields from the
                            QuestionDetailSerializer (explanation, concept_explanation,
                            mnemonic, ai_explanation, ai_mnemonic, ai_references,
                            learning_technique, textbook_references, book/chapter/
                            page/reference_text, concept_keywords, is_verified_by_admin)
                            + the existing explanation-image grid for INI-CET. */}
                        {state.showAnswer && (current.explanation || current.concept_explanation || current.mnemonic || (current as any).ai_explanation || (current as any).ai_mnemonic || explanationImages.length > 0) && (
                            <div
                                role="region"
                                aria-label="Detailed explanation"
                                className="border-t border-indigo-200 bg-gradient-to-br from-indigo-50/60 via-white to-sky-50/40 px-6 py-5 space-y-4"
                            >
                                {/* Why correct answer */}
                                {(() => {
                                    // Filter out the admin `force-regenerate`
                                    // placeholder strings so they never render
                                    // verbatim. The plain `ai_explanation` field
                                    // is intentionally not in the chain — when
                                    // an admin hits force-regenerate on a
                                    // question without a real explanation, the
                                    // column gets the placeholder string and the
                                    // serializer/UI is supposed to fall through
                                    // to the regular `explanation` field.
                                    const eff = nonPlaceholderExplanation(
                                        (current as { effective_explanation?: string }).effective_explanation,
                                    );
                                    const fallback = nonPlaceholderExplanation(current.explanation);
                                    const expText = eff || fallback;
                                    if (!expText) return null;
                                    return (
                                        <section data-testid="expl-why-correct">
                                            <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-700 mb-2 flex items-center gap-1.5">
                                                <Lightbulb className="w-4 h-4" /> Why the correct answer is right
                                            </h3>
                                            <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed">
                                                <FormattedText text={extractAnalysisFromJson(expText)} />
                                            </div>
                                        </section>
                                    );
                                })()}

                                {/* Concept deep-dive */}
                                {current.concept_explanation ? (
                                    <section data-testid="expl-concept">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-sky-700 mb-2 flex items-center gap-1.5">
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
                                    <section data-testid="expl-clinical-pearl" className="rounded-lg bg-sky-50 border border-sky-200 px-4 py-3">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-sky-700 mb-1.5 flex items-center gap-1.5">
                                            <Stethoscope className="w-4 h-4" /> Clinical pearl / Exam tip
                                        </h3>
                                        <div className="text-sm text-sky-900 leading-relaxed">
                                            <FormattedText text={(current as any).learning_technique} />
                                        </div>
                                    </section>
                                ) : null}

                                {/* Textbook references */}
                                {(() => {
                                    const refs: Array<{ book?: string; chapter?: string; page?: string | number }> = [];
                                    const trefs = (current as any).textbook_references;
                                    if (Array.isArray(trefs)) trefs.forEach((r: any) => refs.push(r));
                                    const aRefs = (current as any).ai_references;
                                    if (Array.isArray(aRefs)) aRefs.forEach((r: any) => {
                                        if (r && typeof r === 'object') refs.push(r);
                                    });
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
                                                        <span className="text-sky-600 font-semibold">›</span>
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
                                    <div className="flex items-center gap-2 text-xs text-sky-700 pt-1">
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
                                                (window as any).gtag('event', 'ai_explain_request', { source: 'inicet_practice' });
                                            }
                                            fetchAi();
                                        }}
                                        className="w-full rounded-2xl border border-indigo-200 bg-indigo-50/50 dark:bg-indigo-900/10 dark:border-indigo-800/50 p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:bg-indigo-100 dark:hover:bg-indigo-900/30 hover:shadow-md"
                                        data-testid="generate-ai-analysis"
                                    >
                                        <Brain className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
                                        <div className="text-left">
                                            <span className="text-sm font-bold block text-indigo-700 dark:text-indigo-300">Generate AI Analysis</span>
                                            <span className="text-xs text-slate-500 dark:text-slate-400">Mnemonics, explanations, exam tips & textbook references</span>
                                        </div>
                                    </button>
                                )}

                                {/* AI Loading */}
                                {state.aiLoading && (
                                    <div className="flex items-center justify-center gap-3 p-6 rounded-xl border border-indigo-200 bg-indigo-50/30 dark:bg-indigo-900/10">
                                        <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                                        <span className="text-sm font-medium text-indigo-600 dark:text-indigo-400">Analyzing question with AI…</span>
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

                                {explanationImages.length > 0 && (
                                    <section data-testid="expl-images">
                                        <h4 className="text-[11px] font-bold uppercase tracking-wider text-indigo-700 mb-2 flex items-center gap-1.5">
                                            <FileText className="w-3.5 h-3.5" /> Explanation diagrams ({explanationImages.length})
                                        </h4>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                            {explanationImages.map(img => (
                                                <button
                                                    key={img.id}
                                                    type="button"
                                                    onClick={() => setZoomImg(img)}
                                                    className="relative group rounded-lg overflow-hidden border border-indigo-200 bg-white hover:border-indigo-500 transition-all hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                                >
                                                    {img.file_url && (
                                                        <img
                                                            src={img.file_url}
                                                            alt={img.caption || 'Explanation image'}
                                                            loading="lazy"
                                                            className="w-full h-auto object-contain bg-white max-h-[480px]"
                                                        />
                                                    )}
                                                    {img.caption && (
                                                        <div className="px-3 py-2 text-xs text-slate-600 bg-slate-50 border-t border-indigo-100">
                                                            {img.caption}
                                                        </div>
                                                    )}
                                                </button>
                                            ))}
                                        </div>
                                    </section>
                                )}
                            </div>
                        )}

                        <details className="border-t border-slate-100 bg-slate-50/50 px-6 py-3">
                            <summary className="text-xs font-bold uppercase tracking-wider text-slate-500 cursor-pointer flex items-center gap-1.5 select-none">
                                <Highlighter className="w-3.5 h-3.5" /> Add personal note
                            </summary>
                            <textarea
                                value={state.notes}
                                onChange={(e) => setState(s => ({ ...s, notes: e.target.value }))}
                                placeholder="High-yield takeaway, image-description mnemonic, revision priority…"
                                className="mt-3 w-full min-h-[80px] p-3 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </details>
                    </div>

                    {(rateLimited || hasMore || loadingMore) && (
                        <div
                            role="status"
                            aria-live="polite"
                            className={cn(
                                'mt-4 px-4 py-3 rounded-xl border text-sm flex items-center gap-2',
                                rateLimited
                                    ? 'bg-rose-50 border-rose-200 text-rose-800'
                                    : 'bg-indigo-50 border-indigo-200 text-indigo-800',
                            )}
                        >
                            {loadingMore ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
                                    <span>Loading more questions…</span>
                                </>
                            ) : rateLimited ? (
                                <>
                                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
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
                                    <Activity className="w-4 h-4 flex-shrink-0" />
                                    <span className="flex-1">
                                        {total} loaded. Click Next to fetch more.
                                    </span>
                                </>
                            )}
                        </div>
                    )}

                    <div className="sticky bottom-0 z-20 mt-4 -mx-4 px-4">
                        <div className="bg-white/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-indigo-900/10 border border-indigo-100 p-3 flex items-center gap-2">
                            <Button variant="outline" size="sm" onClick={goPrev} disabled={isFirst} className="border-indigo-200 hover:bg-indigo-50">
                                <ChevronLeft className="w-4 h-4 mr-1" /> Prev
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setPaletteOpen(true)}
                                className="border-indigo-300 text-indigo-700 hover:bg-indigo-50"
                                aria-label="Question palette"
                            >
                                <span className="font-semibold">Palette</span>
                                <span className="ml-1 text-xs opacity-70">{state.index + 1}/{total}</span>
                            </Button>
                            <div className="ml-auto">
                                <Button
                                    size="sm"
                                    onClick={goNext}
                                    disabled={isLast && !hasMore}
                                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold"
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

                {/* Right: AI Tutor — Phase-6 AiTutorPanel (custom prompt, cache badge, progressive reveal, stop) */}
                <aside className="col-span-12 lg:col-span-4 order-1 lg:order-2 space-y-4">
                    <AiTutorPanel
                        questionId={current.id}
                        questionText={current.question_text}
                        correctAnswer={current.correct_answer ?? undefined}
                        subject={typeof current.subject === 'object' ? (current.subject as any)?.name : (current.subject as any)}
                        topic={current.topic ?? null}
                        selectedAnswer={state.selected}
                    />
                </aside>
            </main>

            {paletteOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
                    onClick={() => setPaletteOpen(false)}
                    role="dialog"
                    aria-modal="true"
                >
                    <div
                        className="bg-white rounded-2xl border border-indigo-200 shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="sticky top-0 bg-white/95 backdrop-blur z-10 px-6 py-4 border-b border-indigo-100 flex items-center justify-between">
                            <h2 className="font-bold text-slate-800 flex items-center gap-2">
                                <BookOpen className="w-5 h-5 text-indigo-600" />
                                Question Palette — {title}
                            </h2>
                            <button onClick={() => setPaletteOpen(false)} className="p-2 rounded-lg hover:bg-slate-100" aria-label="Close palette">
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
                                        i === state.index ? 'bg-indigo-600 text-white ring-2 ring-indigo-300' : 'bg-slate-100 text-slate-700 hover:bg-indigo-100',
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
