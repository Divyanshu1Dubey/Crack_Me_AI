/**
 * generate/page.tsx — AI Question Generator page.
 * Generates custom MCQ questions using AI based on subject/topic/difficulty.
 * Features: subject/topic selector, difficulty toggle, question preview,
 * answer reveal with AI explanation. Token consumption with 429 handling.
 */
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { aiAPI, questionsAPI } from '@/lib/api';
import { Sparkles, Loader2, CheckCircle, XCircle, ChevronDown, RefreshCw, Brain, BookMarked, Target } from 'lucide-react';

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

interface Subject {
    id: number;
    name: string;
    code: string;
}

export default function GeneratePage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [selectedSubject, setSelectedSubject] = useState('Medicine');
    const [topic, setTopic] = useState('');
    const [difficulty, setDifficulty] = useState('medium');
    const [count, setCount] = useState(5);
    const [generating, setGenerating] = useState(false);
    const [questions, setQuestions] = useState<GeneratedQuestion[]>([]);
    const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
    const [showExplanations, setShowExplanations] = useState<Record<number, boolean>>({});
    const [aiExplanations, setAiExplanations] = useState<Record<number, Record<string, unknown>>>({});
    const [aiLoadingIdx, setAiLoadingIdx] = useState<number | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (isAuthenticated) {
            questionsAPI.getSubjects().then(res => {
                const list = res.data?.results || res.data;
                if (list?.length) setSubjects(list);
            }).catch(() => { });
        }
    }, [isAuthenticated]);

    const handleGenerate = async () => {
        setGenerating(true);
        setQuestions([]);
        setSelectedAnswers({});
        setShowExplanations({});
        try {
            const res = await aiAPI.generateQuestions({
                subject: selectedSubject,
                topic: topic || undefined,
                difficulty,
                count,
            });
            if (res.data?.questions) {
                setQuestions(res.data.questions.filter((q: GeneratedQuestion) => !q.error));
            }
        } catch (err: unknown) {
            const error = err as { response?: { status?: number; data?: { error?: string } }; message?: string };
            if (error.response?.status === 429) {
                setQuestions([{ question_text: 'AI Tokens Exhausted — Your daily/weekly tokens are used up. Visit /tokens to buy more.', option_a: '', option_b: '', option_c: '', option_d: '', correct_answer: '', explanation: '' } as GeneratedQuestion]);
            } else {
                const msg = error.response?.data?.error || error.message || 'AI service unavailable';
                setQuestions([{ question_text: `⚠️ ${msg}. Please try again.`, option_a: '', option_b: '', option_c: '', option_d: '', correct_answer: '', explanation: '' } as GeneratedQuestion]);
            }
        }
        setGenerating(false);
    };

    const selectAnswer = (qIdx: number, option: string) => {
        if (selectedAnswers[qIdx]) return; // Already answered
        setSelectedAnswers(prev => ({ ...prev, [qIdx]: option }));
        setShowExplanations(prev => ({ ...prev, [qIdx]: true }));
        // Call AI for deep explanation
        const q = questions[qIdx];
        if (q) {
            setAiLoadingIdx(qIdx);
            aiAPI.explainAfterAnswer({
                question_text: q.question_text,
                options: { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d },
                correct_answer: q.correct_answer,
                selected_answer: option,
                subject: q.subject || '',
                topic: q.topic || '',
            }).then(res => {
                setAiExplanations(prev => ({ ...prev, [qIdx]: res.data }));
            }).catch((err) => {
                const errMsg = err?.response?.data?.error || 'AI unavailable';
                setAiExplanations(prev => ({ ...prev, [qIdx]: { why_correct: errMsg, error: true } }));
            }).finally(() => {
                setAiLoadingIdx(null);
            });
        }
    };

    const getOptionClass = (qIdx: number, optKey: string) => {
        const selected = selectedAnswers[qIdx];
        const correct = questions[qIdx]?.correct_answer;
        if (!selected) return 'glass-card hover:scale-[1.01] cursor-pointer';
        if (optKey === correct) return 'border-2 border-green-500 bg-green-500/10';
        if (optKey === selected && optKey !== correct) return 'border-2 border-red-500 bg-red-500/10';
        return 'opacity-50';
    };

    if (authLoading) return null;

    const subjectOptions = subjects.length > 0
        ? subjects.map(s => s.name)
        : ['Medicine', 'Surgery', 'Pediatrics', 'Obstetrics & Gynaecology', 'Preventive & Social Medicine'];

    return (
        <div className="min-h-screen flex bg-background">
            <Sidebar />
            <main className="flex-1 p-8 overflow-y-auto">
                <div className="max-w-4xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center gap-3 mb-2">
                        <Sparkles className="w-8 h-8" style={{ color: 'var(--accent-primary)' }} />
                        <h1 className="text-2xl font-bold">AI Question Generator</h1>
                    </div>
                    <p className="mb-8" style={{ color: 'var(--text-secondary)' }}>
                        Generate unlimited AI-powered practice MCQs on any CMS topic
                    </p>

                    {/* Controls */}
                    <div className="glass-card p-6 mb-8">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                            {/* Subject */}
                            <div>
                                <label className="block text-sm font-medium mb-1">Subject</label>
                                <div className="relative">
                                    <select
                                        value={selectedSubject}
                                        onChange={e => setSelectedSubject(e.target.value)}
                                        className="w-full px-3 py-2 rounded-lg border text-sm appearance-none pr-8"
                                        style={{
                                            background: 'var(--bg-secondary)',
                                            borderColor: 'var(--border-color)',
                                            color: 'var(--text-primary)'
                                        }}
                                    >
                                        {subjectOptions.map(s => (
                                            <option key={s} value={s}>{s}</option>
                                        ))}
                                    </select>
                                    <ChevronDown className="w-4 h-4 absolute right-2 top-3 pointer-events-none" style={{ color: 'var(--text-secondary)' }} />
                                </div>
                            </div>

                            {/* Topic */}
                            <div>
                                <label className="block text-sm font-medium mb-1">Topic (optional)</label>
                                <input
                                    type="text"
                                    value={topic}
                                    onChange={e => setTopic(e.target.value)}
                                    placeholder="e.g., Cardiology, Vaccines"
                                    className="w-full px-3 py-2 rounded-lg border text-sm"
                                    style={{
                                        background: 'var(--bg-secondary)',
                                        borderColor: 'var(--border-color)',
                                        color: 'var(--text-primary)'
                                    }}
                                />
                            </div>

                            {/* Difficulty */}
                            <div>
                                <label className="block text-sm font-medium mb-1">Difficulty</label>
                                <div className="relative">
                                    <select
                                        value={difficulty}
                                        onChange={e => setDifficulty(e.target.value)}
                                        className="w-full px-3 py-2 rounded-lg border text-sm appearance-none pr-8"
                                        style={{
                                            background: 'var(--bg-secondary)',
                                            borderColor: 'var(--border-color)',
                                            color: 'var(--text-primary)'
                                        }}
                                    >
                                        <option value="easy">Easy</option>
                                        <option value="medium">Medium</option>
                                        <option value="hard">Hard</option>
                                    </select>
                                    <ChevronDown className="w-4 h-4 absolute right-2 top-3 pointer-events-none" style={{ color: 'var(--text-secondary)' }} />
                                </div>
                            </div>

                            {/* Count */}
                            <div>
                                <label className="block text-sm font-medium mb-1">Questions</label>
                                <div className="relative">
                                    <select
                                        value={count}
                                        onChange={e => setCount(Number(e.target.value))}
                                        className="w-full px-3 py-2 rounded-lg border text-sm appearance-none pr-8"
                                        style={{
                                            background: 'var(--bg-secondary)',
                                            borderColor: 'var(--border-color)',
                                            color: 'var(--text-primary)'
                                        }}
                                    >
                                        {[3, 5, 10, 15, 20].map(n => (
                                            <option key={n} value={n}>{n}</option>
                                        ))}
                                    </select>
                                    <ChevronDown className="w-4 h-4 absolute right-2 top-3 pointer-events-none" style={{ color: 'var(--text-secondary)' }} />
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={handleGenerate}
                            disabled={generating}
                            className="btn-primary gap-2"
                        >
                            {generating ? (
                                <><Loader2 className="w-4 h-4 animate-spin" /> Generating {count} Questions...</>
                            ) : (
                                <><Sparkles className="w-4 h-4" /> Generate Questions</>
                            )}
                        </button>
                    </div>

                    {/* Results */}
                    {questions.length > 0 && (
                        <div className="space-y-6">
                            <div className="flex items-center justify-between">
                                <h2 className="text-lg font-bold">{questions.length} Questions Generated</h2>
                                <button onClick={handleGenerate} className="text-sm flex items-center gap-1" style={{ color: 'var(--accent-primary)' }}>
                                    <RefreshCw className="w-4 h-4" /> Regenerate
                                </button>
                            </div>

                            {/* Score Summary */}
                            {Object.keys(selectedAnswers).length === questions.length && (
                                <div className="glass-card p-5 text-center">
                                    <div className="text-3xl font-bold gradient-text">
                                        {Object.entries(selectedAnswers).filter(([idx, ans]) =>
                                            ans === questions[Number(idx)]?.correct_answer
                                        ).length} / {questions.length}
                                    </div>
                                    <div className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                                        Score — {Math.round(Object.entries(selectedAnswers).filter(([idx, ans]) =>
                                            ans === questions[Number(idx)]?.correct_answer
                                        ).length / questions.length * 100)}%
                                    </div>
                                </div>
                            )}

                            {questions.map((q, idx) => (
                                <div key={idx} className="glass-card p-6">
                                    {/* Question Number & Header */}
                                    <div className="flex items-start gap-3 mb-4">
                                        <span className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
                                            style={{ background: 'var(--accent-primary)', color: 'white' }}>
                                            {idx + 1}
                                        </span>
                                        <div className="flex-1">
                                            <p className="font-medium leading-relaxed">{q.question_text}</p>
                                            <div className="flex gap-2 mt-2">
                                                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
                                                    {q.subject}
                                                </span>
                                                {q.topic && (
                                                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
                                                        {q.topic}
                                                    </span>
                                                )}
                                                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
                                                    {q.difficulty}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Options */}
                                    <div className="space-y-2 ml-11">
                                        {['A', 'B', 'C', 'D'].map(opt => {
                                            const optKey = `option_${opt.toLowerCase()}` as keyof GeneratedQuestion;
                                            const optValue = q[optKey] as string;
                                            if (!optValue) return null;
                                            return (
                                                <div
                                                    key={opt}
                                                    onClick={() => selectAnswer(idx, opt)}
                                                    className={`p-3 rounded-lg transition-all flex items-center gap-3 ${getOptionClass(idx, opt)}`}
                                                    style={{ background: selectedAnswers[idx] ? undefined : 'var(--bg-secondary)' }}
                                                >
                                                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                                                        style={{
                                                            border: '2px solid var(--border-color)',
                                                            color: 'var(--text-secondary)'
                                                        }}>
                                                        {opt}
                                                    </span>
                                                    <span className="text-sm">{optValue}</span>
                                                    {selectedAnswers[idx] && opt === q.correct_answer && (
                                                        <CheckCircle className="w-5 h-5 text-green-400 ml-auto flex-shrink-0" />
                                                    )}
                                                    {selectedAnswers[idx] === opt && opt !== q.correct_answer && (
                                                        <XCircle className="w-5 h-5 text-red-400 ml-auto flex-shrink-0" />
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>

                                    {/* Explanation */}
                                    {showExplanations[idx] && q.explanation && (
                                        <div className="mt-4 ml-11 p-4 rounded-lg border"
                                            style={{ background: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}>
                                            <div className="text-sm font-semibold mb-2" style={{ color: 'var(--accent-primary)' }}>
                                                Explanation
                                            </div>
                                            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                                {q.explanation}
                                            </p>
                                        </div>
                                    )}

                                    {/* AI Loading */}
                                    {aiLoadingIdx === idx && (
                                        <div className="mt-3 ml-11 p-4 rounded-lg flex items-center gap-3 animate-pulse" style={{ background: 'rgba(6,182,212,0.08)', border: '1px solid rgba(6,182,212,0.2)' }}>
                                            <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                                            <span className="text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>AI generating deep analysis...</span>
                                        </div>
                                    )}

                                    {/* AI Deep Explanation */}
                                    {aiExplanations[idx] && (
                                        <div className="mt-3 ml-11 space-y-3">
                                            <div className="flex items-center gap-2">
                                                <Brain className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                                                <span className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--accent-primary)' }}>🧠 AI Deep Explanation</span>
                                            </div>

                                            {/* Category & Question Type Tags */}
                                            <div className="flex flex-wrap gap-1.5">
                                                {aiExplanations[idx].category && (
                                                    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: 'rgba(6,182,212,0.1)', color: '#06b6d4', border: '1px solid rgba(6,182,212,0.2)' }}>
                                                        📂 {String(aiExplanations[idx].category)}
                                                    </span>
                                                )}
                                                {aiExplanations[idx].sub_category && (
                                                    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: 'rgba(139,92,246,0.1)', color: '#8b5cf6', border: '1px solid rgba(139,92,246,0.2)' }}>
                                                        📁 {String(aiExplanations[idx].sub_category)}
                                                    </span>
                                                )}
                                                {aiExplanations[idx].question_type && (
                                                    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)' }}>
                                                        🏷️ {String(aiExplanations[idx].question_type)}
                                                    </span>
                                                )}
                                                {aiExplanations[idx].core_concept && (
                                                    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)' }}>
                                                        🎯 {String(aiExplanations[idx].core_concept)}
                                                    </span>
                                                )}
                                            </div>

                                            {aiExplanations[idx].why_correct && (
                                                <div className="p-3 rounded-lg" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }}>
                                                    <h6 className="text-xs font-bold mb-1" style={{ color: '#10b981' }}>✅ Why Correct</h6>
                                                    <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{String(aiExplanations[idx].why_correct)}</p>
                                                </div>
                                            )}

                                            {aiExplanations[idx].why_wrong && typeof aiExplanations[idx].why_wrong === 'object' && Object.keys(aiExplanations[idx].why_wrong as object).length > 0 && (
                                                <div className="p-3 rounded-lg" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}>
                                                    <h6 className="text-xs font-bold mb-1" style={{ color: '#ef4444' }}>❌ Why Others Wrong</h6>
                                                    <div className="space-y-1">
                                                        {Object.entries(aiExplanations[idx].why_wrong as Record<string, string>).map(([k, v]) => (
                                                            <p key={k} className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                                                <strong className="font-bold" style={{ color: '#ef4444' }}>{k}:</strong> {String(v)}
                                                            </p>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {aiExplanations[idx].textbook_reference && typeof aiExplanations[idx].textbook_reference === 'object' && (aiExplanations[idx].textbook_reference as any).book && (
                                                <div className="p-3 rounded-lg flex items-start gap-2" style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)' }}>
                                                    <BookMarked className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: '#8b5cf6' }} />
                                                    <div>
                                                        <h6 className="text-xs font-bold" style={{ color: '#8b5cf6' }}>📚 Textbook Reference</h6>
                                                        <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>{String((aiExplanations[idx].textbook_reference as any).book)}</p>
                                                        {(aiExplanations[idx].textbook_reference as any).chapter && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Chapter: {String((aiExplanations[idx].textbook_reference as any).chapter)}</p>}
                                                        {(aiExplanations[idx].textbook_reference as any).page && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Page: {String((aiExplanations[idx].textbook_reference as any).page)}</p>}
                                                        {(aiExplanations[idx].textbook_reference as any).section && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Section: {String((aiExplanations[idx].textbook_reference as any).section)}</p>}
                                                    </div>
                                                </div>
                                            )}

                                            {aiExplanations[idx].mnemonic && (
                                                <div className="p-3 rounded-lg flex items-start gap-2" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
                                                    <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: '#f59e0b' }} />
                                                    <div>
                                                        <h6 className="text-xs font-bold" style={{ color: '#f59e0b' }}>💡 Mnemonic</h6>
                                                        <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{String(aiExplanations[idx].mnemonic)}</p>
                                                    </div>
                                                </div>
                                            )}

                                            {Array.isArray(aiExplanations[idx].high_yield_points) && (aiExplanations[idx].high_yield_points as any[]).length > 0 && (
                                                <div className="p-3 rounded-lg" style={{ background: 'rgba(236,72,153,0.06)', border: '1px solid rgba(236,72,153,0.15)' }}>
                                                    <h6 className="text-xs font-bold mb-1" style={{ color: '#ec4899' }}>🔥 High Yield Points</h6>
                                                    <ul className="space-y-0.5">
                                                        {(aiExplanations[idx].high_yield_points as string[]).map((p: string, i: number) => (
                                                            <li key={i} className="text-xs flex gap-1.5 leading-relaxed" style={{ color: 'var(--text-secondary)' }}><span style={{ color: '#ec4899' }}>•</span>{p}</li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {Array.isArray(aiExplanations[idx].around_concepts) && (aiExplanations[idx].around_concepts as any[]).length > 0 && (
                                                <div>
                                                    <h6 className="text-xs font-bold mb-1.5" style={{ color: '#6366f1' }}>🔗 Related Concepts</h6>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {(aiExplanations[idx].around_concepts as string[]).map((c: string, i: number) => (
                                                            <span key={i} className="text-xs px-2 py-1 rounded-full" style={{ background: 'rgba(99,102,241,0.1)', color: '#6366f1', border: '1px solid rgba(99,102,241,0.2)' }}>{c}</span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            <div className="grid grid-cols-2 gap-2">
                                                {aiExplanations[idx].clinical_pearl && (
                                                    <div className="p-3 rounded-lg" style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.15)' }}>
                                                        <h6 className="text-xs font-bold mb-1" style={{ color: '#10b981' }}>💎 Clinical Pearl</h6>
                                                        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{String(aiExplanations[idx].clinical_pearl)}</p>
                                                    </div>
                                                )}
                                                {aiExplanations[idx].exam_tip && (
                                                    <div className="p-3 rounded-lg" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)' }}>
                                                        <h6 className="text-xs font-bold mb-1" style={{ color: '#f59e0b' }}>🎓 Exam Tip</h6>
                                                        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{String(aiExplanations[idx].exam_tip)}</p>
                                                    </div>
                                                )}
                                            </div>

                                            {/* PYQ Frequency & Similar Questions */}
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                {aiExplanations[idx].pyq_frequency && (
                                                    <div className="p-2.5 rounded-lg flex items-center gap-2" style={{ background: 'rgba(236,72,153,0.06)', border: '1px solid rgba(236,72,153,0.15)' }}>
                                                        <Target className="w-3.5 h-3.5 flex-shrink-0" style={{ color: '#ec4899' }} />
                                                        <span className="text-xs font-medium" style={{ color: '#ec4899' }}>PYQ: {String(aiExplanations[idx].pyq_frequency)}</span>
                                                    </div>
                                                )}
                                                {aiExplanations[idx].similar_pyq && (
                                                    <div className="p-2.5 rounded-lg flex items-start gap-2" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)' }}>
                                                        <Target className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#6366f1' }} />
                                                        <span className="text-xs font-medium" style={{ color: '#6366f1' }}>📋 {String(aiExplanations[idx].similar_pyq)}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Empty state */}
                    {!generating && questions.length === 0 && (
                        <div className="glass-card p-12 text-center">
                            <Sparkles className="w-12 h-12 mx-auto mb-4" style={{ color: 'var(--text-secondary)', opacity: 0.4 }} />
                            <h3 className="text-lg font-bold mb-2">No Questions Yet</h3>
                            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                Select a subject and click &quot;Generate Questions&quot; to create AI-powered practice MCQs
                            </p>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
