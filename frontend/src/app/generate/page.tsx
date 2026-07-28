/**
 * generate/page.tsx — AI Question Generator.
 *
 * Track-aware (NEET PG / INI-CET / CMS) unlimited AI MCQ generator.
 * Polished UI:
 *  * Cards, Buttons, Badges, Progress, Skeletons from `@/components/ui`
 *  * Real subjects fetched per active exam track (NEET PG → 19 PG
 *    subjects; INI-CET → super-specialty; CMS → UPSC subjects)
 *  * Token-cost preview (1 token/question per platform rules)
 *  * Per-question deep explanation card via reveal-on-answer
 *  * Score summary, regenerate, answer-state styling
 */
'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { useExamTrack } from '@/components/ExamTrackProvider';
import Sidebar from '@/components/Sidebar';
import { aiAPI, questionsAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import {
    Sparkles, Loader2, CheckCircle, XCircle, ChevronDown, RefreshCw,
    Brain, BookMarked, Target, Zap, Award, AlertTriangle, Coins,
} from 'lucide-react';

interface AIExplanation {
    category?: string;
    sub_category?: string;
    question_type?: string;
    core_concept?: string;
    why_correct?: string;
    why_wrong?: Record<string, string>;
    textbook_reference?: { book?: string; chapter?: string; page?: string; section?: string };
    mnemonic?: string;
    high_yield_points?: string[];
    around_concepts?: string[];
    clinical_pearl?: string;
    exam_tip?: string;
    pyq_frequency?: string;
    similar_pyq?: string;
    error?: boolean;
}

interface GeneratedQuestion {
    question_text: string;
    option_a: string;
    option_b: string;
    option_c: string;
    option_d: string;
    correct_answer: string;
    explanation: string;
    difficulty: string;
    subject: string;
    topic: string;
    error?: string;
}

interface Subject { id: number; name: string; code: string; exam_type?: string; }

const TRACK_META: Record<string, { label: string; tagline: string; defaultSubject: string }> = {
    cms:     { label: 'UPSC CMS',  tagline: 'Generate AI-powered MCQs across UPSC CMS subjects', defaultSubject: 'General Medicine' },
    neet_pg: { label: 'NEET PG',    tagline: 'Image-rich, clinical AI MCQs on 19 PG subjects',     defaultSubject: 'General Medicine' },
    ini_cet: { label: 'INI-CET',    tagline: 'AIIMS / PGIMER style super-specialty practice MCQs',  defaultSubject: 'General Medicine' },
    usmle:   { label: 'USMLE',      tagline: 'USMLE-style MCQs grounded in First Aid + UWorld',     defaultSubject: 'General Medicine' },
    fmge:    { label: 'FMGE',       tagline: 'NMC-screening style MCQs across MBBS subjects',       defaultSubject: 'General Medicine' },
};

const FALLBACK_SUBJECTS_BY_TRACK: Record<string, string[]> = {
    cms: [
        'General Medicine', 'General Surgery', 'Paediatrics',
        'Obstetrics & Gynaecology', 'Preventive & Social Medicine', 'ENT',
        'Ophthalmology', 'Orthopaedics', 'Dermatology', 'Psychiatry', 'Anaesthesia',
    ],
    neet_pg: [
        'General Medicine', 'General Surgery', 'Paediatrics',
        'Obstetrics & Gynaecology', 'Orthopaedics', 'ENT', 'Ophthalmology',
        'Dermatology', 'Psychiatry', 'Anaesthesia', 'Radiodiagnosis',
    ],
    ini_cet: ['General Medicine', 'General Surgery', 'Paediatrics'],
    usmle:   ['Internal Medicine', 'Surgery', 'Paediatrics', 'OB-GYN', 'Psychiatry'],
    fmge:    ['General Medicine', 'General Surgery', 'Paediatrics', 'OB-GYN'],
};

export default function GeneratePage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const { activeTrack, hydrated } = useExamTrack();
    const router = useRouter();
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [selectedSubject, setSelectedSubject] = useState('General Medicine');
    const [topic, setTopic] = useState('');
    const [difficulty, setDifficulty] = useState('medium');
    const [count, setCount] = useState(5);
    const [generating, setGenerating] = useState(false);
    const [progressPct, setProgressPct] = useState(0);
    const [questions, setQuestions] = useState<GeneratedQuestion[]>([]);
    const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
    const [showExplanations, setShowExplanations] = useState<Record<number, boolean>>({});
    const [aiExplanations, setAiExplanations] = useState<Record<number, AIExplanation>>({});
    const [aiLoadingIdx, setAiLoadingIdx] = useState<number | null>(null);
    const [errorBanner, setErrorBanner] = useState<string | null>(null);

    // Auth gate
    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    // Track-aware subject fetch — re-run when active track changes.
    useEffect(() => {
        if (!isAuthenticated || !hydrated) return;
        questionsAPI.getSubjects({ exam_type: activeTrack })
            .then(res => {
                const list = res.data?.results || res.data;
                if (Array.isArray(list) && list.length > 0) {
                    setSubjects(list);
                    const meta = TRACK_META[activeTrack] || TRACK_META.cms;
                    // Pick first subject matching defaultSubject, else first.
                    const target = list.find(s => s.name === meta.defaultSubject) || list[0];
                    if (target && !list.find(s => s.name === selectedSubject)) {
                        setSelectedSubject(target.name);
                    }
                }
            })
            .catch(() => { /* keep fallback list */ });
        // Reset user-visible selections when switching tracks so the
        // user doesn't see a stale "Medicine" when they're now on USMLE.
        setSubjectListFiller(activeTrack);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isAuthenticated, hydrated, activeTrack]);

    function setSubjectListFiller(track: string) {
        const meta = TRACK_META[track] || TRACK_META.cms;
        setSelectedSubject(prev => {
            if (prev && (prev === meta.defaultSubject || subjects.find(s => s.name === prev))) {
                return prev;
            }
            return meta.defaultSubject;
        });
    }

    // Progress-bar animation while generating.
    useEffect(() => {
        if (!generating) { setProgressPct(0); return; }
        let pct = 0;
        const tick = () => {
            pct = Math.min(pct + Math.random() * 7 + 3, 92);
            setProgressPct(pct);
            if (pct < 92) setTimeout(tick, 350);
        };
        const t = setTimeout(tick, 200);
        return () => clearTimeout(t);
    }, [generating]);

    const subjectOptions = useMemo(() => {
        if (subjects.length > 0) return subjects.map(s => s.name);
        return FALLBACK_SUBJECTS_BY_TRACK[activeTrack] || FALLBACK_SUBJECTS_BY_TRACK.cms;
    }, [subjects, activeTrack]);

    const trackMeta = TRACK_META[activeTrack] || TRACK_META.cms;

    const handleGenerate = async () => {
        setGenerating(true);
        setErrorBanner(null);
        setQuestions([]);
        setSelectedAnswers({});
        setShowExplanations({});
        setAiExplanations({});
        try {
            const res = await aiAPI.generateQuestions({
                subject: selectedSubject,
                topic: topic || undefined,
                difficulty,
                count,
            });
            if (res.data?.questions) {
                const filtered = res.data.questions.filter(
                    (q: GeneratedQuestion) => !q.error,
                );
                setQuestions(filtered);
            }
        } catch (err: unknown) {
            const error = err as {
                response?: { status?: number; data?: { error?: string } };
                message?: string;
            };
            if (error?.response?.status === 429) {
                setErrorBanner(
                    'AI tokens exhausted — your daily/weekly free quota is used up. ' +
                    'Visit /subscription or /tokens to top up.',
                );
            } else {
                const msg = error?.response?.data?.error || error?.message || 'AI service unavailable';
                setErrorBanner(`${msg}. Please try again.`);
            }
        }
        setGenerating(false);
        setProgressPct(100);
    };

    const selectAnswer = (qIdx: number, option: string) => {
        if (selectedAnswers[qIdx]) return;
        setSelectedAnswers(prev => ({ ...prev, [qIdx]: option }));
        setShowExplanations(prev => ({ ...prev, [qIdx]: true }));
        const q = questions[qIdx];
        if (!q) return;
        setAiLoadingIdx(qIdx);
        aiAPI.explainAfterAnswer({
            question_text: q.question_text,
            options: { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d },
            correct_answer: q.correct_answer,
            selected_answer: option,
            subject: q.subject || '',
            topic: q.topic || '',
        }).then(res => setAiExplanations(prev => ({ ...prev, [qIdx]: res.data })))
            .catch(err => setAiExplanations(prev => ({
                ...prev,
                [qIdx]: { why_correct: err?.response?.data?.error || 'AI unavailable', error: true },
            })))
            .finally(() => setAiLoadingIdx(null));
    };

    const getOptionClass = (qIdx: number, optKey: string) => {
        const selected = selectedAnswers[qIdx];
        const correct = questions[qIdx]?.correct_answer;
        if (!selected) {
            return 'border-border bg-card hover:bg-accent/40 hover:border-primary/40 cursor-pointer transition-all';
        }
        if (optKey === correct) {
            return 'border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/30';
        }
        if (optKey === selected) {
            return 'border-red-500 bg-red-500/10 ring-1 ring-red-500/30';
        }
        return 'border-border bg-card/40 opacity-50';
    };

    if (authLoading || !hydrated) return null;

    // Score derived state.
    const answeredCount = Object.keys(selectedAnswers).length;
    const correctCount = Object.entries(selectedAnswers).filter(
        ([idx, ans]) => ans === questions[Number(idx)]?.correct_answer,
    ).length;
    const quizComplete = questions.length > 0 && answeredCount === questions.length;

    return (
        <>
            <Sidebar />
            <div className="main-content">
                <main className="page-container p-6 md:p-8">
                    <div className="max-w-5xl mx-auto space-y-6">
                        {/* Hero */}
                        <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-card via-card to-primary/5 p-6 md:p-8">
                            <div className="absolute -right-12 -top-12 h-48 w-48 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
                            <div className="relative flex items-start gap-4">
                                <div className="rounded-xl bg-primary/15 p-3 text-primary shrink-0">
                                    <Sparkles className="h-7 w-7" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex flex-wrap items-center gap-2 mb-1">
                                        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
                                            AI Question Generator
                                        </h1>
                                        <Badge variant="secondary" className="gap-1">
                                            <Zap className="h-3 w-3" /> AI
                                        </Badge>
                                        <Badge variant="outline" className="gap-1 text-xs">
                                            {trackMeta.label}
                                        </Badge>
                                    </div>
                                    <p className="text-sm md:text-base text-muted-foreground">
                                        {trackMeta.tagline}. Every question costs 1 token — first 10 are free every day.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Controls */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-lg">
                                    <Target className="h-5 w-5 text-primary" />
                                    Configure your quiz
                                </CardTitle>
                                <CardDescription>
                                    Pick a subject and (optionally) a sub-topic. We&apos;ll generate {count}{' '}
                                    fresh MCQs calibrated to {difficulty} difficulty.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-5">
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                    {/* Subject */}
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                            Subject
                                        </label>
                                        <div className="relative">
                                            <select
                                                value={selectedSubject}
                                                onChange={e => setSelectedSubject(e.target.value)}
                                                className="w-full px-3 py-2 rounded-md border bg-background text-sm appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-ring"
                                            >
                                                {subjectOptions.map(s => (
                                                    <option key={s} value={s}>{s}</option>
                                                ))}
                                            </select>
                                            <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground" />
                                        </div>
                                    </div>

                                    {/* Topic */}
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                            Topic (optional)
                                        </label>
                                        <Input
                                            type="text"
                                            value={topic}
                                            onChange={e => setTopic(e.target.value)}
                                            placeholder="e.g., Cardiology, Vaccines"
                                        />
                                    </div>

                                    {/* Difficulty */}
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                            Difficulty
                                        </label>
                                        <div className="relative">
                                            <select
                                                value={difficulty}
                                                onChange={e => setDifficulty(e.target.value)}
                                                className="w-full px-3 py-2 rounded-md border bg-background text-sm appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-ring"
                                            >
                                                <option value="easy">Easy — recall</option>
                                                <option value="medium">Medium — applied</option>
                                                <option value="hard">Hard — clinical reasoning</option>
                                            </select>
                                            <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground" />
                                        </div>
                                    </div>

                                    {/* Count */}
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                            Questions
                                        </label>
                                        <div className="relative">
                                            <select
                                                value={count}
                                                onChange={e => setCount(Number(e.target.value))}
                                                className="w-full px-3 py-2 rounded-md border bg-background text-sm appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-ring"
                                            >
                                                {[3, 5, 10, 15, 20].map(n => (
                                                    <option key={n} value={n}>{n}</option>
                                                ))}
                                            </select>
                                            <ChevronDown className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground" />
                                        </div>
                                    </div>
                                </div>

                                {/* Cost preview + CTA */}
                                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <Coins className="h-3.5 w-3.5 text-amber-500" />
                                        <span>
                                            Estimated cost:&nbsp;
                                            <span className="font-semibold text-foreground">{count}</span>
                                            &nbsp;token{count > 1 ? 's' : ''} (1 per question + 1 per AI explanation)
                                        </span>
                                    </div>
                                    <Button
                                        onClick={handleGenerate}
                                        disabled={generating}
                                        size="lg"
                                        className="gap-2"
                                    >
                                        {generating ? (
                                            <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                                        ) : (
                                            <><Sparkles className="h-4 w-4" /> Generate Questions</>
                                        )}
                                    </Button>
                                </div>

                                {generating && (
                                    <div className="space-y-1.5">
                                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                                            <span>AI is composing questions…</span>
                                            <span>{Math.round(progressPct)}%</span>
                                        </div>
                                        <Progress value={progressPct} />
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Error banner */}
                        {errorBanner && (
                            <div className="flex items-start gap-3 rounded-lg border border-red-500/40 bg-red-500/10 p-4">
                                <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
                                <div className="text-sm text-red-700 dark:text-red-300">{errorBanner}</div>
                            </div>
                        )}

                        {/* Results header + score */}
                        {questions.length > 0 && (
                            <div className="flex items-center justify-between gap-4 flex-wrap">
                                <div>
                                    <h2 className="text-lg font-bold flex items-center gap-2">
                                        <Award className="h-5 w-5 text-primary" />
                                        {questions.length} Questions generated
                                    </h2>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {answeredCount === 0
                                            ? 'Pick an option on each card to reveal the AI explanation.'
                                            : `Answered ${answeredCount} of ${questions.length}.`}
                                    </p>
                                </div>
                                <Button variant="outline" size="sm" onClick={handleGenerate} disabled={generating} className="gap-1">
                                    <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                                </Button>
                            </div>
                        )}

                        {quizComplete && (
                            <Card>
                                <CardContent className="p-6 text-center">
                                    <div className="text-4xl font-bold text-primary">
                                        {correctCount} / {questions.length}
                                    </div>
                                    <div className="text-sm text-muted-foreground mt-1">
                                        Score —{' '}
                                        <span className="font-semibold text-foreground">
                                            {Math.round((correctCount / questions.length) * 100)}%
                                        </span>
                                        {' · '}
                                        {correctCount >= Math.ceil(questions.length * 0.7)
                                            ? 'Strong performance on this topic'
                                            : 'Re-read the explanations and try Regenerate'}
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Question cards */}
                        <div className="space-y-4">
                            {questions.map((q, idx) => (
                                <Card key={idx}>
                                    <CardContent className="p-5 md:p-6 space-y-4">
                                        <div className="flex items-start gap-3">
                                            <span className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold bg-primary text-primary-foreground">
                                                {idx + 1}
                                            </span>
                                            <div className="flex-1 min-w-0">
                                                <p className="font-medium leading-relaxed">{q.question_text}</p>
                                                <div className="flex gap-1.5 mt-2 flex-wrap">
                                                    <Badge variant="secondary">{q.subject}</Badge>
                                                    {q.topic && <Badge variant="outline">{q.topic}</Badge>}
                                                    <Badge variant="outline" className="text-[10px] uppercase">
                                                        {q.difficulty}
                                                    </Badge>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Options */}
                                        <div className="space-y-2 ml-0 md:ml-12">
                                            {(['A', 'B', 'C', 'D'] as const).map(opt => {
                                                const optValue = q[`option_${opt.toLowerCase()}` as keyof GeneratedQuestion] as string;
                                                if (!optValue) return null;
                                                const selected = selectedAnswers[idx];
                                                const correct = q.correct_answer;
                                                return (
                                                    <div
                                                        key={opt}
                                                        onClick={() => selectAnswer(idx, opt)}
                                                        className={`p-3 rounded-lg border flex items-center gap-3 ${getOptionClass(idx, opt)}`}
                                                    >
                                                        <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border shrink-0">
                                                            {opt}
                                                        </span>
                                                        <span className="text-sm flex-1">{optValue}</span>
                                                        {selected && opt === correct && (
                                                            <CheckCircle className="h-5 w-5 text-emerald-500 shrink-0" />
                                                        )}
                                                        {selected === opt && opt !== correct && (
                                                            <XCircle className="h-5 w-5 text-red-500 shrink-0" />
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        {/* Inline explanation */}
                                        {showExplanations[idx] && q.explanation && (
                                            <div className="ml-0 md:ml-12 rounded-lg border bg-muted/40 p-4">
                                                <div className="text-xs font-bold uppercase tracking-wide text-primary mb-1">
                                                    Why this answer
                                                </div>
                                                <p className="text-sm leading-relaxed text-muted-foreground">
                                                    {q.explanation}
                                                </p>
                                            </div>
                                        )}

                                        {/* AI deep explanation loader */}
                                        {aiLoadingIdx === idx && (
                                            <div className="ml-0 md:ml-12 flex items-center gap-2 text-xs text-primary animate-pulse">
                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                AI is preparing a deep analysis…
                                            </div>
                                        )}

                                        {/* AI deep explanation */}
                                        {aiExplanations[idx] && (
                                            <div className="ml-0 md:ml-12 space-y-3 pt-2 border-t">
                                                <div className="flex items-center gap-2 pt-2">
                                                    <Brain className="h-4 w-4 text-primary" />
                                                    <span className="text-xs font-bold uppercase tracking-wide text-primary">
                                                        AI Deep Explanation
                                                    </span>
                                                    {aiExplanations[idx].error && (
                                                        <Badge variant="destructive" className="ml-auto">
                                                            AI unavailable
                                                        </Badge>
                                                    )}
                                                </div>

                                                <Separator />

                                                {/* Tags row */}
                                                <div className="flex flex-wrap gap-1.5">
                                                    {aiExplanations[idx].category && (
                                                        <Badge variant="secondary">{aiExplanations[idx].category}</Badge>
                                                    )}
                                                    {aiExplanations[idx].question_type && (
                                                        <Badge variant="outline">{aiExplanations[idx].question_type}</Badge>
                                                    )}
                                                    {aiExplanations[idx].core_concept && (
                                                        <Badge variant="outline" className="border-primary/30 text-primary">
                                                            {aiExplanations[idx].core_concept}
                                                        </Badge>
                                                    )}
                                                </div>

                                                {aiExplanations[idx].why_correct && (
                                                    <ExplanationBlock
                                                        title="Why the correct answer is right"
                                                        accent="emerald"
                                                    >
                                                        {aiExplanations[idx].why_correct!}
                                                    </ExplanationBlock>
                                                )}

                                                {aiExplanations[idx].why_wrong && Object.keys(aiExplanations[idx].why_wrong!).length > 0 && (
                                                    <ExplanationBlock title="Why the other options are wrong" accent="red">
                                                        <div className="space-y-1">
                                                            {Object.entries(aiExplanations[idx].why_wrong!).map(([k, v]) => (
                                                                <p key={k}>
                                                                    <span className="font-semibold">{k}:</span>{' '}
                                                                    <span className="text-muted-foreground">{String(v)}</span>
                                                                </p>
                                                            ))}
                                                        </div>
                                                    </ExplanationBlock>
                                                )}

                                                {aiExplanations[idx].mnemonic && (
                                                    <ExplanationBlock
                                                        title="Mnemonic"
                                                        accent="amber"
                                                        icon={<Sparkles className="h-3.5 w-3.5" />}
                                                    >
                                                        <span className="font-medium">{aiExplanations[idx].mnemonic}</span>
                                                    </ExplanationBlock>
                                                )}

                                                {aiExplanations[idx].textbook_reference?.book && (
                                                    <ExplanationBlock title="Textbook reference" accent="violet" icon={<BookMarked className="h-3.5 w-3.5" />}>
                                                        <p className="font-semibold">{aiExplanations[idx].textbook_reference!.book}</p>
                                                        {aiExplanations[idx].textbook_reference!.chapter && (
                                                            <p className="text-xs text-muted-foreground">
                                                                Chapter: {aiExplanations[idx].textbook_reference!.chapter}
                                                            </p>
                                                        )}
                                                        {aiExplanations[idx].textbook_reference!.page && (
                                                            <p className="text-xs text-muted-foreground">
                                                                Page: {aiExplanations[idx].textbook_reference!.page}
                                                            </p>
                                                        )}
                                                    </ExplanationBlock>
                                                )}

                                                {aiExplanations[idx].high_yield_points && aiExplanations[idx].high_yield_points!.length > 0 && (
                                                    <ExplanationBlock title="High-yield points" accent="pink">
                                                        <ul className="list-disc pl-5 space-y-0.5">
                                                            {aiExplanations[idx].high_yield_points!.map((p, i) => (
                                                                <li key={i}>{p}</li>
                                                            ))}
                                                        </ul>
                                                    </ExplanationBlock>
                                                )}

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                    {aiExplanations[idx].clinical_pearl && (
                                                        <ExplanationBlock title="Clinical pearl" accent="emerald">
                                                            {aiExplanations[idx].clinical_pearl!}
                                                        </ExplanationBlock>
                                                    )}
                                                    {aiExplanations[idx].exam_tip && (
                                                        <ExplanationBlock title="Exam tip" accent="amber">
                                                            {aiExplanations[idx].exam_tip!}
                                                        </ExplanationBlock>
                                                    )}
                                                </div>

                                                {(aiExplanations[idx].pyq_frequency || aiExplanations[idx].similar_pyq) && (
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                                                        {aiExplanations[idx].pyq_frequency && (
                                                            <div className="text-xs p-2.5 rounded-md bg-pink-500/10 border border-pink-500/20">
                                                                <span className="font-semibold text-pink-600 dark:text-pink-400">
                                                                    PYQ frequency:{' '}
                                                                </span>
                                                                {aiExplanations[idx].pyq_frequency}
                                                            </div>
                                                        )}
                                                        {aiExplanations[idx].similar_pyq && (
                                                            <div className="text-xs p-2.5 rounded-md bg-indigo-500/10 border border-indigo-500/20">
                                                                <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                                                                    Similar PYQs:{' '}
                                                                </span>
                                                                {aiExplanations[idx].similar_pyq}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            ))}
                        </div>

                        {/* Empty state */}
                        {!generating && questions.length === 0 && !errorBanner && (
                            <Card>
                                <CardContent className="p-12 text-center">
                                    <div className="mx-auto mb-4 rounded-full bg-primary/10 p-4 w-fit">
                                        <Sparkles className="h-10 w-10 text-primary" />
                                    </div>
                                    <h3 className="text-lg font-bold mb-2">No questions yet</h3>
                                    <p className="text-sm text-muted-foreground max-w-md mx-auto">
                                        Pick a subject above and click{' '}
                                        <span className="font-medium text-foreground">Generate Questions</span>{' '}
                                        to create {count} AI-powered practice MCQs for{' '}
                                        <span className="font-medium text-foreground">{trackMeta.label}</span>.
                                    </p>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </main>
            </div>
        </>
    );
}

/**
 * ExplanationBlock — colour-coded card for a single AI explanation
 * field. Avoids prop-drilling `style={{ background: 'rgba(…)' }}` —
 * the rest of the codebase reads cleaner with explicit classes.
 */
type ExplanationAccent = 'emerald' | 'red' | 'amber' | 'violet' | 'pink';

function ExplanationBlock({
    title,
    accent,
    icon,
    children,
}: {
    title: string;
    accent: ExplanationAccent;
    icon?: React.ReactNode;
    children: React.ReactNode;
}) {
    const accentClass: Record<ExplanationAccent, string> = {
        emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
        red:     'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300',
        amber:   'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
        violet:  'border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300',
        pink:    'border-pink-500/30 bg-pink-500/10 text-pink-700 dark:text-pink-300',
    };
    return (
        <div className={`rounded-md border p-3 text-sm leading-relaxed ${accentClass[accent]}`}>
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide mb-1.5">
                {icon}
                <span>{title}</span>
            </div>
            <div>{children}</div>
        </div>
    );
}