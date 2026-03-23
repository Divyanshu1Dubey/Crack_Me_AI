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
import { Suspense, useEffect, useState, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { questionsAPI, aiAPI } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { BookOpen, Search, Filter, Bookmark, Eye, ChevronLeft, ChevronRight, Loader2, Brain, Sparkles, Target, BookMarked, Lightbulb, CheckCircle, Zap, GraduationCap, ArrowRight, Flag } from 'lucide-react';
import Header from '@/components/Header';
import DiscussionThread from '@/components/DiscussionThread';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

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
        <Suspense fallback={<div className="min-h-screen bg-background"><Sidebar /><div className="main-content"><Header /><div className="page-container"><Skeleton className="h-8 w-48 mb-4" /><Skeleton className="h-16 w-full mb-6" /><div className="grid lg:grid-cols-5 gap-6"><div className="lg:col-span-2 space-y-3">{[...Array(5)].map((_,i)=><Skeleton key={i} className="h-24" />)}</div><Skeleton className="lg:col-span-3 h-96" /></div></div></div></div>}>
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
    const [flagOpen, setFlagOpen] = useState(false);
    const [flagCategory, setFlagCategory] = useState('wrong_answer');
    const [flagComment, setFlagComment] = useState('');
    const [flagSubmitting, setFlagSubmitting] = useState(false);
    const [flagSuccess, setFlagSuccess] = useState(false);

    // Rotating loading messages for AI analysis
    const loadingMessages = useRef([
        '🧠 AI is crafting your personalised study notes...',
        '📚 Scanning Harrison, Bailey & Love, Schwartz...',
        '💡 Building memory tricks for instant recall...',
        '🎯 Identifying high-yield exam patterns...',
        '⚡ Connecting this to frequently tested topics...',
        '🔬 Analyzing why each option is right or wrong...',
        '📖 Finding the perfect textbook reference...',
        '🏥 Preparing clinical pearls for ward rounds...',
        '🎓 Crafting exam strategy tips just for you...',
        '🧬 Mapping related concepts for deep understanding...',
    ]);
    const [loadingMsgIndex, setLoadingMsgIndex] = useState(0);

    // ── Keyboard Navigation: A/B/C/D to answer, N/P for next/prev ──
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            // Skip if user is typing in an input/textarea
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

            const key = e.key.toLowerCase();

            // A/B/C/D to select answer option (only when viewing a question, before answer is revealed)
            if (['a', 'b', 'c', 'd'].includes(key) && questionDetail && !showAnswer) {
                e.preventDefault();
                handleSelectOption(key.toUpperCase());
            }

            // N = next question in list
            if (key === 'n' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                const currentIdx = questions.findIndex(q => q.id === selectedQuestion);
                if (currentIdx < questions.length - 1) {
                    openQuestion(questions[currentIdx + 1].id);
                } else if (page < Math.ceil(totalCount / pageSize)) {
                    // Load next page
                    handlePageChange(page + 1);
                }
            }

            // P = previous question in list
            if (key === 'p' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                const currentIdx = questions.findIndex(q => q.id === selectedQuestion);
                if (currentIdx > 0) {
                    openQuestion(questions[currentIdx - 1].id);
                } else if (page > 1) {
                    handlePageChange(page - 1);
                }
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [questionDetail, showAnswer, questions, selectedQuestion, page, totalCount]);

    useEffect(() => {
        if (!aiLoading) return;
        setLoadingMsgIndex(0);
        const interval = setInterval(() => {
            setLoadingMsgIndex(prev => (prev + 1) % loadingMessages.current.length);
        }, 3000);
        return () => clearInterval(interval);
    }, [aiLoading]);

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
    const fetchAiExplanation = (retryCount: number = 0) => {
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
            setAiLoading(false);
        }).catch((err) => {
            if (err?.response?.status === 429) {
                setTokenError(true);
                setAiLoading(false);
            } else if (retryCount < 1 && !err?.response?.status) {
                // Network/timeout error — auto-retry once
                setTimeout(() => fetchAiExplanation(retryCount + 1), 2000);
            } else {
                setAiError(err?.response?.data?.error || 'AI service unavailable. Please try again.');
                setAiExplanation(null);
                setAiLoading(false);
            }
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

    const handleFlagSubmit = () => {
        if (!detail || !flagComment.trim()) return;
        setFlagSubmitting(true);
        questionsAPI.submitFeedback({
            question: detail.id,
            category: flagCategory,
            comment: flagComment.trim(),
        }).then(() => {
            setFlagSuccess(true);
            setTimeout(() => { setFlagOpen(false); setFlagSuccess(false); setFlagComment(''); }, 2000);
        }).catch(() => {})
        .finally(() => setFlagSubmitting(false));
    };

    const diffBadge = (d: string) => {
        const cls = d === 'easy' ? 'badge-easy' : d === 'hard' ? 'badge-hard' : 'badge-medium';
        return <span className={`badge ${cls}`}>{d}</span>;
    };

    const detail = questionDetail as any;
    const totalPages = Math.ceil(totalCount / pageSize);

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-3 text-foreground">
                            <BookOpen className="w-6 h-6 text-primary" />
                            CMS Question Bank
                        </h1>
                        <p className="text-sm mt-1 text-muted-foreground">
                            1,920 PYQs + AI-curated important questions — Master the exam with targeted practice
                        </p>
                    </div>
                </div>

                {/* Filters */}
                <Card className="mb-6">
                    <CardContent className="p-4">
                    <div className="flex flex-wrap gap-3 items-center">
                        <div className="relative flex-1 min-w-[200px]">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input className="pl-10" placeholder="Search questions..."
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
                        <Button onClick={handleSearch} size="sm">
                            <Filter className="w-4 h-4" /> Filter
                        </Button>
                    </div>
                    </CardContent>
                </Card>

                {/* Content */}
                <div className="grid lg:grid-cols-5 gap-6" style={{ height: 'calc(100vh - 220px)' }}>
                    {/* Question List */}
                    <div className="lg:col-span-2 overflow-y-auto overscroll-contain pr-1" style={{ scrollbarWidth: 'thin' }}>
                        <div className="space-y-3">
                        {loading ? (
                            <div className="space-y-3">
                                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
                            </div>
                        ) : questions.length === 0 ? (
                            <Card className="p-8 text-center text-muted-foreground">
                                No questions found. Try adjusting your filters.
                            </Card>
                        ) : (
                            <>
                                {questions.map(q => (
                                    <Card key={q.id} className={`p-4 cursor-pointer transition-all hover:shadow-md ${selectedQuestion === q.id ? 'ring-2 ring-primary border-primary' : ''}`}
                                        onClick={() => openQuestion(q.id)}>
                                        <div className="flex justify-between items-start mb-2">
                                            <Badge variant="secondary" className="text-xs">
                                                {q.year} &bull; {q.subject_name}
                                            </Badge>
                                            <div className="flex items-center gap-2">
                                                {diffBadge(q.difficulty)}
                                                <button onClick={(e) => handleBookmark(q.id, e)} className="hover:scale-110 transition-transform">
                                                    <Bookmark className={`w-4 h-4 ${q.is_bookmarked ? 'text-amber-500 fill-amber-500' : 'text-muted-foreground'}`} />
                                                </button>
                                            </div>
                                        </div>
                                        <p className="text-sm leading-relaxed text-foreground">{stripMarkdown(q.question_text).slice(0, 150)}{q.question_text.length > 150 ? '...' : ''}</p>
                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                            {q.topic_name && <Badge variant="outline" className="text-xs">{q.topic_name}</Badge>}
                                            {q.year && <Badge variant="outline" className="text-[10px]">PYQ {q.year}</Badge>}
                                            {q.concept_tags?.includes('high_yield') && (
                                                <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-[10px]">🔥 High Yield</Badge>
                                            )}
                                        </div>
                                    </Card>
                                ))}
                                {/* Pagination */}
                                {totalPages > 1 && (
                                    <div className="flex items-center justify-center gap-2 pt-4">
                                        <Button variant="outline" size="sm" onClick={() => handlePageChange(page - 1)} disabled={page <= 1}>
                                            <ChevronLeft className="w-4 h-4" />
                                        </Button>
                                        <span className="text-sm px-3 text-muted-foreground">
                                            Page {page} of {totalPages}
                                        </span>
                                        <Button variant="outline" size="sm" onClick={() => handlePageChange(page + 1)} disabled={page >= totalPages}>
                                            <ChevronRight className="w-4 h-4" />
                                        </Button>
                                    </div>
                                )}
                            </>
                        )}
                        </div>
                    </div>

                    {/* Question Detail */}
                    <div className="lg:col-span-3 overflow-y-auto overscroll-contain" style={{ scrollbarWidth: 'thin' }}>
                        {selectedQuestion && detail ? (
                            <div className="space-y-3 animate-fadeInUp">
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

                                        {/* 🚩 Flag Wrong Answer */}
                                        <div className="flex justify-end">
                                            <button onClick={() => { setFlagOpen(!flagOpen); setFlagSuccess(false); }}
                                                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                                                <Flag className="w-3.5 h-3.5" /> Flag Issue
                                            </button>
                                        </div>
                                        {flagOpen && (
                                            <div className="glass-card p-4 space-y-3 animate-fadeInUp">
                                                <h5 className="text-sm font-bold flex items-center gap-2" style={{ color: '#ef4444' }}>
                                                    <Flag className="w-4 h-4" /> Report an Issue
                                                </h5>
                                                {flagSuccess ? (
                                                    <p className="text-sm text-emerald-500 font-medium">✓ Thanks! Your feedback has been submitted. You&apos;ll earn 2 tokens if accepted.</p>
                                                ) : (
                                                    <>
                                                        <select className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                                                            value={flagCategory} onChange={e => setFlagCategory(e.target.value)}>
                                                            <option value="wrong_answer">Wrong Answer</option>
                                                            <option value="discrepancy">Discrepancy in Options</option>
                                                            <option value="out_of_syllabus">Out of Syllabus</option>
                                                            <option value="typo">Typo/Formatting Issue</option>
                                                            <option value="explanation_needed">Better Explanation Needed</option>
                                                            <option value="other">Other</option>
                                                        </select>
                                                        <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-[60px] resize-none"
                                                            placeholder="Describe the issue (e.g., correct answer should be B because...)"
                                                            value={flagComment} onChange={e => setFlagComment(e.target.value)} />
                                                        <div className="flex gap-2">
                                                            <Button size="sm" onClick={handleFlagSubmit} disabled={flagSubmitting || !flagComment.trim()}>
                                                                {flagSubmitting ? 'Submitting...' : 'Submit'}
                                                            </Button>
                                                            <Button size="sm" variant="ghost" onClick={() => setFlagOpen(false)}>Cancel</Button>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        )}

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
                                                    <span className="text-sm font-bold transition-all duration-500" style={{ color: 'var(--accent-primary)' }}>{loadingMessages.current[loadingMsgIndex]}</span>
                                                    <span className="text-xs block mt-1" style={{ color: 'var(--text-secondary)' }}>Generating mnemonics, topic knowledge, exam tips & more</span>
                                                </div>
                                            </div>
                                        )}

                                        {/* Generate AI Analysis button — only shown after answer, before AI loads */}
                                        {showAnswer && !aiExplanation && !aiLoading && !tokenError && (
                                            <button onClick={() => fetchAiExplanation()}
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
                                                        <button onClick={() => fetchAiExplanation()} className="text-xs mt-2 font-bold" style={{ color: 'var(--accent-primary)' }}>
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

                                {/* 💬 Discussion Thread */}
                                <DiscussionThread questionId={detail.id} />

                                {/* ⌨️ Keyboard Shortcuts Hint */}
                                <div className="flex flex-wrap items-center gap-3 px-2 py-2 text-[10px] text-muted-foreground">
                                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">A-D</kbd> answer</span>
                                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">N</kbd> next</span>
                                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">P</kbd> prev</span>
                                </div>
                            </div>
                        ) : (
                            <Card className="p-16 text-center h-[500px] flex flex-col items-center justify-center">
                                <BookOpen className="w-16 h-16 mx-auto mb-6 text-muted-foreground/30" />
                                <p className="text-lg font-medium mb-2 text-foreground">Select a Question</p>
                                <p className="text-sm text-muted-foreground">Click any question from the bank to practice and review detailed AI-powered explanations.</p>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
            </div>
        </div>
    );
}
