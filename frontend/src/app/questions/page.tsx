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
import { questionsAPI, aiAPI, testsAPI, extractApiErrorMessage } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { BookOpen, Search, Filter, Bookmark, ChevronLeft, ChevronRight, ChevronDown, Loader2, Brain, Sparkles, CheckCircle, ArrowRight, Flag, Target, Zap, GraduationCap, Lightbulb, Play, Calendar, ListChecks } from 'lucide-react';
import Header from '@/components/Header';
import DiscussionThread from '@/components/DiscussionThread';
import EngagingLoader from '@/components/EngagingLoader';
import { ExamTrackProvider, useExamTrack } from '@/components/ExamTrackProvider';
import { useDock } from '@/context/DockContext';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { PremiumVideoPlayer } from '@/components/ui/PremiumVideoPlayer';
import { FormattedText, stripMarkdown } from '@/components/FormattedText';
import { cleanOptionText, decodeMojiB } from '@/lib/textCleanup';

/** Map frontend URL slugs → DB enums + human labels.
 *  The Question model has TWO independent fields:
 *    - `exam_type`  : CharField enum ('cms' | 'neet_pg' | 'usmle' | 'fmge')
 *    - `exam_source`: CharField free text ('UPSC CMS' | 'NEET PG' | ...)
 *  Frontend state holds the URL slug (e.g. 'neet-pg'). Two helpers convert:
 *    - `slugToExamType(slug)` → enum string sent to /questions/ (filterset_field)
 *    - `slugToExamSource(slug)` → label sent to /questions/stats/
 *  Without these, `exam_type=neet-pg` is ignored (mixed exams) and
 *  `exam_source=neet-pg` matches zero rows (0 years shown).
 */
const SLUG_TO_EXAM_TYPE: Record<string, string> = {
    'cms': 'cms',
    'neet-pg': 'neet_pg',
    'neet_pg': 'neet_pg',
    'ini-cet': 'cms',         // INI-CET falls back to cms enum (no row in DB yet)
    'inicet': 'cms',
    'fmge': 'fmge',
    'usmle': 'usmle',
    'medical-officer': 'cms', // same fallback
};
const SLUG_TO_EXAM_SOURCE: Record<string, string> = {
    'cms': 'UPSC CMS',
    'neet-pg': 'NEET PG',
    'neet_pg': 'NEET PG',
    'ini-cet': 'INI-CET',
    'inicet': 'INI-CET',
    'fmge': 'FMGE',
    'usmle': 'USMLE',
    'medical-officer': 'Medical Officer',
};
function slugToExamType(slug: string): string | undefined {
    return SLUG_TO_EXAM_TYPE[slug];
}
function slugToExamSource(slug: string): string | undefined {
    return SLUG_TO_EXAM_SOURCE[slug];
}

/** Small color-swatch chip used inside the exam-mode palette legend. */
function LegendChip({ color, label }: { color: string; label: string }) {
    return (
        <span className="inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
            <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />
            {label}
        </span>
    );
}

/** Cleans AI response text — strips JSON/code fence artifacts that appear
 * when AI parsing fails, normalizes stray markdown heading markers, and
 * collapses newlines so the FormattedText renderer can format the rest.
 */
function cleanAiText(text: string): string {
    if (!text) return text;
    let t = text.trim();

    // Decode double-encoded UTF-8 mojibake (ΓÇÿ → ', etc.) so model output
    // that came back as Latin-1-of-UTF-8 renders correctly.
    t = decodeMojiB(t);

    // Strip code fences: ```json ... ```
    if (t.startsWith('```')) t = t.replace(/^```\w*\n?/, '');
    if (t.endsWith('```')) t = t.slice(0, -3);
    t = t.trim();

    // Strip a stray leading "json" keyword the model sometimes prepends.
    if (t.toLowerCase().startsWith('json')) t = t.slice(4).trim();

    // If it looks like a JSON object, try to extract the why_correct field
    // (AI sometimes returns the full JSON instead of just the string).
    if (t.startsWith('{')) {
        try {
            const parsed = JSON.parse(t);
            if (typeof parsed === 'object' && parsed) {
                if (parsed.why_correct) return cleanAiText(parsed.why_correct);
                if (parsed.explanation) return cleanAiText(parsed.explanation);
            }
        } catch { /* not valid JSON, continue */ }
    }

    // Replace ATX heading markers (#, ##, ###) with bold so they render as
    // emphasis instead of as literal "#" characters in the UI.
    // "### Why this is correct" → "**Why this is correct**"
    t = t.replace(/^\s{0,3}#{1,6}\s+(.+)$/gm, '**$1**');
    // Collapse 3+ blank lines down to one.
    t = t.replace(/\n{3,}/g, '\n\n');

    return t.trim();
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
    user_selected_answer?: string;
    user_is_correct?: boolean;
    video_url?: string;
    video_status?: string;
    video_thumbnail?: string;
    video_subtitles_url?: string;
    video_duration?: number;
}

interface Subject {
    id: number;
    name: string;
    code: string;
    question_count: number;
}

export default function QuestionsPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-background">
                    <Sidebar />
                    <div className="main-content">
                        <Header />
                        <EngagingLoader
                            title="Preparing Your Question Bank"
                            subtitle="Loading PYQs, filters, and topic mapping for a smoother attempt flow"
                            tips={[
                                'Use subject + year filters to simulate exam-weighted practice blocks.',
                                'Attempt first, then open AI analysis to strengthen retention and reasoning.',
                                'Bookmark difficult concepts and revise them in spaced cycles.',
                            ]}
                        />
                    </div>
                </div>
            }
        >
            <QuestionsContent />
        </Suspense>
    );
}

function QuestionsContent() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const { activeTrack } = useExamTrack();
    const { setContextQuestionId } = useDock();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [selectedExam, setSelectedExam] = useState<string>('cms');
    const [questions, setQuestions] = useState<Question[]>([]);
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedSubject, setSelectedSubject] = useState('');
    const [selectedDifficulty, setSelectedDifficulty] = useState('');
    const [selectedYear, setSelectedYear] = useState('');
    const [years, setYears] = useState<number[]>([]);
    const [qbankStats, setQbankStats] = useState<any>(null);
    const [listError, setListError] = useState<string | null>(null);
    const [selectedQuestion, setSelectedQuestion] = useState<number | null>(null);
    const [questionDetail, setQuestionDetail] = useState<any>(null);
    const [showAnswer, setShowAnswer] = useState(false);
    const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
    const [studyMode, setStudyMode] = useState<'practice' | 'exam'>('practice');
    // Exam-mode state — tracks which questions the user answered in the
    // current session, used by the right-rail palette.
    const [examAnswers, setExamAnswers] = useState<Record<number, { selected: string; isCorrect: boolean; answeredAt: number }>>({});
    const [examPaletteOpen, setExamPaletteOpen] = useState(true);
    // Reset exam state when toggling modes or changing filters.
    useEffect(() => {
        setExamAnswers({});
    }, [studyMode, selectedSubject, selectedDifficulty, selectedYear, selectedExam, searchQuery]);
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
    const [flagError, setFlagError] = useState<string | null>(null);
    const [showAiDeepDive, setShowAiDeepDive] = useState(false);

    useEffect(() => {
        setContextQuestionId(selectedQuestion);
    }, [selectedQuestion, setContextQuestionId]);

    // Year selection modal states
    const [yearModalOpen, setYearModalOpen] = useState(false);
    const [modalYear, setModalYear] = useState<string | null>(null);
    const [startingSimulation, setStartingSimulation] = useState(false);
    const [simulationError, setSimulationError] = useState<string | null>(null);
    const [showStatsDetail, setShowStatsDetail] = useState(false);

    // Exam-mode full-year question index. When the user enters exam mode
    // for a specific year, we fetch ALL questions for that year (paginated
    // until exhausted) so the right-rail palette can render every question
    // number — like a real UPSC CMS test HUD (240 buttons for 240 questions).
    const [examQuestions, setExamQuestions] = useState<Question[]>([]);
    const [examQuestionsLoading, setExamQuestionsLoading] = useState(false);

    // Textbook reference states
    const [textbookRef, setTextbookRef] = useState<any>(null);
    const [textbookLoading, setTextbookLoading] = useState(false);
    const [textbookScreenshot, setTextbookScreenshot] = useState<string | null>(null);

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
            setListError(null);
            const initialExamType = slugToExamType(selectedExam) || selectedExam;
            const initialExamSource = slugToExamSource(selectedExam) || selectedExam;
            Promise.all([
                questionsAPI.list({ page: 1, page_size: pageSize, exam_type: initialExamType }),
                questionsAPI.getSubjects(),
                questionsAPI.getYears(),
                questionsAPI.getStats({ exam_source: initialExamSource }),
            ]).then(([qRes, sRes, yRes, statsRes]) => {
                const qData = qRes.data;
                setQuestions(qData.results || qData || []);
                setTotalCount(qData.count || (qData.results || qData || []).length);
                setSubjects(sRes.data.results || sRes.data || []);
                setYears(yRes.data.results || yRes.data || []);
                setQbankStats(statsRes.data);
            }).catch((err: unknown) => {
                const apiError = err as { response?: { data?: unknown } };
                if (apiError.response?.data) {
                    setListError(extractApiErrorMessage(apiError.response.data, 'Unable to load questions right now.'));
                    return;
                }
                setListError('Unable to load questions right now. Please refresh and try again.');
            }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router, selectedExam]);

    // Handle bookmark click-through: /questions?q=123
    useEffect(() => {
        const qId = searchParams.get('q');
        if (qId && !loading && isAuthenticated) {
            openQuestion(Number(qId));
        }
    }, [searchParams, loading, isAuthenticated]);

    const fetchQuestions = (params: Record<string, string | number>) => {
        setLoading(true);
        setListError(null);
        questionsAPI.list(params).then(res => {
            const d = res.data;
            setQuestions(d.results || d || []);
            setTotalCount(d.count || (d.results || d || []).length);
        }).catch((err: unknown) => {
            const apiError = err as { response?: { data?: unknown } };
            if (apiError.response?.data) {
                setListError(extractApiErrorMessage(apiError.response.data, 'Unable to load questions right now.'));
                return;
            }
            setListError('Unable to load questions right now. Please refresh and try again.');
        }).finally(() => setLoading(false));
    };

    useEffect(() => {
        if (!isAuthenticated) return;
        const params: Record<string, string | number> = { page: 1, page_size: pageSize };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        const examType = slugToExamType(selectedExam);
        if (examType) params.exam_type = examType;
        setPage(1);
        fetchQuestions(params);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedSubject, selectedDifficulty, selectedYear, selectedExam]);

    const handlePageChange = (newPage: number) => {
        setPage(newPage);
        const params: Record<string, string | number> = { page: newPage, page_size: pageSize };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        const examType = slugToExamType(selectedExam);
        if (examType) params.exam_type = examType;
        fetchQuestions(params);
    };

    // Exam-mode: load ALL questions for the selected year (or current filter
    // set) so the right-rail palette can show every question number like a
    // real test HUD — not just the 20 currently visible on the list page.
    // Paginated until exhausted; capped at 600 to avoid runaway fetches.
    useEffect(() => {
        if (studyMode !== 'exam') {
            setExamQuestions([]);
            return;
        }
        if (!isAuthenticated) return;

        const params: Record<string, string | number> = { page: 1, page_size: 100 };
        if (selectedYear) params.year = selectedYear;
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (searchQuery) params.search = searchQuery;
        const examType = slugToExamType(selectedExam);
        if (examType) params.exam_type = examType;

        setExamQuestionsLoading(true);
        const collected: Question[] = [];
        const HARD_CAP = 600;
        const MAX_PAGES = 30;

        const fetchPage = (pageNum: number): Promise<void> => {
            return questionsAPI.list({ ...params, page: pageNum })
                .then(res => {
                    const d = res.data;
                    const items: Question[] = (d.results || d || []);
                    collected.push(...items);
                    const total = d.count || items.length;
                    const reachedEnd = items.length < 100 || collected.length >= total || collected.length >= HARD_CAP;
                    if (reachedEnd || pageNum >= MAX_PAGES) {
                        setExamQuestions(collected);
                        setExamQuestionsLoading(false);
                        return;
                    }
                    return fetchPage(pageNum + 1);
                })
                .catch(() => {
                    setExamQuestions(collected);
                    setExamQuestionsLoading(false);
                });
        };

        fetchPage(1);
         
    }, [studyMode, selectedYear, selectedSubject, selectedDifficulty, selectedExam, searchQuery, isAuthenticated]);

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
            if (detailData.user_selected_answer) {
                setSelectedAnswer(detailData.user_selected_answer);
                setShowAnswer(true);
            }
        }).catch(() => {
            questionsAPI.get(id).then(res => {
                setQuestionDetail(res.data);
                if (res.data.user_selected_answer) {
                    setSelectedAnswer(res.data.user_selected_answer);
                    setShowAnswer(true);
                }
            });
        });
    };

    const handleSelectOption = (opt: string) => {
        if (!detail) return;
        if (showAnswer) return; // Prevent changing answer after revealed
        setSelectedAnswer(opt);
        
        if (studyMode === 'practice') {
            setShowAnswer(true);
            const qId = detail.id;
            const isCorrect = opt === detail.correct_answer;
            questionsAPI.attempt(qId, { selected_answer: opt }).then(res => {
                const tokenEarned = res.data?.token_earned;
                if (tokenEarned) {
                    setQuestions(prev => prev.map(q => q.id === qId ? { ...q, user_selected_answer: opt, user_is_correct: isCorrect } : q));
                }
            }).catch(() => { });
        }
    };

    const handleSubmitExamModeAnswer = () => {
        if (!detail || !selectedAnswer || showAnswer) return;
        setShowAnswer(true);
        const qId = detail.id;
        const isCorrect = selectedAnswer === detail.correct_answer;
        questionsAPI.attempt(qId, { selected_answer: selectedAnswer }).then(res => {
            const tokenEarned = res.data?.token_earned;
            if (tokenEarned) {
                setQuestions(prev => prev.map(q => q.id === qId ? { ...q, user_selected_answer: selectedAnswer, user_is_correct: isCorrect } : q));
            }
        }).catch(() => { });
        // Mark this question answered in the exam palette (only visible
        // when studyMode === 'exam').
        setExamAnswers(prev => ({ ...prev, [qId]: { selected: selectedAnswer, isCorrect, answeredAt: Date.now() } }));
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
        const examType = slugToExamType(selectedExam);
        if (examType) params.exam_type = examType;
        setPage(1);
        fetchQuestions(params);
    };

    const handleFlagSubmit = () => {
        if (!detail || !flagComment.trim()) return;
        setFlagSubmitting(true);
        setFlagError(null);
        questionsAPI.submitFeedback({
            question: detail.id,
            category: flagCategory,
            comment: flagComment.trim(),
        }).then(() => {
            setFlagSuccess(true);
            setTimeout(() => { setFlagOpen(false); setFlagSuccess(false); setFlagComment(''); setFlagError(null); }, 2000);
        }).catch((err: unknown) => {
            const apiError = err as { response?: { data?: unknown } };
            if (apiError.response?.data) {
                setFlagError(extractApiErrorMessage(apiError.response.data, 'Unable to submit feedback right now. Please try again.'));
                return;
            }
            setFlagError('Unable to submit feedback right now. Please try again.');
        })
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
            <div className="main-content lg:h-screen lg:overflow-hidden flex flex-col">
                <Header />
                <div className="page-container space-y-4 pb-0 flex-1 flex flex-col min-h-0">
                <p className="text-sm text-muted-foreground">
                    1,920 PYQs + AI-curated important questions — Master the exam with targeted practice
                </p>

                {/* ═══ Persistent Year Banner ═══
                    Pinned at the top of the page once a year is selected so
                    users always see which PYQ year they are working on. Previously
                    the year chip lived inside the filter card and got buried,
                    so users lost track of their context on mobile. */}
                {selectedYear && (
                    <div className="sticky top-2 z-20 -mx-1">
                        <div className="rounded-2xl border-2 border-primary/40 bg-primary/5 backdrop-blur-sm shadow-sm px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
                            <div className="flex items-center gap-3 min-w-0">
                                <div className="w-9 h-9 rounded-xl bg-primary/15 flex items-center justify-center text-primary shrink-0">
                                    <Calendar className="w-5 h-5" />
                                </div>
                                <div className="min-w-0">
                                    <p className="text-xs font-semibold uppercase tracking-wider text-primary">Active PYQ Bank</p>
                                    <p className="text-base sm:text-lg font-bold text-foreground truncate">
                                        UPSC CMS {selectedYear} · {qbankStats?.by_year?.find((b: any) => String(b.year) === selectedYear)?.count ?? '—'} Questions
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                                <button
                                    type="button"
                                    onClick={() => {
                                        if (studyMode !== 'exam') setStudyMode('exam');
                                    }}
                                    className={`text-xs font-bold px-3 py-2 rounded-xl border transition-colors ${
                                        studyMode === 'exam'
                                            ? 'bg-indigo-600 text-white border-indigo-600'
                                            : 'bg-card text-foreground border-border hover:bg-indigo-50 dark:hover:bg-indigo-900/20'
                                    }`}
                                >
                                    <Target className="w-3.5 h-3.5 inline mr-1" />
                                    Exam Mode
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        router.push(`/questions/practice?year=${selectedYear}&exam=${selectedExam}`);
                                    }}
                                    className="text-xs font-bold px-3 py-2 rounded-xl border bg-card text-foreground border-border hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors"
                                >
                                    <BookOpen className="w-3.5 h-3.5 inline mr-1" />
                                    Practice Fullscreen
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setSelectedYear('')}
                                    className="text-xs font-semibold text-muted-foreground hover:text-foreground px-2 py-1 underline-offset-2 hover:underline"
                                >
                                    Change year
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Unified Dashboard & Filters Panel.
                    `overflow-visible` here (instead of `overflow-hidden`) so the
                    native <select> dropdowns for Subject/Difficulty/Year can
                    overflow the card instead of being clipped — that was causing
                    the "cut text" look on the filter row. */}
                <Card className="border-border/80 bg-card/85 shadow-sm backdrop-blur-xs relative overflow-visible">
                    <div className="absolute top-0 right-0 h-32 w-32 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
                    <CardContent className="p-4 space-y-4">
                        {/* Header & Main Stats Row */}
                        {qbankStats && (
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/40 pb-3">
                                <div className="space-y-2 text-left">
                                    <div className="flex items-center gap-3">
                                        <h2 className="text-lg font-bold text-foreground">
                                            🎯 Question Bank
                                        </h2>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Master {qbankStats.total} high-yield {selectedExam} clinical MCQs and PYQs.
                                    </p>
                                </div>

                                <div className="flex flex-1 max-w-md items-center gap-4">
                                    <div className="flex-1 space-y-1 min-w-0">
                                        <div className="flex justify-between text-xs font-semibold gap-2">
                                            <span className="truncate">Overall Progress</span>
                                            <span className="text-primary font-bold shrink-0">
                                                {qbankStats.total_solved} / {qbankStats.total} ({Math.round(qbankStats.total_solved / (qbankStats.total || 1) * 100)}%)
                                            </span>
                                        </div>
                                        <Progress value={Math.round(qbankStats.total_solved / (qbankStats.total || 1) * 100)} className="h-2" />
                                    </div>
                                    {/* Show/Hide Year Stats — explicit `type=button` so it never submits
                                        a parent form, and `aria-expanded` so screen readers + tests
                                        can verify the toggle actually fired. */}
                                    <button
                                        type="button"
                                        aria-expanded={showStatsDetail}
                                        aria-controls="year-stats-panel"
                                        onClick={() => setShowStatsDetail(prev => !prev)}
                                        className="btn-secondary text-[11px] font-bold py-1.5 px-3 flex items-center gap-1.5 cursor-pointer shrink-0 border border-border/80 relative z-10"
                                    >
                                        {showStatsDetail ? 'Hide Year Stats' : 'Show Year Stats'}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Collapsible Year Breakdown Details — every year
                            from the stats API, in a scrollable grid. Clicking
                            a year tile applies the year filter directly (so
                            "Show Year Stats" reveals the bank + one tap
                            narrows the question list to that year). The
                            long-form "Open Year" button on each tile brings
                            up the modal with Practice / Exam Simulation. */}
                        {qbankStats && showStatsDetail && (
                            <div
                                id="year-stats-panel"
                                className="pt-1 pb-3 border-b border-border/40 animate-fadeIn space-y-2"
                            >
                                <div className="flex items-center justify-between">
                                    <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                                        Tap a year to filter · long-press / right-click for the Practice & Exam modal
                                    </p>
                                    <p className="text-[10px] text-muted-foreground">
                                        {(qbankStats.by_year || []).length} years
                                    </p>
                                </div>
                                <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-1.5 max-h-[260px] overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                                    {(qbankStats.by_year || []).map((item: any) => {
                                        const solvedPct = Math.round(item.solved / (item.count || 1) * 100);
                                        const isSelected = selectedYear === String(item.year);
                                        const isComplete = item.count > 0 && item.solved >= item.count;
                                        return (
                                            <div key={item.year} className="relative group">
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        if (isSelected) {
                                                            setSelectedYear('');
                                                        } else {
                                                            setSelectedYear(String(item.year));
                                                        }
                                                    }}
                                                    className={`w-full p-2 rounded-xl border text-center transition-all cursor-pointer ${isSelected ? 'border-primary bg-primary/10 ring-2 ring-primary/50' : 'border-border/60 bg-muted/30 hover:border-primary/30 hover:bg-muted/65'}`}
                                                    aria-pressed={isSelected}
                                                    aria-label={`Filter to PYQ ${item.year}, ${item.solved} of ${item.count} solved`}
                                                >
                                                    <p className="text-[11px] font-bold text-foreground">{item.year}</p>
                                                    <p className="text-[9px] text-muted-foreground mt-0.5">
                                                        {item.solved}/{item.count}
                                                    </p>
                                                    <div className="w-full bg-border/40 h-1 rounded-full overflow-hidden mt-1">
                                                        <div
                                                            className={`h-full transition-all ${isComplete ? 'bg-emerald-500' : 'bg-primary'}`}
                                                            style={{ width: `${solvedPct}%` }}
                                                        />
                                                    </div>
                                                    {isComplete && (
                                                        <p className="text-[8px] text-emerald-500 font-extrabold mt-0.5">DONE</p>
                                                    )}
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setModalYear(String(item.year));
                                                        setYearModalOpen(true);
                                                        setSimulationError(null);
                                                    }}
                                                    className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity bg-card border border-border shadow-sm rounded-full w-5 h-5 flex items-center justify-center text-[10px] font-bold text-primary hover:bg-primary hover:text-primary-foreground"
                                                    title="Open Practice / Exam modal"
                                                    aria-label={`Open ${item.year} Practice and Exam modal`}
                                                >
                                                    ⤴
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}

                        {/* Persistent year chip — moved to a sticky top banner
                            above the filter card (see banner above). Kept the
                            "Clear year" affordance accessible inside the filter
                            card as well for convenience. */}
                        {selectedYear && (
                            <div className="flex items-center gap-2 -mt-1 text-[11px] text-muted-foreground">
                                <span>Showing only {selectedYear} questions</span>
                                <button
                                    type="button"
                                    onClick={() => setSelectedYear('')}
                                    className="font-semibold text-primary hover:underline underline-offset-2"
                                >
                                    Clear year
                                </button>
                            </div>
                        )}

                        {/* Filters Row */}
                        <div className="flex flex-col gap-3 pt-1">
                            {/* Top row: Search and Exam Mode Toggle */}
                            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
                                <div className="relative w-full sm:max-w-xs flex-1 min-w-0">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                                    <Input className="pl-10 h-9 text-xs w-full" placeholder="Search questions..."
                                        value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleSearch()} />
                                </div>
                                <div className="flex items-center gap-1 bg-muted/30 p-1 rounded-xl border border-border/60 shrink-0">
                                    <button
                                        type="button"
                                        onClick={() => setStudyMode('practice')}
                                        className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all ${studyMode === 'practice' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted/80'}`}
                                    >
                                        Practice Mode
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setStudyMode('exam')}
                                        className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all ${studyMode === 'exam' ? 'bg-indigo-600 text-white shadow-sm' : 'text-muted-foreground hover:bg-muted/80'}`}
                                    >
                                        Exam Mode
                                    </button>
                                </div>
                            </div>
                            {/* Bottom row: Select Filters.
                                Min width 0 on children so grid items shrink correctly
                                on narrow viewports; consistent h-10 across all four
                                controls to remove button-size inconsistency. */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_140px_120px_120px] gap-2 lg:gap-3 items-center">
                                <select
                                    aria-label="Filter by subject"
                                    className="input-field h-10 text-xs px-3 w-full min-w-0 truncate"
                                    value={selectedSubject}
                                    onChange={e => setSelectedSubject(e.target.value)}
                                >
                                    <option value="">All Subjects</option>
                                    {subjects.map(s => (
                                        <option key={s.id} value={s.id}>{s.name} ({s.question_count})</option>
                                    ))}
                                </select>
                                <select
                                    aria-label="Filter by difficulty"
                                    className="input-field h-10 text-xs px-3 w-full min-w-0"
                                    value={selectedDifficulty}
                                    onChange={e => setSelectedDifficulty(e.target.value)}
                                >
                                    <option value="">Difficulty</option>
                                    <option value="easy">Easy</option>
                                    <option value="medium">Medium</option>
                                    <option value="hard">Hard</option>
                                </select>
                                <select
                                    aria-label="Filter by year"
                                    className="input-field h-10 text-xs px-3 w-full min-w-0"
                                    value={selectedYear}
                                    onChange={e => setSelectedYear(e.target.value)}
                                >
                                    <option value="">Year</option>
                                    {years.map(y => (
                                        <option key={y} value={y}>{y}</option>
                                    ))}
                                </select>
                                <Button
                                    variant="neon"
                                    onClick={handleSearch}
                                    size="sm"
                                    className="h-10 px-3 w-full group"
                                >
                                    <Filter className="w-3.5 h-3.5 mr-1 group-hover:rotate-12 transition-transform" /> Filter
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Content */}
                <div className={`qbank-grid flex-1 min-h-0 ${selectedQuestion ? 'has-selected' : ''} ${studyMode === 'exam' ? 'qbank-mode-exam' : ''}`}>
                    {/* Question List */}
                    <div className="qbank-list lg:overflow-y-auto lg:overscroll-contain lg:pr-2" style={{ scrollbarWidth: 'thin' }}>
                        <div className="space-y-3 px-1 py-0.5">
                        {loading ? (
                            <div className="space-y-3">
                                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
                            </div>
                        ) : listError ? (
                            <Card className="p-8 text-center text-destructive">
                                {listError}
                            </Card>
                        ) : questions.length === 0 ? (
                            <Card className="p-8 text-center text-muted-foreground">
                                No questions found. Try adjusting your filters.
                            </Card>
                        ) : (
                            <>
                                {questions.map(q => (
                                    <Card key={q.id} className={`cursor-pointer border-border/80 bg-card/90 p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md ${selectedQuestion === q.id ? 'border-primary/70 ring-2 ring-inset ring-primary/60 shadow-md' : ''}`}
                                        onClick={() => openQuestion(q.id)}>
                                        <div className="flex justify-between items-start mb-2">
                                            <Badge variant="secondary" className="text-xs">
                                                {q.year} &bull; {q.subject_name}
                                            </Badge>
                                            <div className="flex items-center gap-2">
                                                {q.user_selected_answer && (
                                                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${q.user_is_correct ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}`}>
                                                        {q.user_is_correct ? '✓ Solved' : '✗ Incorrect'}
                                                    </span>
                                                )}
                                                {diffBadge(q.difficulty)}
                                                <button
                                                    onClick={(e) => handleBookmark(q.id, e)}
                                                    className="hover:scale-110 transition-transform"
                                                    aria-label={q.is_bookmarked ? `Remove bookmark for question ${q.id}` : `Add bookmark for question ${q.id}`}
                                                    aria-pressed={q.is_bookmarked}
                                                >
                                                    <Bookmark className={`w-4 h-4 ${q.is_bookmarked ? 'text-amber-500 fill-amber-500' : 'text-muted-foreground'}`} />
                                                </button>
                                            </div>
                                        </div>
                                        <p className="text-sm leading-relaxed text-foreground">{stripMarkdown(q.question_text).slice(0, 150)}{q.question_text.length > 150 ? '...' : ''}</p>
                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                            <Badge variant="outline" className="text-xs bg-muted text-foreground border-border/80">{q.topic_name || 'Topic unavailable'}</Badge>
                                            {q.year && <Badge variant="outline" className="text-[10px] bg-muted text-foreground border-border/80">PYQ {q.year}</Badge>}
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
                    {/* Exam-mode question palette — shows all questions in the current
                            filter with attempted / not-attempted state. Rendered as
                            a sticky right rail on desktop and a collapsible
                            bottom-sheet trigger on mobile. */}
                    {studyMode === 'exam' && examPaletteOpen && (
                        <Card className="qbank-palette border-border/80 bg-card/90 backdrop-blur-sm shadow-sm sticky top-0 self-start">
                            <CardContent className="p-4 space-y-3 max-h-[calc(100vh-180px)] overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">Question Palette</h4>
                                        <p className="text-[10px] text-muted-foreground mt-0.5">
                                            {Object.keys(examAnswers).length}/{examQuestions.length || questions.length} answered
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => setExamPaletteOpen(false)}
                                        className="lg:hidden text-xs text-muted-foreground hover:text-foreground"
                                    >Hide</button>
                                </div>

                                {/* Legend */}
                                <div className="flex flex-wrap gap-2 text-[10px]">
                                    <LegendChip color="bg-emerald-500" label="Correct" />
                                    <LegendChip color="bg-red-500" label="Wrong" />
                                    <LegendChip color="bg-amber-400" label="Current" />
                                    <LegendChip color="bg-muted-foreground/40" label="Unseen" />
                                </div>

                                {/* The grid — uses the full exam-mode question
                                    list (all 240 questions for the year, fetched
                                    in pages) so the palette covers every question
                                    like a real UPSC CMS test HUD. Previously this
                                    only mapped over the 20 currently-visible page
                                    items, leaving the rest as empty slots. */}
                                {examQuestionsLoading && examQuestions.length === 0 ? (
                                    <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground">
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                        Loading full palette…
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-6 gap-1.5">
                                        {examQuestions.map((q, idx) => {
                                            const ans = examAnswers[q.id];
                                            const isCurrent = q.id === selectedQuestion;
                                            const status = ans
                                                ? ans.isCorrect ? 'correct' : 'wrong'
                                                : isCurrent ? 'current' : 'unseen';
                                            const statusClass = {
                                                correct: 'bg-emerald-500 text-white border-emerald-500',
                                                wrong: 'bg-red-500 text-white border-red-500',
                                                current: 'bg-amber-400 text-amber-950 border-amber-400 ring-2 ring-amber-400/40',
                                                unseen: 'bg-muted text-muted-foreground border-border hover:bg-muted/80',
                                            }[status];
                                            return (
                                                <button
                                                    key={q.id}
                                                    type="button"
                                                    onClick={() => openQuestion(q.id)}
                                                    className={`aspect-square rounded-lg border text-[11px] font-bold flex items-center justify-center transition-colors ${statusClass}`}
                                                    aria-label={`Question ${idx + 1}, ${status}`}
                                                >
                                                    {idx + 1}
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    <div className="qbank-detail lg:overflow-y-auto lg:overscroll-contain lg:pr-2" style={{ scrollbarWidth: 'thin' }}>
                        {selectedQuestion && !detail ? (
                            // Skeleton placeholder while the question detail loads —
                            // previously the right pane showed stale content from the
                            // previous question until the new fetch resolved.
                            <div className="space-y-3 px-1 py-0.5 animate-fadeIn" aria-busy="true" aria-label="Loading question">
                                <Skeleton className="h-8 w-2/3 rounded-md" />
                                <Skeleton className="h-6 w-1/3 rounded-md" />
                                <Skeleton className="h-32 w-full rounded-2xl" />
                                <div className="space-y-2">
                                    {[0, 1, 2, 3].map(i => (
                                        <Skeleton key={i} className="h-12 w-full rounded-xl" />
                                    ))}
                                </div>
                                <Skeleton className="h-20 w-full rounded-xl" />
                            </div>
                        ) : selectedQuestion && detail ? (
                            <div className="animate-fadeInUp space-y-4 px-1 py-0.5">
                                {/* Question Card */}
                                <div className="glass-card rounded-2xl border border-primary/40 shadow-[0_18px_40px_rgba(14,116,144,0.16)]">
                                    <div className="px-5 py-3 flex flex-wrap items-center gap-2 border-b border-border bg-slate-50 dark:bg-slate-900/50">
                                        <Badge variant="secondary" className="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 pointer-events-none">PYQ {String(detail.year)}</Badge>
                                        <Badge variant="secondary" className="pointer-events-none">{String(detail.subject_name)}</Badge>
                                        {detail.topic_name && <Badge variant="outline" className="pointer-events-none">{String(detail.topic_name)}</Badge>}
                                        {detail.difficulty && <Badge variant="outline" className="pointer-events-none capitalize">{detail.difficulty}</Badge>}
                                        {detail.is_verified_by_admin && (
                                            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 pointer-events-none">
                                                ✔ Verified by Admin
                                            </Badge>
                                        )}
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

                                                // Readable palette — was using `opacity-80`
                                                // on wrong/unselected options which made
                                                // the option text invisible in light mode.
                                                return (
                                                    <div key={opt}
                                                        className={`flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer ${
                                                            showAnswer
                                                                ? (isCorrect
                                                                    ? 'border-emerald-500 bg-emerald-50/70 dark:bg-emerald-950/30 text-foreground'
                                                                    : isWrong
                                                                        ? 'border-red-500 bg-red-50/70 dark:bg-red-950/30 text-foreground'
                                                                        : 'border-border/70 bg-muted/40 text-foreground')
                                                                : (isSelected
                                                                    ? 'border-primary bg-primary/5 ring-1 ring-primary text-foreground'
                                                                    : 'border-border bg-card hover:bg-muted/60 text-foreground')
                                                        }`}
                                                        onClick={() => handleSelectOption(opt)}>
                                                        <div className={`w-7 h-7 shrink-0 flex items-center justify-center rounded-full text-sm font-bold transition-colors ${showAnswer ? (isCorrect ? 'bg-emerald-500 text-white' : isWrong ? 'bg-red-500 text-white' : 'bg-muted text-muted-foreground') : (isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')}`}>{opt}</div>
                                                        <div className="flex-1 text-sm font-medium">{cleanOptionText(String(optionText))}</div>
                                                        {showAnswer && isCorrect && <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">✓ Correct</span>}
                                                        {isWrong && <span className="text-xs font-bold text-red-600 dark:text-red-400">✗ Wrong</span>}
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        {!showAnswer && !selectedAnswer && studyMode === 'practice' && (
                                            <p className="text-xs text-center py-2 text-muted-foreground">👆 Select an option to reveal the answer & detailed analysis</p>
                                        )}
                                        
                                        {!showAnswer && studyMode === 'exam' && (
                                            <div className="mt-6 flex justify-end">
                                                <Button 
                                                    variant="neon" 
                                                    onClick={handleSubmitExamModeAnswer} 
                                                    disabled={!selectedAnswer}
                                                    className="w-full sm:w-auto"
                                                >
                                                    Submit Answer
                                                </Button>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* === ANSWER ANALYSIS === */}
                                {showAnswer && (
                                    <div className="space-y-3 animate-fadeInUp">
                                        {/* ✅ Correct Answer — light/dark readable palette:
                                            bg-emerald-50 was washed out so explanation body
                                            was nearly invisible. Switched to a stronger
                                            emerald tone with an opaque white inner card so
                                            the body text inherits proper contrast. */}
                                        <Card className="border-emerald-300 bg-emerald-50/80 dark:bg-emerald-950/30 dark:border-emerald-800/60">
                                            <CardContent className="p-4 space-y-2">
                                                <h4 className="text-sm font-bold text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
                                                    <CheckCircle className="w-4 h-4" /> Correct Answer: {detail.correct_answer}
                                                </h4>
                                                {detail.explanation && (
                                                    <div className="rounded-lg bg-white/80 dark:bg-slate-900/40 p-3 text-sm leading-relaxed text-foreground">
                                                        <FormattedText text={String(detail.explanation)} />
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>

                                        {/* VIDEO PLAYER */}
                                        {detail?.video_url && detail?.video_status === 'completed' && (
                                            <div className="explanation-card explanation-card-indigo animate-fadeInUp mt-4 mb-4 overflow-hidden">
                                                <div className="p-1">
                                                    <h4 className="explanation-card-title indigo px-4 py-2"><Play className="w-4 h-4" /> AI Video Explanation</h4>
                                                    <PremiumVideoPlayer 
                                                        src={detail.video_url} 
                                                        subtitlesSrc={detail.video_subtitles_url}
                                                        poster={detail.video_thumbnail}
                                                        className="w-full max-h-[500px]"
                                                    />
                                                </div>
                                            </div>
                                        )}

                                        {/* 🚩 Flag Wrong Answer */}
                                        <div className="flex justify-end">
                                            <button onClick={() => { setFlagOpen(!flagOpen); setFlagSuccess(false); setFlagError(null); }}
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
                                                        {flagError && <p className="text-sm text-destructive">{flagError}</p>}
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
                                                            value={flagComment} onChange={e => setFlagComment(e.target.value)} />
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

                                        {/* Generate AI Analysis button — shown directly below flag section */}
                                        {!aiExplanation && !aiLoading && !tokenError && (
                                            <button onClick={() => fetchAiExplanation()}
                                                className="w-full rounded-2xl border border-blue-200 bg-blue-50/50 dark:bg-blue-900/10 dark:border-blue-800/50 p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:bg-blue-50 dark:hover:bg-blue-900/20 mt-1">
                                                <Brain className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                                                <div className="text-left">
                                                    <span className="text-sm font-bold block text-blue-700 dark:text-blue-300">Generate AI Analysis</span>
                                                    <span className="text-xs text-muted-foreground">Click to get mnemonics, explanations, exam tips & more</span>
                                                </div>
                                            </button>
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
                                                <Bookmark className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#8b5cf6' }} />
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
                                                <div className="flex items-center gap-2 px-1 pt-1 opacity-80">
                                                    <Brain className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                                    <span className="font-bold text-xs tracking-wider text-blue-600 dark:text-blue-400 uppercase">AI-Powered Deep Analysis</span>
                                                    <div className="flex-1 h-px bg-border ml-2"></div>
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
                                                            <FormattedText text={cleanAiText(aiExplanation.why_correct)} />
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

                                                {/* 📚 Reference */}
                                                {aiExplanation.textbook_reference?.book && (
                                                    <div className="glass-card p-4 flex items-start gap-2.5">
                                                        <Bookmark className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#8b5cf6' }} />
                                                        <div>
                                                            <h6 className="text-xs font-bold mb-0.5" style={{ color: '#8b5cf6' }}>📚 Textbook Reference</h6>
                                                            <p className="text-xs font-semibold">{aiExplanation.textbook_reference.book}</p>
                                                            {aiExplanation.textbook_reference.chapter && <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>Ch: {aiExplanation.textbook_reference.chapter}</p>}
                                                            {aiExplanation.textbook_reference.page && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Pg: {aiExplanation.textbook_reference.page}</p>}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* DEEP DIVE TOGGLE */}
                                                {(aiExplanation.topic_deep_dive || aiExplanation.high_yield_points?.length > 0 || aiExplanation.key_differentiators?.length > 0 || aiExplanation.around_concepts?.length > 0 || aiExplanation.pyq_frequency || aiExplanation.similar_pyq || aiExplanation.clinical_pearl || aiExplanation.exam_tip || aiExplanation.quick_revision) && (
                                                    <div className="mt-4">
                                                        <button 
                                                            onClick={() => setShowAiDeepDive(!showAiDeepDive)}
                                                            className="flex items-center justify-between w-full p-3 glass-card hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                                                            style={{ borderColor: 'rgba(99,102,241,0.3)' }}
                                                        >
                                                            <span className="font-bold text-sm flex items-center gap-2" style={{ color: '#6366f1' }}>
                                                                <Brain className="w-4 h-4" /> Deep Dive & PYQ Analysis
                                                            </span>
                                                            {showAiDeepDive ? <ChevronDown className="w-4 h-4 text-indigo-500" /> : <ChevronRight className="w-4 h-4 text-indigo-500" />}
                                                        </button>
                                                        
                                                        {showAiDeepDive && (
                                                            <div className="mt-3 space-y-3 animate-in slide-in-from-top-2 fade-in duration-200">
                                                                {/* 📖 Topic Deep Dive */}
                                                                {aiExplanation.topic_deep_dive && (
                                                                    <div className="explanation-card explanation-card-indigo">
                                                                        <div className="explanation-card-accent indigo"></div>
                                                                        <div className="p-4 pl-5">
                                                                            <h4 className="explanation-card-title indigo"><BookOpen className="w-4 h-4" /> 📖 Topic Deep Dive — Learn the Bigger Picture</h4>
                                                                            <FormattedText text={cleanAiText(aiExplanation.topic_deep_dive)} />
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

                                                                {/* 💎 Pearl + 🎓 Exam Tip */}
                                                                {(aiExplanation.clinical_pearl || aiExplanation.exam_tip) && (
                                                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                                                                )}

                                                                {/* 📝 Quick Revision */}
                                                                {aiExplanation.quick_revision && (
                                                                    <div className="quick-revision-card">
                                                                        <div className="absolute top-0 left-0 w-full h-1" style={{ background: 'var(--gradient-primary)' }}></div>
                                                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1.5" style={{ color: 'var(--accent-primary)' }}>
                                                                            <Lightbulb className="w-3.5 h-3.5" /> 📝 Quick Revision — Read Before Exam
                                                                        </h5>
                                                                        <FormattedText text={cleanAiText(aiExplanation.quick_revision)} />
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
                                                                        {aiExplanation.pyq_frequency && <FormattedText text={`📈 **Frequency:** ${cleanAiText(aiExplanation.pyq_frequency)}`} />}
                                                                        {aiExplanation.similar_pyq && <FormattedText text={`📋 **Similar Questions:** ${cleanAiText(aiExplanation.similar_pyq)}`} />}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* 📖 Textbook Reference Lookup */}
                                {showAnswer && detail && (
                                    <div className="space-y-2">
                                        {!textbookRef && !textbookLoading && (
                                            <button
                                                onClick={() => {
                                                    setTextbookLoading(true);
                                                    setTextbookRef(null);
                                                    setTextbookScreenshot(null);
                                                    aiAPI.textbookReference({ question_text: detail.question_text })
                                                        .then(res => {
                                                            setTextbookRef(res.data);
                                                            // Try to get screenshot
                                                            aiAPI.getScreenshot(detail.id)
                                                                .then(sRes => {
                                                                    if (sRes.data?.screenshot_url) setTextbookScreenshot(sRes.data.screenshot_url);
                                                                })
                                                                .catch(() => {});
                                                        })
                                                        .catch(() => {
                                                            setTextbookRef({ error: true });
                                                        })
                                                        .finally(() => setTextbookLoading(false));
                                                }}
                                                className="w-full rounded-2xl border border-indigo-200 bg-indigo-50/50 dark:bg-indigo-900/10 dark:border-indigo-800/50 p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:bg-indigo-50 dark:hover:bg-indigo-900/20"
                                            >
                                                <Bookmark className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                                                <div className="text-left">
                                                    <span className="text-sm font-bold block text-indigo-700 dark:text-indigo-300">Find in Textbook</span>
                                                    <span className="text-xs text-muted-foreground">See which book, chapter & page covers this topic</span>
                                                </div>
                                            </button>
                                        )}
                                        {textbookLoading && (
                                            <div className="flex items-center justify-center gap-3 p-4 rounded-xl border border-indigo-200 bg-indigo-50/30 dark:bg-indigo-900/10">
                                                <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />
                                                <span className="text-xs font-medium text-indigo-600">Looking up textbook references...</span>
                                            </div>
                                        )}
                                        {textbookRef && !textbookRef.error && (
                                            <Card className="border-indigo-200 bg-indigo-50/30 dark:bg-indigo-950/10 dark:border-indigo-900/30">
                                                <CardContent className="p-4 space-y-2">
                                                    <h5 className="text-xs font-bold text-indigo-700 dark:text-indigo-400 flex items-center gap-1.5">
                                                        <Bookmark className="w-3.5 h-3.5" /> 📖 Textbook Reference
                                                    </h5>
                                                    {textbookRef.book_name && <p className="text-sm font-semibold">{textbookRef.book_name}</p>}
                                                    {textbookRef.chapter && <p className="text-xs text-muted-foreground">Chapter: {textbookRef.chapter}</p>}
                                                    {textbookRef.page_range && <p className="text-xs text-muted-foreground">Pages: {textbookRef.page_range}</p>}
                                                    {textbookRef.excerpt && <p className="text-xs leading-relaxed mt-1 italic text-muted-foreground">&quot;{textbookRef.excerpt}&quot;</p>}
                                                    {textbookRef.reference && typeof textbookRef.reference === 'string' && (
                                                        <p className="text-xs leading-relaxed text-muted-foreground">{textbookRef.reference}</p>
                                                    )}
                                                    {textbookScreenshot && (
                                                        <div className="mt-2 rounded-lg overflow-hidden border border-border/40 bg-white">
                                                            <img
                                                              src={textbookScreenshot}
                                                              alt="Textbook page screenshot"
                                                              width={800}
                                                              height={1000}
                                                              loading="lazy"
                                                              className="w-full h-auto"
                                                            />
                                                            <p className="text-[10px] text-center text-muted-foreground py-1 bg-muted/30">Screenshot from textbook page</p>
                                                        </div>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        )}
                                        {textbookRef?.error && (
                                            <Card className="border-border/60">
                                                <CardContent className="p-3 text-center text-xs text-muted-foreground">
                                                    No textbook mapping available for this question.
                                                </CardContent>
                                            </Card>
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
                            <Card className="p-16 text-center h-125 flex flex-col items-center justify-center">
                                <BookOpen className="w-16 h-16 mx-auto mb-6 text-muted-foreground/30" />
                                <p className="text-lg font-medium mb-2 text-foreground">Select a Question</p>
                                <p className="text-sm text-muted-foreground">Click any question from the bank to practice and review detailed AI-powered explanations.</p>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
            </div>

            {/* Mobile exam palette toggle — only in exam mode and when the
                right-rail palette is hidden. Shows count against the full
                exam-mode question set (240) instead of the loaded page (20). */}
            {studyMode === 'exam' && !examPaletteOpen && (
                <button
                    type="button"
                    onClick={() => setExamPaletteOpen(true)}
                    className="fixed bottom-20 right-4 z-30 lg:hidden bg-indigo-600 text-white shadow-lg rounded-full px-4 py-2 text-xs font-bold flex items-center gap-2"
                >
                    <ListChecks className="w-4 h-4" />
                    Palette ({Object.keys(examAnswers).length}/{examQuestions.length || questions.length})
                </button>
            )}

            {/* Year Modal Popup — centered on desktop, anchored near the top
                on mobile so the two option buttons (Practice / Exam Simulation)
                are immediately visible instead of being squeezed at the bottom
                of a small viewport. The wrapper scrolls if the card itself
                overflows on tall phones. */}
            {yearModalOpen && modalYear && (
                <div className="fixed inset-0 z-50 flex items-start sm:items-center justify-center bg-black/60 backdrop-blur-xs p-4 pt-16 sm:pt-4 overflow-y-auto animate-fadeIn">
                    <Card className="max-w-md w-full border-border/80 bg-card shadow-2xl relative overflow-hidden animate-fadeInUp">
                        <div className="absolute top-0 right-0 h-32 w-32 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
                        <CardContent className="p-6 space-y-6">
                            <div className="text-center space-y-2">
                                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-2 text-primary">
                                    <Target className="w-6 h-6 animate-pulse" />
                                </div>
                                <h3 className="text-xl font-bold text-foreground">UPSC CMS {modalYear} PYQs</h3>
                                <p className="text-xs text-muted-foreground">
                                    Select how you would like to prepare with the {modalYear} question bank.
                                </p>
                            </div>

                            {simulationError && (
                                <div className="p-3 text-xs rounded-xl bg-destructive/10 text-destructive border border-destructive/20">
                                    {simulationError}
                                </div>
                            )}

                            <div className="grid gap-3">
                                {/* Option 1: Practice Mode — opens fullscreen immersive page */}
                                <button
                                    onClick={() => {
                                        router.push(`/questions/practice?year=${modalYear}&exam=${selectedExam}`);
                                    }}
                                    className="w-full p-4 rounded-xl border border-border/80 bg-muted/20 hover:bg-muted/50 hover:border-primary/30 text-left transition-all group flex gap-3 cursor-pointer"
                                >
                                    <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-500 shrink-0 group-hover:scale-105 transition-transform">
                                        <BookOpen className="w-5 h-5" />
                                    </div>
                                    <div>
                                        <span className="font-bold text-sm text-foreground block group-hover:text-primary transition-colors">Study & Practice Mode</span>
                                        <span className="text-[11px] text-muted-foreground mt-0.5 block">Fullscreen, one-question-at-a-time practice with AI explanations and textbook references.</span>
                                    </div>
                                </button>

                                {/* Option 2: Timed Exam Mode */}
                                <button
                                    onClick={() => {
                                        if (startingSimulation) return;
                                        setStartingSimulation(true);
                                        setSimulationError(null);
                                        testsAPI.pyqSimulation({ year: Number(modalYear) })
                                            .then(res => {
                                                router.push(`/tests/${res.data.id}`);
                                            })
                                            .catch(err => {
                                                setSimulationError(extractApiErrorMessage(err.response?.data || err.message, 'Failed to generate simulation. Make sure there are enough questions in the database.'));
                                                setStartingSimulation(false);
                                            });
                                    }}
                                    disabled={startingSimulation}
                                    className="w-full p-4 rounded-xl border border-border/80 bg-muted/20 hover:bg-muted/50 hover:border-primary/30 text-left transition-all group flex gap-3 cursor-pointer disabled:opacity-50"
                                >
                                    <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-500 shrink-0 group-hover:scale-105 transition-transform">
                                        {startingSimulation ? <Loader2 className="w-5 h-5 animate-spin" /> : <GraduationCap className="w-5 h-5" />}
                                    </div>
                                    <div>
                                        <span className="font-bold text-sm text-foreground block group-hover:text-primary transition-colors">
                                            {startingSimulation ? 'Generating Simulator...' : 'Timed Exam Simulation'}
                                        </span>
                                        <span className="text-[11px] text-muted-foreground mt-0.5 block">120 questions, 120-minute time limit, negative marking (-0.33). Experience the real UPSC CMS exam HUD.</span>
                                    </div>
                                </button>
                            </div>

                            <div className="flex gap-2 pt-2 border-t border-border/50">
                                <Button
                                    variant="ghost"
                                    className="w-full text-xs font-semibold"
                                    onClick={() => {
                                        setYearModalOpen(false);
                                        setModalYear(null);
                                        setSimulationError(null);
                                    }}
                                    disabled={startingSimulation}
                                >
                                    Cancel
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
