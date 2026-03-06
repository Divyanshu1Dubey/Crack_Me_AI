/**
 * tests/[id]/page.tsx — Test-taking and review page.
 * Modes: (1) Test mode — timed MCQ session with question grid and auto-submit.
 * (2) Review mode — question-by-question review with correct answers,
 * AI-powered deep analysis (mnemonics, explanations, tips), and navigation.
 * Handles token consumption for AI features with 429 error handling.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { testsAPI, aiAPI } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { Send, CheckCircle, Eye, ChevronLeft, ChevronRight, AlertTriangle, Loader2, Brain, Sparkles, BookMarked, Target, Lightbulb, GraduationCap, Zap, BookOpen, ArrowRight, Flag, MessageSquare } from 'lucide-react';

/**
 * Renders medical question text with proper formatting.
 * Converts raw markdown (bold, lists, line breaks) into readable HTML.
 * Handles PYQ-style formatting: **bold**, * list items, Roman numerals.
 */
function FormattedText({ text, className = '' }: { text: string; className?: string }) {
    if (!text) return null;
    // Clean up the text: normalize line breaks for markdown
    const cleaned = text
        .replace(/\*\s+(?=[IVXLC]+\.\s)/g, '\n* ')  // Ensure Roman numeral items start on new lines
        .replace(/\*\s*\*\*Codes/g, '\n\n**Codes')   // Codes section on new line
        .replace(/\*\s+\(/g, '\n* (');                // Option items on new lines
    return (
        <div className={`formatted-text ${className}`}>
            <ReactMarkdown>{cleaned}</ReactMarkdown>
        </div>
    );
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
    correct_answer?: string;
    explanation?: string;
}

interface TestData {
    title: string;
    time_limit_minutes: number;
    num_questions: number;
    negative_marking: boolean;
}

export default function TakeTestPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
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
    const [showConfirm, setShowConfirm] = useState(false);
    const [reviewMode, setReviewMode] = useState(false);
    const [reviewIdx, setReviewIdx] = useState(0);
    const [reviewAiExplanations, setReviewAiExplanations] = useState<Record<number, any>>({});
    const [reviewAiLoading, setReviewAiLoading] = useState(false);
    const [reviewTokenError, setReviewTokenError] = useState(false);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const startTimes = useRef<Record<number, number>>({});
    const timeSpent = useRef<Record<number, number>>({});
    const doSubmitRef = useRef<() => void>(() => {});

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated && testId) {
            testsAPI.start(testId).then(res => {
                setTest(res.data.test);
                setQuestions(res.data.questions);
                setAttemptId(res.data.attempt_id);
                setTimeLeft(res.data.test.time_limit_minutes * 60);
                startTimes.current[0] = Date.now();
            }).finally(() => setLoading(false));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [authLoading, isAuthenticated, testId]);

    // Timer — uses ref to avoid stale closure
    useEffect(() => {
        if (timeLeft > 0 && !submitted) {
            timerRef.current = setInterval(() => {
                setTimeLeft(prev => {
                    if (prev <= 1) {
                        doSubmitRef.current();
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);
        }
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
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
        if (!attemptId || submitted) return;
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
            setResult(res.data);
            setSubmitted(true);
            setShowConfirm(false);
            // Fetch full review data with correct answers & explanations
            try {
                const reviewRes = await testsAPI.review(testId, attemptId);
                setReviewData(reviewRes.data.questions || []);
            } catch { /* review fetch is non-critical */ }
        } catch (err) {
            console.error('Submit failed:', err);
        }
    }, [attemptId, submitted, currentIdx, questions, answers, testId]);

    // Keep ref in sync so timer always calls latest doSubmit
    useEffect(() => { doSubmitRef.current = doSubmit; }, [doSubmit]);

    // NOTE: AI explanation is NO LONGER auto-fetched.
    // Students must click "Generate AI Analysis" to save API tokens.

    const handleSubmit = () => setShowConfirm(true);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
                <div className="animate-pulse text-xl gradient-text">Loading Test...</div>
            </div>
        );
    }

    // ─── REVIEW MODE ────────────────────────────────────
    if (submitted && result && reviewMode) {
        const rq = questions[reviewIdx];
        // Match review data by question_id, not by index (order may differ)
        const rd = reviewData ? reviewData.find((r: any) => r.question_id === rq?.id) : null;
        const userAns = rd?.selected_answer || answers[rq?.id];
        const correctAns = rd?.correct_answer || rq?.correct_answer;
        const explanation = rd?.explanation || rq?.explanation;
        const aiExp = reviewAiExplanations[reviewIdx];

        const fetchAiExplanation = (idx: number) => {
            if (reviewAiExplanations[idx] || reviewTokenError) return;
            const q = questions[idx];
            if (!q) return;
            const rrd = reviewData ? reviewData.find((r: any) => r.question_id === q.id) : null;
            setReviewAiLoading(true);
            aiAPI.explainAfterAnswer({
                question_text: q.question_text,
                options: { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d },
                correct_answer: rrd?.correct_answer || q.correct_answer || '',
                selected_answer: rrd?.selected_answer || answers[q.id] || '',
                subject: rrd?.subject || q.subject_name || '',
                topic: rrd?.topic || q.topic_name || '',
            }).then(res => {
                setReviewAiExplanations(prev => ({ ...prev, [idx]: res.data }));
            }).catch((err) => {
                if (err?.response?.status === 429) {
                    setReviewTokenError(true);
                }
            }).finally(() => setReviewAiLoading(false));
        };

        return (
            <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
                {/* Sticky Header */}
                <div className="sticky top-0 z-50 px-4 md:px-6 py-3 flex items-center justify-between" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                    <div className="flex items-center gap-3">
                        <span className="font-bold text-base gradient-text">📖 REVIEW MODE</span>
                        <span className="hidden sm:inline text-xs px-2 py-1 rounded-full" style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)' }}>{test?.title} — {questions.length} Questions</span>
                    </div>
                    <div className="flex items-center gap-2">
                        {/* Mini question nav dots */}
                        <div className="hidden md:flex items-center gap-1 flex-wrap max-w-[500px]">
                            {questions.map((q, i) => {
                                const qrd = reviewData?.find((r: any) => r.question_id === q.id);
                                const isCorrect = qrd?.is_correct === true;
                                const isWrong = qrd?.is_correct === false;
                                return (
                                    <button key={i} onClick={() => setReviewIdx(i)}
                                        className="w-7 h-7 rounded-full text-xs font-bold transition-all flex items-center justify-center"
                                        style={{
                                            background: i === reviewIdx ? 'var(--accent-primary)' : isCorrect ? 'rgba(16,185,129,0.15)' : isWrong ? 'rgba(239,68,68,0.15)' : 'var(--bg-card)',
                                            color: i === reviewIdx ? 'white' : isCorrect ? '#10b981' : isWrong ? '#ef4444' : 'var(--text-secondary)',
                                            border: i === reviewIdx ? '2px solid var(--accent-primary)' : '1px solid transparent',
                                            transform: i === reviewIdx ? 'scale(1.2)' : 'scale(1)',
                                        }}>
                                        {i + 1}
                                    </button>
                                );
                            })}
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
                                        {rd?.is_correct ? 'Correct! Great job 🎉' : rd?.is_correct === false ? 'Incorrect — Study the explanation below carefully' : 'Skipped — Review what you missed'}
                                    </div>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {rq?.subject_name && <span className="review-tag review-tag-cyan">{rq.subject_name}</span>}
                                {(rd?.topic || rq?.topic_name) && <span className="review-tag review-tag-purple">{rd?.topic || rq?.topic_name}</span>}
                                {rd?.difficulty && <span className={`review-tag ${rd.difficulty === 'hard' ? 'review-tag-red' : rd.difficulty === 'medium' ? 'review-tag-amber' : 'review-tag-green'}`}>{rd.difficulty}</span>}
                                {rd?.year && <span className="review-tag review-tag-pink">PYQ {rd.year}</span>}
                            </div>
                        </div>

                        {/* Question Text — rendered with markdown for proper bold/list formatting */}
                        <div className="p-5 md:p-6">
                            <div className="text-base md:text-lg font-medium leading-relaxed mb-6" style={{ color: 'var(--text-primary)' }}>
                                <FormattedText text={rq?.question_text || ''} />
                            </div>

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
                                    const isCorrect = correctAns === opt;
                                    const isUserPick = userAns === opt;
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
                        </div>
                    </div>

                    {/* ═══ DB EXPLANATION (always show first if available) ═══ */}
                    {explanation && (
                        <div className="explanation-card explanation-card-green animate-fadeInUp">
                            <div className="explanation-card-accent green"></div>
                            <div className="p-5 pl-6">
                                <h4 className="explanation-card-title green"><CheckCircle className="w-4 h-4" /> Answer Explanation</h4>
                                <p className="text-sm leading-relaxed mt-2" style={{ color: 'var(--text-secondary)' }}>{String(explanation)}</p>
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

                    {/* ═══ AI GENERATE BUTTON — only triggers on click to save API tokens ═══ */}
                    {!aiExp && !reviewAiLoading && !reviewTokenError && (
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
                    {reviewTokenError && !aiExp && (
                        <div className="token-depleted-banner">
                            <div className="flex items-start gap-3">
                                <Zap className="w-5 h-5 mt-0.5 shrink-0" style={{ color: '#ef4444' }} />
                                <div>
                                    <h5 className="text-sm font-bold" style={{ color: '#ef4444' }}>AI Tokens Exhausted</h5>
                                    <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                        Your daily/weekly free tokens have been used up. Purchase more tokens to continue using AI features.
                                    </p>
                                    <a href="/tokens" className="btn-primary text-xs mt-3 inline-flex">
                                        <Zap className="w-3 h-3" /> Buy Tokens
                                    </a>
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
                                    {aiExp.pyq_frequency && <p className="text-sm mb-1.5" style={{ color: 'var(--text-secondary)' }}>📈 <strong style={{ color: '#ec4899' }}>Frequency:</strong> {aiExp.pyq_frequency}</p>}
                                    {aiExp.similar_pyq && <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>📋 <strong style={{ color: '#818cf8' }}>Similar Questions:</strong> {aiExp.similar_pyq}</p>}
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
                    <div className="flex items-center justify-between py-4 sticky bottom-0" style={{ background: 'var(--bg-primary)' }}>
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
        );
    }

    // ─── RESULTS SCREEN ─────────────────────────────────
    if (submitted && result) {
        return (
            <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen flex items-center justify-center p-8">
                <div className="glass-card p-8 max-w-lg w-full text-center animate-fadeInUp">
                    <CheckCircle className="w-16 h-16 mx-auto mb-4" style={{ color: '#10b981' }} />
                    <h1 className="text-2xl font-bold mb-2">Test Completed!</h1>
                    <p className="mb-6" style={{ color: 'var(--text-secondary)' }}>{test?.title}</p>

                    <div className="grid grid-cols-3 gap-4 mb-6">
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

    const answeredCount = Object.keys(answers).length;
    const markedCount = marked.size;
    const notVisitedCount = questions.length - Math.max(currentIdx + 1, Object.keys(startTimes.current).length);
    const notAnsweredCount = questions.length - answeredCount;

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen flex flex-col">
            {/* Confirm Dialog */}
            {showConfirm && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
                    <div className="glass-card p-8 max-w-sm w-full mx-4 text-center animate-fadeInUp">
                        <AlertTriangle className="w-12 h-12 mx-auto mb-4" style={{ color: '#f59e0b' }} />
                        <h3 className="text-xl font-bold mb-2">Submit Test?</h3>
                        <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                            You have answered <strong style={{ color: 'var(--text-primary)' }}>{answeredCount}</strong> of <strong style={{ color: 'var(--text-primary)' }}>{questions.length}</strong> questions.
                        </p>
                        {notAnsweredCount > 0 && (
                            <p className="text-sm mb-6" style={{ color: '#f59e0b' }}>
                                {notAnsweredCount} question{notAnsweredCount > 1 ? 's' : ''} unanswered!
                            </p>
                        )}
                        <div className="flex gap-3">
                            <button onClick={() => setShowConfirm(false)} className="btn-secondary flex-1">Go Back</button>
                            <button onClick={doSubmit} className="btn-primary flex-1 justify-center" style={{ background: '#10b981' }}>
                                <Send className="w-4 h-4" /> Confirm
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Top Bar */}
            <div className="sticky top-0 z-50 px-6 py-3 flex items-center justify-between"
                style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                <div className="flex items-center gap-4">
                    <div className="font-bold text-lg gradient-text">UPSC CMS SIMULATOR</div>
                    <div className="text-sm px-3 py-1 rounded-full" style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)' }}>{test?.title}</div>
                </div>
                <div className="flex items-center gap-4">
                    <div className={`flex items-center gap-2 font-mono text-xl font-bold px-4 py-2 rounded-lg ${timeLeft < 300 ? 'animate-pulse' : ''}`}
                        style={{ background: timeLeft < 300 ? 'rgba(239,68,68,0.15)' : 'var(--bg-card)', color: timeLeft < 300 ? '#ef4444' : 'var(--text-primary)' }}>
                        ⏱ {formatTime(timeLeft)}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col lg:flex-row max-w-[1600px] mx-auto w-full p-4 gap-4">

                {/* Left: Question */}
                <div className="flex-1 glass-card flex flex-col overflow-hidden">
                    <div className="px-6 py-3 flex justify-between items-center" style={{ borderBottom: '1px solid var(--glass-border)', background: 'var(--bg-secondary)' }}>
                        <span className="font-bold text-lg">Question {currentIdx + 1}</span>
                        <div className="flex gap-2 text-sm">
                            <span className="badge" style={{ background: 'rgba(6,182,212,0.1)', color: 'var(--accent-primary)' }}>{currentQ.subject_name}</span>
                            {currentQ.topic_name && <span className="badge" style={{ background: 'rgba(139,92,246,0.1)', color: 'var(--accent-secondary)' }}>{currentQ.topic_name}</span>}
                        </div>
                    </div>

                    <div className="p-8 flex-1 overflow-y-auto" style={{ minHeight: '400px' }}>
                        <div className="text-lg leading-relaxed font-medium mb-10 pb-6" style={{ borderBottom: '1px solid var(--glass-border)' }}>
                            <FormattedText text={currentQ.question_text} />
                        </div>
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

                    <div className="px-6 py-4 flex items-center justify-between" style={{ borderTop: '1px solid var(--glass-border)', background: 'var(--bg-secondary)' }}>
                        <div className="flex gap-3">
                            <button onClick={handleClear} className="btn-secondary text-sm">Clear</button>
                            <button onClick={handleMarkAndNext} className="text-sm px-4 py-2 rounded-lg font-semibold transition-colors"
                                style={{ background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)' }}>
                                Mark & Next
                            </button>
                        </div>
                        <div className="flex gap-3">
                            <button onClick={() => goTo(Math.max(0, currentIdx - 1))} disabled={currentIdx === 0} className="btn-secondary text-sm">
                                <ChevronLeft className="w-4 h-4" /> Prev
                            </button>
                            <button onClick={handleSaveAndNext} className="btn-primary text-sm">
                                Save & Next <ChevronRight className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right Sidebar */}
                <div className="w-full lg:w-72 flex flex-col gap-4">
                    <div className="glass-card p-4 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg" style={{ background: 'var(--accent-primary)', color: 'white' }}>
                            {test?.title.charAt(0)}
                        </div>
                        <div>
                            <div className="font-bold text-sm">{test?.title}</div>
                            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>UPSC CMS Mock</div>
                        </div>
                    </div>

                    <div className="glass-card p-4">
                        <div className="font-bold text-sm mb-3">Legend</div>
                        <div className="grid grid-cols-2 gap-y-3 gap-x-2 text-xs font-semibold">
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs" style={{ background: '#10b981' }}>{answeredCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Answered</span></div>
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs" style={{ background: '#ef4444' }}>{notAnsweredCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Not Answered</span></div>
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-xs" style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)' }}>{notVisitedCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Not Visited</span></div>
                            <div className="flex items-center gap-2"><span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs" style={{ background: '#8b5cf6' }}>{markedCount}</span> <span style={{ color: 'var(--text-secondary)' }}>Marked</span></div>
                        </div>
                    </div>

                    <div className="glass-card p-4 flex-1 flex flex-col min-h-[300px]">
                        <div className="font-bold text-sm mb-3 flex justify-between items-center">
                            <span>Question Palette</span>
                            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{questions.length} Qs</span>
                        </div>
                        <div className="flex-1 overflow-y-auto pr-1">
                            <div className="grid grid-cols-5 gap-2">
                                {questions.map((q, i) => {
                                    const answered = !!answers[q.id];
                                    const isMarked = marked.has(i);
                                    const isCurrent = i === currentIdx;
                                    let bg = 'var(--bg-card)'; let color = 'var(--text-secondary)'; let border = 'var(--glass-border)';
                                    if (answered) { bg = '#10b981'; color = 'white'; border = '#059669'; }
                                    else if (isMarked) { bg = '#8b5cf6'; color = 'white'; border = '#7c3aed'; }
                                    else if (startTimes.current[i]) { bg = '#ef4444'; color = 'white'; border = '#dc2626'; }
                                    return (
                                        <button key={i} onClick={() => goTo(i)}
                                            className="w-full aspect-square rounded flex items-center justify-center text-xs font-bold transition-all"
                                            style={{ background: bg, color, border: `2px solid ${border}`, outline: isCurrent ? '2px solid var(--accent-primary)' : 'none', outlineOffset: '2px', transform: isCurrent ? 'scale(1.1)' : 'none' }}>
                                            {i + 1}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--glass-border)' }}>
                            <button onClick={handleSubmit}
                                className="w-full py-3 rounded-lg font-bold text-lg flex justify-center items-center gap-2 transition-colors"
                                style={{ background: '#10b981', color: 'white' }}>
                                <Send className="w-5 h-5" /> Submit Test
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
