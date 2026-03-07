/**
 * questions/page.tsx — Question Bank browser page.
 * Left panel: Filterable, paginated question list with subject/year/difficulty filters.
 * Right panel: Question detail with options, answer reveal, AI-powered deep analysis.
 * AI analysis includes: mnemonics, why correct/wrong, topic deep dive, high yield points,
 * key differentiators, textbook references, clinical pearls, exam tips, quick revision,
 * related concepts, PYQ intelligence. Requires token consumption (429 handling included).
 * Helper functions: FormattedText (markdown→HTML), stripMarkdown (plain text preview),
 * cleanOptionText (removes trailing asterisks), cleanAiText (strips JSON artifacts).
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { questionsAPI, aiAPI } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { BookOpen, Search, Filter, Bookmark, Eye, ChevronLeft, ChevronRight, Loader2, Brain, Sparkles, Target, BookMarked, Lightbulb, CheckCircle, Zap, GraduationCap, ArrowRight, Flag } from 'lucide-react';

/**
 * Renders medical question text with proper formatting.
 * Converts raw markdown (bold, lists) into readable HTML.
 */
function FormattedText({ text, className = '' }: { text: string; className?: string }) {
    if (!text) return null;
    const cleaned = text
        .replace(/\*\s+(?=[IVXLC]+\.\s)/g, '\n* ')
        .replace(/\*\s*\*\*Codes/g, '\n\n**Codes')
        .replace(/\*\s+\(/g, '\n* (');
    return (
        <div className={`formatted-text ${className}`}>
            <ReactMarkdown>{cleaned}</ReactMarkdown>
        </div>
    );
}

/** Strips markdown symbols for plain-text previews (list cards, etc.) */
function stripMarkdown(text: string): string {
    return text
        .replace(/\*\*(.+?)\*\*/g, '$1')   // **bold** → bold
        .replace(/\*([^*]+)\*/g, '$1')      // *italic* → italic
        .replace(/\*+/g, '')                // leftover asterisks
        .replace(/__(.+?)__/g, '$1')        // __underline__
        .replace(/#+\s?/g, '')              // # headings
        .replace(/`([^`]+)`/g, '$1')        // `code`
        .replace(/\s{2,}/g, ' ')            // collapse whitespace
        .trim();
}

/** Cleans option text — removes trailing asterisks/stars from PYQ data */
function cleanOptionText(text: string): string {
    return text.replace(/\s*\*+\s*$/, '').trim();
}

/** Cleans AI response text — strips JSON/code fence artifacts that appear when AI parsing fails */
function cleanAiText(text: string): string {
    if (!text) return text;
    let t = text.trim();
    // Strip code fences: ```json ... ```
    if (t.startsWith('```')) t = t.replace(/^```\w*\n?/, '');
    if (t.endsWith('```')) t = t.slice(0, -3);
    t = t.trim();
    // If it looks like a JSON object, try to extract the why_correct field
    if (t.startsWith('{')) {
        try {
            const parsed = JSON.parse(t);
            if (parsed.why_correct) return parsed.why_correct;
        } catch { /* not valid JSON, continue */ }
    }
    // Strip leading "json" keyword
    if (t.toLowerCase().startsWith('json')) t = t.slice(4).trim();
    return t;
}

interface Question {
    id: number;
    question_text: string;
    year: number;
    subject: number;
    subject_name: string;
    topic_name: string;
    difficulty: string;
    concept_tags: string[];
    is_bookmarked: boolean;
}

interface Subject {
    id: number;
    name: string;
    code: string;
    question_count: number;
}

export default function QuestionsPage() {
    return (
        <Suspense fallback={<div style={{ background: 'var(--bg-primary)' }} className="min-h-screen"><Sidebar /><div className="main-content"><div className="glass-card p-8 text-center animate-pulse gradient-text">Loading...</div></div></div>}>
            <QuestionsContent />
        </Suspense>
    );
}

function QuestionsContent() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [questions, setQuestions] = useState<Question[]>([]);
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedSubject, setSelectedSubject] = useState('');
    const [selectedDifficulty, setSelectedDifficulty] = useState('');
    const [selectedYear, setSelectedYear] = useState('');
    const [years, setYears] = useState<number[]>([]);
    const [selectedQuestion, setSelectedQuestion] = useState<number | null>(null);
    const [questionDetail, setQuestionDetail] = useState<any>(null);
    const [showAnswer, setShowAnswer] = useState(false);
    const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [totalCount, setTotalCount] = useState(0);
    const pageSize = 20;
    const [aiExplanation, setAiExplanation] = useState<any>(null);
    const [aiLoading, setAiLoading] = useState(false);
    const [tokenError, setTokenError] = useState(false);
    const [aiError, setAiError] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            Promise.all([
                questionsAPI.list({ page: 1, page_size: pageSize }),
                questionsAPI.getSubjects(),
                questionsAPI.getYears(),
            ]).then(([qRes, sRes, yRes]) => {
                const qData = qRes.data;
                setQuestions(qData.results || qData || []);
                setTotalCount(qData.count || (qData.results || qData || []).length);
                setSubjects(sRes.data.results || sRes.data || []);
                setYears(yRes.data.results || yRes.data || []);
            }).catch(() => { }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    // Handle bookmark click-through: /questions?q=123
    useEffect(() => {
        const qId = searchParams.get('q');
        if (qId && !loading && isAuthenticated) {
            openQuestion(Number(qId));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchParams, loading, isAuthenticated]);

    const fetchQuestions = (params: Record<string, string | number>) => {
        setLoading(true);
        questionsAPI.list(params).then(res => {
            const d = res.data;
            setQuestions(d.results || d || []);
            setTotalCount(d.count || (d.results || d || []).length);
        }).catch(() => { }).finally(() => setLoading(false));
    };

    useEffect(() => {
        if (!isAuthenticated) return;
        const params: Record<string, string | number> = { page: 1, page_size: pageSize };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        setPage(1);
        fetchQuestions(params);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedSubject, selectedDifficulty, selectedYear]);

    const handlePageChange = (newPage: number) => {
        setPage(newPage);
        const params: Record<string, string | number> = { page: newPage, page_size: pageSize };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        fetchQuestions(params);
    };

    const openQuestion = (id: number) => {
        setSelectedQuestion(id);
        setShowAnswer(false);
        setSelectedAnswer(null);
        setAiExplanation(null);
        setAiLoading(false);
        setTokenError(false);
        setAiError(null);
        Promise.all([
            questionsAPI.get(id),
            questionsAPI.getSimilar(id)
        ]).then(([qRes, sRes]) => {
            const detailData = qRes.data;
            detailData.similar = sRes.data;
            setQuestionDetail(detailData);
        }).catch(() => {
            questionsAPI.get(id).then(res => setQuestionDetail(res.data));
        });
    };

    const handleSelectOption = (opt: string) => {
        setSelectedAnswer(opt);
        setShowAnswer(true);
        // NOTE: AI explanation is NOT auto-triggered anymore.
        // Students must click "Generate AI Analysis" button to save API tokens.
    };

    /**
     * Fetches AI explanation for the currently viewed question.
     * Called only when user clicks the "Generate AI Analysis" button.
     */
    const fetchAiExplanation = () => {
        if (!questionDetail || aiLoading) return;
        const d = questionDetail as any;
        setAiLoading(true);
        setAiExplanation(null);
        setTokenError(false);
        setAiError(null);
        aiAPI.explainAfterAnswer({
            question_text: d.question_text,
            options: {
                A: d.option_a || d.option_A || '',
                B: d.option_b || d.option_B || '',
                C: d.option_c || d.option_C || '',
                D: d.option_d || d.option_D || '',
            },
            correct_answer: d.correct_answer || '',
            selected_answer: selectedAnswer || '',
            subject: d.subject_name || '',
            topic: d.topic_name || '',
        }).then(res => {
            setAiExplanation(res.data);
        }).catch((err) => {
            if (err?.response?.status === 429) {
                setTokenError(true);
            } else {
                setAiError(err?.response?.data?.error || 'AI service unavailable. Please try again.');
            }
            setAiExplanation(null);
        }).finally(() => {
            setAiLoading(false);
        });
    };

    const handleBookmark = (id: number, e: React.MouseEvent) => {
        e.stopPropagation();
        questionsAPI.bookmark(id).then(() => {
            setQuestions(prev => prev.map(q => q.id === id ? { ...q, is_bookmarked: !q.is_bookmarked } : q));
        });
    };

    const handleSearch = () => {
        const params: Record<string, string | number> = { page: 1, page_size: pageSize };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        setPage(1);
        fetchQuestions(params);
    };

    const diffBadge = (d: string) => {
        const cls = d === 'easy' ? 'badge-easy' : d === 'hard' ? 'badge-hard' : 'badge-medium';
        return <span className={`badge ${cls}`}>{d}</span>;
    };

    const detail = questionDetail as any;
    const totalPages = Math.ceil(totalCount / pageSize);

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-3">
                            <BookOpen className="w-7 h-7" style={{ color: 'var(--accent-primary)' }} />
                            CMS Question Bank
                        </h1>
                        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                            {totalCount} questions — Master the exam with targeted PYQ practice
                        </p>
                    </div>
                </div>

                {/* Filters */}
                <div className="glass-card p-4 mb-6">
                    <div className="flex flex-wrap gap-3 items-center">
                        <div className="relative flex-1 min-w-[200px]">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                            <input className="input-field pl-10" placeholder="Search questions..."
                                value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handleSearch()} />
                        </div>
                        <select className="input-field w-auto" value={selectedSubject} onChange={e => setSelectedSubject(e.target.value)}>
                            <option value="">All Subjects</option>
                            {subjects.map(s => <option key={s.id} value={s.id}>{s.name} ({s.question_count})</option>)}
                        </select>
                        <select className="input-field w-auto" value={selectedDifficulty} onChange={e => setSelectedDifficulty(e.target.value)}>
                            <option value="">All Difficulty</option>
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                        </select>
                        <select className="input-field w-auto" value={selectedYear} onChange={e => setSelectedYear(e.target.value)}>
                            <option value="">All Years</option>
                            {years.map(y => <option key={y} value={y}>{y}</option>)}
                        </select>
                        <button onClick={handleSearch} className="btn-primary">
                            <Filter className="w-4 h-4" /> Filter
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="grid lg:grid-cols-5 gap-6">
                    {/* Question List */}
                    <div className="lg:col-span-2 space-y-3">
                        {loading ? (
                            <div className="glass-card p-8 text-center">
                                <div className="animate-pulse gradient-text font-semibold">Loading Q-Bank...</div>
                            </div>
                        ) : questions.length === 0 ? (
                            <div className="glass-card p-8 text-center" style={{ color: 'var(--text-secondary)' }}>
                                No questions found. Try adjusting your filters.
                            </div>
                        ) : (
                            <>
                                {questions.map(q => (
                                    <div key={q.id} className={`glass-card p-4 cursor-pointer transition-all ${selectedQuestion === q.id ? 'ring-1' : ''}`}
                                        style={selectedQuestion === q.id ? { borderColor: 'var(--accent-primary)' } : {}}
                                        onClick={() => openQuestion(q.id)}>
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="text-xs font-bold px-2 py-1 rounded" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
                                                {q.year} &bull; {q.subject_name}
                                            </span>
                                            <div className="flex items-center gap-2">
                                                {diffBadge(q.difficulty)}
                                                <button onClick={(e) => handleBookmark(q.id, e)} className="hover:scale-110 transition-transform">
                                                    <Bookmark className="w-4 h-4" style={{ color: q.is_bookmarked ? '#f59e0b' : 'var(--text-secondary)', fill: q.is_bookmarked ? '#f59e0b' : 'none' }} />
                                                </button>
                                            </div>
                                        </div>
                                        <p className="text-sm leading-relaxed">{stripMarkdown(q.question_text).slice(0, 150)}{q.question_text.length > 150 ? '...' : ''}</p>
                                        {q.topic_name && (
                                            <div className="mt-2">
                                                <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: 'rgba(6,182,212,0.1)', color: 'var(--accent-primary)' }}>
                                                    {q.topic_name}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                ))}
                                {/* Pagination */}
                                {totalPages > 1 && (
                                    <div className="flex items-center justify-center gap-2 pt-4">
                                        <button onClick={() => handlePageChange(page - 1)} disabled={page <= 1}
                                            className="btn-secondary py-2 px-3 text-sm" style={{ opacity: page <= 1 ? 0.4 : 1 }}>
                                            <ChevronLeft className="w-4 h-4" />
                                        </button>
                                        <span className="text-sm px-3" style={{ color: 'var(--text-secondary)' }}>
                                            Page {page} of {totalPages}
                                        </span>
                                        <button onClick={() => handlePageChange(page + 1)} disabled={page >= totalPages}
                                            className="btn-secondary py-2 px-3 text-sm" style={{ opacity: page >= totalPages ? 0.4 : 1 }}>
                                            <ChevronRight className="w-4 h-4" />
                                        </button>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    {/* Question Detail */}
                    <div className="lg:col-span-3">
                        {selectedQuestion && detail ? (
                            <div className="sticky top-6 space-y-3 animate-fadeInUp" style={{ maxHeight: 'calc(100vh - 3rem)', overflowY: 'auto' }}>
                                {/* Question Card */}
                                <div className="glass-card overflow-hidden">
                                    {/* Header Tags */}
                                    <div className="px-5 py-3 flex flex-wrap items-center gap-2" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--glass-border)' }}>
                                        <span className="review-tag review-tag-cyan">PYQ {String(detail.year)}</span>
                                        <span className="review-tag review-tag-purple">{String(detail.subject_name)}</span>
                                        {detail.topic_name && <span className="review-tag" style={{ background: 'rgba(99,102,241,0.1)', color: '#6366f1', border: '1px solid rgba(99,102,241,0.2)' }}>{String(detail.topic_name)}</span>}
                                        {detail.difficulty && <span className={`review-tag ${detail.difficulty === 'hard' ? 'review-tag-red' : detail.difficulty === 'medium' ? 'review-tag-amber' : 'review-tag-green'}`}>{detail.difficulty}</span>}
                                    </div>

                                    {/* Question Text — rendered with markdown */}
                                    <div className="p-5">
                                        <div className="text-base font-medium leading-relaxed mb-5">
                                            <FormattedText text={String(detail.question_text)} />
                                        </div>

                                        {/* Options */}
                                        <div className="space-y-2.5 mb-4">
                                            {['A', 'B', 'C', 'D'].map(opt => {
                                                const key = `option_${opt.toLowerCase()}`;
                                                const optionText = detail[key] || detail[`option_${opt}`];
                                                if (!optionText) return null;
                                                const isCorrect = detail.correct_answer === opt;
                                                const isSelected = selectedAnswer === opt;
                                                const isWrong = isSelected && !isCorrect && showAnswer;

                                                return (
                                                    <div key={opt}
                                                        className={`review-option ${showAnswer && isCorrect ? 'review-option-correct' : ''} ${isWrong ? 'review-option-wrong' : ''} ${!showAnswer && isSelected ? 'review-option-selected' : ''} cursor-pointer`}
                                                        onClick={() => handleSelectOption(opt)}>
                                                        <div className={`review-option-dot ${showAnswer && isCorrect ? 'correct' : ''} ${isWrong ? 'wrong' : ''} ${!showAnswer && isSelected ? 'selected' : ''}`}>{opt}</div>
                                                        <div className="flex-1 text-sm font-medium">{cleanOptionText(String(optionText))}</div>
                                                        {showAnswer && isCorrect && <span className="review-option-label correct">✓ Correct</span>}
                                                        {isWrong && <span className="review-option-label wrong">✗ Wrong</span>}
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        {!showAnswer && !selectedAnswer && (
                                            <p className="text-xs text-center py-2" style={{ color: 'var(--text-secondary)' }}>👆 Select an option to reveal the answer & detailed analysis</p>
                                        )}
                                    </div>
                                </div>

                                {/* === ANSWER ANALYSIS === */}
                                {showAnswer && (
                                    <div className="space-y-3 animate-fadeInUp">
                                        {/* ✅ Correct Answer */}
                                        <div className="explanation-card explanation-card-green">
                                            <div className="explanation-card-accent green"></div>
                                            <div className="p-4 pl-5">
                                                <h4 className="explanation-card-title green"><CheckCircle className="w-4 h-4" /> Correct Answer: {detail.correct_answer}</h4>
                                                {detail.explanation && <p className="text-sm leading-relaxed mt-1.5" style={{ color: 'var(--text-secondary)', lineHeight: '1.7' }}>{String(detail.explanation)}</p>}
                                            </div>
                                        </div>

                                        {/* DB Mnemonic */}
                                        {detail.mnemonic && !aiExplanation?.mnemonic && (
                                            <div className="mnemonic-card">
                                                <div className="flex items-start gap-3">
                                                    <div className="mnemonic-icon">💡</div>
                                                    <div>
                                                        <h5 className="text-sm font-bold mb-1" style={{ color: '#f59e0b' }}>🧠 Memory Trick</h5>
                                                        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{String(detail.mnemonic)}</p>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                        {/* DB Textbook Reference */}
                                        {detail.book_name && !aiExplanation?.textbook_reference?.book && (
                                            <div className="glass-card p-4 flex items-start gap-3">
                                                <BookMarked className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#8b5cf6' }} />
                                                <div>
                                                    <h5 className="text-xs font-bold mb-0.5" style={{ color: '#8b5cf6' }}>📚 Textbook Reference</h5>
                                                    <p className="text-sm font-semibold">{String(detail.book_name)} {detail.chapter ? `— Ch: ${String(detail.chapter)}` : ''} {detail.page_number ? `(pg ${String(detail.page_number)})` : ''}</p>
                                                </div>
                                            </div>
                                        )}

                                        {/* Similar PYQs from DB */}
                                        {detail.similar && (detail.similar as unknown[]).length > 0 && (
                                            <div className="glass-card p-4">
                                                <h5 className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--accent-primary)' }}>
                                                    <Target className="w-3.5 h-3.5" /> Similar PYQs from Database
                                                </h5>
                                                <div className="space-y-1.5">
                                                    {(detail.similar as Array<{ id: number; year: number; question_text: string }>).map((sq) => (
                                                        <div key={sq.id} className="flex gap-2 items-start cursor-pointer p-2 rounded-lg transition-colors hover:bg-[rgba(6,182,212,0.05)]"
                                                            onClick={() => { openQuestion(sq.id); }}>
                                                            <span className="text-xs font-bold px-1.5 py-0.5 rounded whitespace-nowrap" style={{ background: 'rgba(6,182,212,0.1)', color: 'var(--accent-primary)' }}>PYQ {sq.year}</span>
                                                            <span className="text-xs line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{sq.question_text}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* AI Loading */}
                                        {aiLoading && (
                                            <div className="glass-card p-5 flex items-center gap-4 animate-pulse" style={{ borderColor: 'rgba(6,182,212,0.3)' }}>
                                                <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                                                <div>
                                                    <span className="text-sm font-bold" style={{ color: 'var(--accent-primary)' }}>🧠 AI is preparing your study material...</span>
                                                    <span className="text-xs block mt-1" style={{ color: 'var(--text-secondary)' }}>Generating mnemonics, topic knowledge, exam tips & more</span>
                                                </div>
                                            </div>
                                        )}

                                        {/* Generate AI Analysis button — only shown after answer, before AI loads */}
                                        {showAnswer && !aiExplanation && !aiLoading && !tokenError && (
                                            <button onClick={fetchAiExplanation}
                                                className="w-full glass-card p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:scale-[1.01] group mt-3"
                                                style={{ background: 'rgba(6,182,212,0.04)' }}>
                                                <Brain className="w-6 h-6 group-hover:animate-pulse" style={{ color: 'var(--accent-primary)' }} />
                                                <div className="text-left">
                                                    <span className="text-sm font-bold block" style={{ color: 'var(--accent-primary)' }}>Generate AI Analysis</span>
                                                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Click to get mnemonics, explanations, exam tips & more</span>
                                                </div>
                                            </button>
                                        )}

                                        {/* Token depleted error */}
                                        {tokenError && (
                                            <div className="token-depleted-banner mt-3">
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

                                        {/* AI Error */}
                                        {aiError && !tokenError && (
                                            <div className="glass-card p-4 mt-3" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
                                                <div className="flex items-start gap-3">
                                                    <Brain className="w-5 h-5 mt-0.5 shrink-0" style={{ color: '#f59e0b' }} />
                                                    <div>
                                                        <h5 className="text-sm font-bold" style={{ color: '#f59e0b' }}>AI Temporarily Unavailable</h5>
                                                        <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{aiError}</p>
                                                        <button onClick={fetchAiExplanation} className="text-xs mt-2 font-bold" style={{ color: 'var(--accent-primary)' }}>
                                                            Retry
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                        {/* ═══ AI DEEP ANALYSIS ═══ */}
                                        {aiExplanation && !aiLoading && (
                                            <div className="space-y-3">
                                                {/* Section Header */}
                                                <div className="flex items-center gap-2 px-1 pt-1">
                                                    <Brain className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                                    <span className="font-bold text-sm gradient-text tracking-wide">AI-POWERED DEEP ANALYSIS</span>
                                                    <div className="flex-1 h-px" style={{ background: 'linear-gradient(to right, var(--glass-border), transparent)' }}></div>
                                                </div>

                                                {/* 🧠 Mnemonic — ALWAYS FIRST */}
                                                {aiExplanation.mnemonic && (
                                                    <div className="mnemonic-card">
                                                        <div className="flex items-start gap-3">
                                                            <div className="mnemonic-icon">💡</div>
                                                            <div className="flex-1">
                                                                <h5 className="text-sm font-bold mb-1.5" style={{ color: '#f59e0b' }}>🧠 Memory Trick — Never Forget This!</h5>
                                                                <p className="text-sm font-medium leading-relaxed" style={{ color: 'var(--text-primary)' }}>{aiExplanation.mnemonic}</p>
                                                            </div>
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Core Concept + Why Correct + Why Wrong */}
                                                <div className="glass-card overflow-hidden">
                                                    {aiExplanation.core_concept && (
                                                        <div className="px-4 py-2.5 flex items-center gap-2" style={{ background: 'rgba(6,182,212,0.05)', borderBottom: '1px solid var(--glass-border)' }}>
                                                            <Target className="w-3.5 h-3.5" style={{ color: 'var(--accent-primary)' }} />
                                                            <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--accent-primary)' }}>Core Concept</span>
                                                            <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{aiExplanation.core_concept}</span>
                                                        </div>
                                                    )}
                                                    {aiExplanation.why_correct && (
                                                        <div className="p-4">
                                                            <h5 className="text-xs font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1.5" style={{ color: '#10b981' }}>
                                                                <CheckCircle className="w-3.5 h-3.5" /> Why {detail.correct_answer} is Correct
                                                            </h5>
                                                            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)', lineHeight: '1.7' }}>{cleanAiText(aiExplanation.why_correct)}</p>
                                                        </div>
                                                    )}
                                                    {aiExplanation.why_wrong && Object.keys(aiExplanation.why_wrong).length > 0 && (
                                                        <div className="px-4 pb-4 space-y-1.5">
                                                            <h5 className="text-xs font-bold uppercase tracking-wider mb-1.5" style={{ color: '#ef4444' }}>❌ Why Other Options Are Wrong</h5>
                                                            {Object.entries(aiExplanation.why_wrong).map(([key, val]) => (
                                                                <div key={key} className="flex gap-2 text-xs p-2 rounded-lg" style={{ background: 'rgba(239,68,68,0.04)' }}>
                                                                    <span className="font-bold shrink-0 w-5 h-5 rounded-full flex items-center justify-center" style={{ background: 'rgba(239,68,68,0.12)', color: '#ef4444', fontSize: '10px' }}>{key}</span>
                                                                    <span style={{ color: 'var(--text-secondary)' }}>{String(val)}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>

                                                {/* 📖 Topic Deep Dive */}
                                                {aiExplanation.topic_deep_dive && (
                                                    <div className="explanation-card explanation-card-indigo">
                                                        <div className="explanation-card-accent indigo"></div>
                                                        <div className="p-4 pl-5">
                                                            <h4 className="explanation-card-title indigo"><BookOpen className="w-4 h-4" /> 📖 Topic Deep Dive — Learn the Bigger Picture</h4>
                                                            <p className="text-sm leading-relaxed mt-2" style={{ color: 'var(--text-secondary)', lineHeight: '1.75' }}>{aiExplanation.topic_deep_dive}</p>
                                                        </div>
                                                    </div>
                                                )}

                                                {/* ⚡ High Yield + ⚖️ Key Differentiators */}
                                                {(aiExplanation.high_yield_points?.length > 0 || aiExplanation.key_differentiators?.length > 0) && (
                                                    <div className="grid grid-cols-1 gap-3">
                                                        {aiExplanation.high_yield_points?.length > 0 && (
                                                            <div className="glass-card p-4">
                                                                <h5 className="text-xs font-bold uppercase tracking-wider mb-2.5 flex items-center gap-1.5" style={{ color: '#ec4899' }}>
                                                                    <Zap className="w-3.5 h-3.5" /> ⚡ High Yield Points
                                                                </h5>
                                                                <ul className="space-y-2">
                                                                    {aiExplanation.high_yield_points.map((point: string, i: number) => (
                                                                        <li key={i} className="text-xs flex gap-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                                                            <span className="mt-0.5 shrink-0" style={{ color: '#ec4899' }}>▸</span>
                                                                            <span>{point}</span>
                                                                        </li>
                                                                    ))}
                                                                </ul>
                                                            </div>
                                                        )}
                                                        {aiExplanation.key_differentiators?.length > 0 && (
                                                            <div className="glass-card p-4">
                                                                <h5 className="text-xs font-bold uppercase tracking-wider mb-2.5 flex items-center gap-1.5" style={{ color: '#f59e0b' }}>
                                                                    <ArrowRight className="w-3.5 h-3.5" /> ⚖️ Key Differentiators
                                                                </h5>
                                                                <ul className="space-y-2">
                                                                    {aiExplanation.key_differentiators.map((d: string, i: number) => (
                                                                        <li key={i} className="text-xs leading-relaxed px-3 py-2 rounded-lg" style={{ background: 'rgba(245,158,11,0.05)', color: 'var(--text-secondary)', borderLeft: '2px solid rgba(245,158,11,0.3)' }}>
                                                                            {d}
                                                                        </li>
                                                                    ))}
                                                                </ul>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                {/* 📚 Reference + 💎 Pearl + 🎓 Exam Tip */}
                                                <div className="grid grid-cols-1 gap-3">
                                                    {aiExplanation.textbook_reference?.book && (
                                                        <div className="glass-card p-4 flex items-start gap-2.5">
                                                            <BookMarked className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#8b5cf6' }} />
                                                            <div>
                                                                <h6 className="text-xs font-bold mb-0.5" style={{ color: '#8b5cf6' }}>📚 Textbook Reference</h6>
                                                                <p className="text-xs font-semibold">{aiExplanation.textbook_reference.book}</p>
                                                                {aiExplanation.textbook_reference.chapter && <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>Ch: {aiExplanation.textbook_reference.chapter}</p>}
                                                                {aiExplanation.textbook_reference.page && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Pg: {aiExplanation.textbook_reference.page}</p>}
                                                            </div>
                                                        </div>
                                                    )}
                                                    <div className="grid grid-cols-2 gap-3">
                                                        {aiExplanation.clinical_pearl && (
                                                            <div className="glass-card p-3 flex items-start gap-2">
                                                                <Sparkles className="w-3.5 h-3.5 mt-0.5 shrink-0" style={{ color: '#10b981' }} />
                                                                <div>
                                                                    <h6 className="text-xs font-bold mb-0.5" style={{ color: '#10b981' }}>💎 Clinical Pearl</h6>
                                                                    <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{aiExplanation.clinical_pearl}</p>
                                                                </div>
                                                            </div>
                                                        )}
                                                        {aiExplanation.exam_tip && (
                                                            <div className="glass-card p-3 flex items-start gap-2">
                                                                <GraduationCap className="w-3.5 h-3.5 mt-0.5 shrink-0" style={{ color: '#f59e0b' }} />
                                                                <div>
                                                                    <h6 className="text-xs font-bold mb-0.5" style={{ color: '#f59e0b' }}>🎓 Exam Strategy</h6>
                                                                    <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{aiExplanation.exam_tip}</p>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* 📝 Quick Revision */}
                                                {aiExplanation.quick_revision && (
                                                    <div className="quick-revision-card">
                                                        <div className="absolute top-0 left-0 w-full h-1" style={{ background: 'var(--gradient-primary)' }}></div>
                                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1.5" style={{ color: 'var(--accent-primary)' }}>
                                                            <Lightbulb className="w-3.5 h-3.5" /> 📝 Quick Revision — Read Before Exam
                                                        </h5>
                                                        <p className="text-sm leading-relaxed font-medium" style={{ color: 'var(--text-primary)', lineHeight: '1.7' }}>{aiExplanation.quick_revision}</p>
                                                    </div>
                                                )}

                                                {/* 🔗 Related Concepts */}
                                                {aiExplanation.around_concepts?.length > 0 && (
                                                    <div className="glass-card p-4">
                                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#6366f1' }}>🔗 Related Concepts (Often Asked Together)</h5>
                                                        <div className="flex flex-wrap gap-1.5">
                                                            {aiExplanation.around_concepts.map((concept: string, i: number) => (
                                                                <span key={i} className="text-xs px-2.5 py-1 rounded-full font-medium" style={{ background: 'rgba(99,102,241,0.08)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.15)' }}>{concept}</span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* 📊 PYQ Intelligence */}
                                                {(aiExplanation.pyq_frequency || aiExplanation.similar_pyq) && (
                                                    <div className="glass-card p-4">
                                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: '#ec4899' }}>
                                                            <Target className="w-3.5 h-3.5" /> 📊 PYQ Intelligence
                                                        </h5>
                                                        {aiExplanation.pyq_frequency && <p className="text-sm mb-1.5" style={{ color: 'var(--text-secondary)' }}>📈 <strong style={{ color: '#ec4899' }}>Frequency:</strong> {aiExplanation.pyq_frequency}</p>}
                                                        {aiExplanation.similar_pyq && <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>📋 <strong style={{ color: '#818cf8' }}>Similar Questions:</strong> {aiExplanation.similar_pyq}</p>}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="glass-card p-16 text-center h-[500px] flex flex-col items-center justify-center">
                                <BookOpen className="w-16 h-16 mx-auto mb-6" style={{ color: 'var(--text-secondary)', opacity: 0.3 }} />
                                <p className="text-lg font-medium mb-2">Select a Question</p>
                                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Click any question from the bank to practice and review detailed AI-powered explanations.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
