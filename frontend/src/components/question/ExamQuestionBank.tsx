/**
 * ExamQuestionBank — Phase-9 unified Question Bank.
 *
 * Extracted from /questions/page.tsx so the same bank UI powers:
 *   - /questions               (UPSC CMS, default exam)
 *   - /questions/neet-pg/practice
 *   - /questions/inicet/practice
 *
 * Left panel: filterable, paginated question list with subject/year/difficulty
 * filters, year-stats grid, and a Practice/Exam-mode toggle.
 * Right panel: question detail with options, answer reveal, AI Deep
 * Analysis (mnemonic, why correct/wrong, topic deep dive, high-yield
 * points, key differentiators, textbook references, clinical pearls,
 * exam tips, quick revision, related concepts, PYQ intelligence).
 *
 * Token-aware: 429 surfaces a "buy more tokens" banner.
 *
 * `examType`   → backend `exam_type` enum (filters `Question.exam_type`)
 * `examSource` → backend `exam_source` label (filters `Question.exam_source`)
 *                and is shown in the page title / sticky year banner.
 * `defaultYear`, `initialQueryId`, `initialBookmarkOnly` pre-seed the
 * initial filter state from URL params so links like
 * `/questions/neet-pg/practice?year=2025&q=12345` open the right
 * question immediately.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { questionsAPI, aiAPI, testsAPI, extractApiErrorMessage } from '@/lib/api';
import {
    BookOpen, Search, Filter, Bookmark, ChevronLeft, ChevronRight,
    ChevronDown, Loader2, Brain, Sparkles, CheckCircle, ArrowRight,
    Flag, Target, Zap, GraduationCap, Lightbulb, Play, Calendar, ListChecks,
    Lock,
} from 'lucide-react';
import DiscussionThread from '@/components/DiscussionThread';
import { ExamTrackProvider, useExamTrack } from '@/components/ExamTrackProvider';
import ImageViewer, { type ViewerImage } from '@/components/image/ImageViewer';
import { useDock } from '@/context/DockContext';
import { useQuestionFocus } from '@/context/QuestionFocusContext';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { PremiumVideoPlayer } from '@/components/ui/PremiumVideoPlayer';
import { LockedBadge } from '@/components/paywall/LockedBadge';
import { usePaywall } from '@/lib/paywall/paywallContext';
import { FormattedText, stripMarkdown, resolveImageTokensForMarkdown } from '@/components/FormattedText';
import { cleanOptionText, decodeMojiB, extractAnalysisFromJson, isLikelyGarbled, sanitizeQuestionText, sanitizeOptionText } from '@/lib/textCleanup';
import { analytics } from '@/lib/analytics';

/** Color-swatch chip used inside the exam-mode palette legend. */
function LegendChip({ color, label }: { color: string; label: string }) {
    return (
        <span className="inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
            <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />
            {label}
        </span>
    );
}

/**
 * Cleans AI response text — strips JSON/code fence artifacts that appear
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

interface ExamQuestionBankProps {
    /** DB enum value for `Question.exam_type` (e.g. 'cms', 'neet_pg'). */
    examType: string;
    /** Human label for `Question.exam_source` (e.g. 'UPSC CMS', 'NEET PG'). */
    examSource: string;
    /** Optional year to pre-select from `?year=` URL param. */
    defaultYear?: string | null;
    /** Optional question id to auto-open from `?q=` URL param. */
    initialQueryId?: string | null;
    /** Optional bookmarked-only filter from `?bookmarked=1` URL param. */
    initialBookmarkOnly?: boolean;
}

const PAGE_SIZE = 20;

export default function ExamQuestionBank({
    examType,
    examSource,
    defaultYear = null,
    initialQueryId = null,
    initialBookmarkOnly = false,
}: ExamQuestionBankProps) {
    return (
        <ExamTrackProvider>
            <ExamQuestionBankInner
                examType={examType}
                examSource={examSource}
                defaultYear={defaultYear}
                initialQueryId={initialQueryId}
                initialBookmarkOnly={initialBookmarkOnly}
            />
        </ExamTrackProvider>
    );
}

function ExamQuestionBankInner({
    examType,
    examSource,
    defaultYear,
    initialQueryId,
    initialBookmarkOnly,
}: ExamQuestionBankProps) {
    const { isAuthenticated, loading: authLoading, user } = useAuth();
    const { activeTrack } = useExamTrack();
    const { setContextQuestionId } = useDock();
    const { show: showPaywall } = usePaywall();
    // Freemium: a user is "premium" if they have an active subscription OR
    // are admin/staff — mirrors backend `accounts.utils.is_premium`.
    const isPremium =
        (user as { is_premium?: boolean } | null)?.is_premium === true ||
        (user as { subscription_info?: { is_active?: boolean } } | null)?.subscription_info?.is_active === true ||
        (user as { is_admin?: boolean } | null)?.is_admin === true;
    // Broadcast whether a question is currently being solved so the
    // SidebarAutoHide controller can keep the sidebar collapsed for the
    // entire /questions session while a question is open.
    const { setQuestionFocused } = useQuestionFocus();
    const router = useRouter();
    const searchParams = useSearchParams();

    // `examType` is the source of truth for which bank we're showing. We
    // intentionally do NOT honour `?exam=` overrides here — the route URL
    // is authoritative. (The standalone `/questions` page has its own
    // override behaviour; see `QuestionsBankSlim` below.)
    const [selectedExam, setSelectedExam] = useState<string>(examType);

    const [questions, setQuestions] = useState<Question[]>([]);
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedSubject, setSelectedSubject] = useState('');
    const [selectedDifficulty, setSelectedDifficulty] = useState('');
    const [selectedYear, setSelectedYear] = useState<string>(defaultYear ?? '');
    const [years, setYears] = useState<number[]>([]);
    const [qbankStats, setQbankStats] = useState<any>(null);
    const [listError, setListError] = useState<string | null>(null);
    const [selectedQuestion, setSelectedQuestion] = useState<number | null>(
        initialQueryId ? Number(initialQueryId) : null,
    );
    const [questionDetail, setQuestionDetail] = useState<any>(null);
    const [showAnswer, setShowAnswer] = useState(false);
    const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
    const [studyMode, setStudyMode] = useState<'practice' | 'exam'>('practice');
    const [examAnswers, setExamAnswers] = useState<Record<number, { selected: string; isCorrect: boolean; answeredAt: number }>>({});
    const [examPaletteOpen, setExamPaletteOpen] = useState(true);
    const [page, setPage] = useState(1);
    const [totalCount, setTotalCount] = useState(0);
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
    const [bookmarkedOnly, setBookmarkedOnly] = useState<boolean>(initialBookmarkOnly ?? false);
    // Image viewer modal state — null when closed. Clicking a thumbnail
    // in the question image carousel opens ImageViewer at the right index,
    // matching the standalone NEET-PG / INI-CET player UX.
    const [viewImageIdx, setViewImageIdx] = useState<number | null>(null);

    const [yearModalOpen, setYearModalOpen] = useState(false);
    const [modalYear, setModalYear] = useState<string | null>(null);
    const [startingSimulation, setStartingSimulation] = useState(false);
    const [simulationError, setSimulationError] = useState<string | null>(null);
    const [showStatsDetail, setShowStatsDetail] = useState(false);

    const [examQuestions, setExamQuestions] = useState<Question[]>([]);
    const [examQuestionsLoading, setExamQuestionsLoading] = useState(false);

    const [textbookRef, setTextbookRef] = useState<any>(null);
    const [textbookLoading, setTextbookLoading] = useState(false);
    const [textbookScreenshot, setTextbookScreenshot] = useState<string | null>(null);

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
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

            const key = e.key.toLowerCase();
            const detail = questionDetail as any;
            if (['a', 'b', 'c', 'd'].includes(key) && detail && !showAnswer) {
                e.preventDefault();
                handleSelectOption(key.toUpperCase());
            }

            if (key === 'n' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                const currentIdx = questions.findIndex(q => q.id === selectedQuestion);
                if (currentIdx >= 0 && currentIdx < questions.length - 1) {
                    openQuestion(questions[currentIdx + 1].id);
                } else if (page < Math.ceil(totalCount / PAGE_SIZE)) {
                    handlePageChange(page + 1);
                }
            }

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

    // Initial list + stats + subjects + years.
    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            setListError(null);
            // Fetch every page of subjects — the DRF default page_size=20 caps the
            // response at 20 rows, so a single fetch was clipping 'Expert Curated'
            // (id=291 + id=309, alphabetically last) into page 2 and dropping it
            // from the dropdown. Subject count is small (~40 rows total) so a
            // short loop is cheap.
            const fetchAllSubjects = async () => {
                const collected: Subject[] = [];
                let page = 1;
                // Hard cap protects against a misconfigured backend that returns
                // an unbounded `next` pointer; in practice there are < 50 subjects.
                while (page <= 10) {
                    const res = await questionsAPI.getSubjects({ page, page_size: 100 });
                    const results = res.data?.results || res.data || [];
                    if (!Array.isArray(results) || results.length === 0) break;
                    collected.push(...results);
                    if (!res.data?.next) break;
                    page += 1;
                }
                return collected;
            };
            Promise.all([
                questionsAPI.list({ page: 1, page_size: PAGE_SIZE, exam_type: selectedExam }),
                // Subjects are NOT filtered by exam_type: the Question → Subject FK
                // model uses the same medical subject names across CMS / NEET PG /
                // INI-CET tracks, and the loader's "Imported" bucket is itself
                // tagged exam_type='cms'. Filtering by exam_type=cms therefore
                // hides every real medical subject (Anatomy, Surgery, etc.) and
                // leaves only the two "Expert Curated" rows, which is what users
                // were seeing before this fix.
                fetchAllSubjects(),
                questionsAPI.getYears(),
                questionsAPI.getStats({ exam_source: examSource }),
            ]).then(([qRes, allSubjects, yRes, statsRes]) => {
                const qData = qRes.data;
                setQuestions(qData.results || qData || []);
                setTotalCount(qData.count || (qData.results || qData || []).length);
                setSubjects(allSubjects);
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

    // Honour `?q=ID` from the URL on first mount after questions load.
    useEffect(() => {
        if (!initialQueryId) return;
        const id = Number(initialQueryId);
        if (!Number.isFinite(id) || id <= 0) return;
        if (loading || !isAuthenticated || questionDetail) return;
        if (questions.some(q => q.id === id) || page === 1) {
            openQuestion(id);
        }
    }, [initialQueryId, loading, isAuthenticated, questions, page]); // eslint-disable-line react-hooks/exhaustive-deps

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
        const params: Record<string, string | number> = { page: 1, page_size: PAGE_SIZE };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        if (bookmarkedOnly) params.bookmarked = 'true';
        params.exam_type = selectedExam;
        setPage(1);
        fetchQuestions(params);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedSubject, selectedDifficulty, selectedYear, selectedExam, searchQuery, bookmarkedOnly]);

    const handlePageChange = (newPage: number) => {
        setPage(newPage);
        const params: Record<string, string | number> = { page: newPage, page_size: PAGE_SIZE };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        if (bookmarkedOnly) params.bookmarked = 'true';
        params.exam_type = selectedExam;
        fetchQuestions(params);
    };

    // Reset exam state when toggling modes or changing filters.
    useEffect(() => {
        setExamAnswers({});
    }, [studyMode, selectedSubject, selectedDifficulty, selectedYear, selectedExam, searchQuery, bookmarkedOnly]);

    // Exam-mode: load ALL questions for the selected year (or current filter
    // set) so the right-rail palette can show every question number like a
    // real test HUD — not just the 20 currently visible on the list page.
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
        if (bookmarkedOnly) params.bookmarked = 'true';
        params.exam_type = selectedExam;

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
    }, [studyMode, selectedYear, selectedSubject, selectedDifficulty, selectedExam, searchQuery, isAuthenticated, bookmarkedOnly]);

    const openQuestion = useCallback((id: number) => {
        setSelectedQuestion(id);
        setShowAnswer(false);
        setSelectedAnswer(null);
        setAiExplanation(null);
        setAiLoading(false);
        setTokenError(false);
        setAiError(null);
        setTextbookRef(null);
        setTextbookScreenshot(null);
        setTextbookLoading(false);
        Promise.all([
            questionsAPI.get(id),
            questionsAPI.getSimilar(id),
        ]).then(([qRes, sRes]) => {
            const detailData = qRes.data;
            detailData.similar = sRes.data;
            setQuestionDetail(detailData);
            // Track the prior attempt for the Resume banner (line 998 area)
            // but DO NOT auto-reveal the explanation — that defeats practice
            // mode. Students must pick an option again to see the answer.
            if (detailData.user_selected_answer) {
                setSelectedAnswer(detailData.user_selected_answer);
            }
        }).catch(() => {
            questionsAPI.get(id).then(res => {
                setQuestionDetail(res.data);
                if (res.data.user_selected_answer) {
                    setSelectedAnswer(res.data.user_selected_answer);
                }
            });
        });
    }, []);

    useEffect(() => {
        setContextQuestionId(selectedQuestion);
    }, [selectedQuestion, setContextQuestionId]);

    // Broadcast "user is solving a question" to the rest of the app so the
    // SidebarAutoHide controller can keep the sidebar collapsed while the
    // question is open (and re-expand it when the user closes the question
    // by navigating away / picking a different list view).
    useEffect(() => {
        setQuestionFocused(selectedQuestion !== null);
    }, [selectedQuestion, setQuestionFocused]);

    const handleSelectOption = (opt: string) => {
        if (!questionDetail) return;
        if (showAnswer) return;
        setSelectedAnswer(opt);

        if (studyMode === 'practice') {
            setShowAnswer(true);
            const qId = questionDetail.id;
            const isCorrect = opt === questionDetail.correct_answer;
            questionsAPI.attempt(qId, { selected_answer: opt }).then(res => {
                const tokenEarned = res.data?.token_earned;
                if (tokenEarned) {
                    setQuestions(prev => prev.map(q => q.id === qId ? { ...q, user_selected_answer: opt, user_is_correct: isCorrect } : q));
                }
            }).catch(() => { });
        }
    };

    const handleSubmitExamModeAnswer = () => {
        if (!questionDetail || !selectedAnswer || showAnswer) return;
        setShowAnswer(true);
        const qId = questionDetail.id;
        const isCorrect = selectedAnswer === questionDetail.correct_answer;
        questionsAPI.attempt(qId, { selected_answer: selectedAnswer }).then(res => {
            const tokenEarned = res.data?.token_earned;
            if (tokenEarned) {
                setQuestions(prev => prev.map(q => q.id === qId ? { ...q, user_selected_answer: selectedAnswer, user_is_correct: isCorrect } : q));
            }
        }).catch(() => { });
        setExamAnswers(prev => ({ ...prev, [qId]: { selected: selectedAnswer, isCorrect, answeredAt: Date.now() } }));
    };

    const fetchAiExplanation = (retryCount: number = 0) => {
        if (!questionDetail || aiLoading) return;
        const d = questionDetail as any;
        analytics.aiExplanationOpen(d.id, String(d.subject_name || ''));
        setAiLoading(true);
        setAiExplanation(null);
        setTokenError(false);
        setAiError(null);
        aiAPI.explainAfterAnswer({
            question_text: sanitizeQuestionText(d.question_text),
            options: {
                A: sanitizeOptionText(d.option_a || d.option_A || ''),
                B: sanitizeOptionText(d.option_b || d.option_B || ''),
                C: sanitizeOptionText(d.option_c || d.option_C || ''),
                D: sanitizeOptionText(d.option_d || d.option_D || ''),
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
            if (questionDetail?.id === id) {
                setQuestionDetail((prev: any) => prev ? { ...prev, is_bookmarked: !prev.is_bookmarked } : prev);
            }
        });
    };

    const handleSearch = () => {
        const params: Record<string, string | number> = { page: 1, page_size: PAGE_SIZE };
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (selectedYear) params.year = selectedYear;
        if (searchQuery) params.search = searchQuery;
        if (bookmarkedOnly) params.bookmarked = 'true';
        params.exam_type = selectedExam;
        setPage(1);
        fetchQuestions(params);
    };

    const handleFlagSubmit = () => {
        if (!questionDetail || !flagComment.trim()) return;
        setFlagSubmitting(true);
        setFlagError(null);
        questionsAPI.submitFeedback({
            question: questionDetail.id,
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
    const totalPages = Math.ceil(totalCount / PAGE_SIZE);

    // ── Render ────────────────────────────────────────────
    // NOTE: do NOT add the shell's `main-content` class here. The page
    // shell (Sidebar + Header + <div class="main-content">) already
    // owns that class and its `margin-left: 260px` (sidebar offset).
    // Re-applying it inside <ExamQuestionBank> doubled the offset, so
    // the bank content landed at x≈540 instead of x≈280 with a huge
    // white gap on the left. The CMS `<QuestionsPage>` had this same
    // wrapper historically and never stripped the class — keep the
    // inner `lg:h-screen lg:overflow-hidden flex flex-col` to preserve
    // the question list scroll layout, just drop the redundant class.
    return (
        <div className="bank-shell lg:h-screen lg:overflow-hidden flex flex-col">
            <div className="qbank-container space-y-4 pb-0 flex-1 flex flex-col min-h-0">
                <p className="text-sm text-muted-foreground">
                    Master {examSource} PYQs with AI-powered explanations, mnemonics, and clinical pearls
                </p>

                {/* Persistent Year Banner */}
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
                                        {examSource} {selectedYear} · {qbankStats?.by_year?.find((b: any) => String(b.year) === selectedYear)?.count ?? '—'} Questions
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                                <button
                                    type="button"
                                    onClick={() => {
                                        analytics.mockTestStart(selectedExam, selectedYear ? Number(selectedYear) : null, 'banner');
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
                                        analytics.mockTestStart(selectedExam, selectedYear ? Number(selectedYear) : null, 'simulator');
                                        const slug = String(selectedExam).replace('_', '-');
                                        if (slug === 'neet-pg') {
                                            router.push(`/questions/neet-pg/practice?year=${selectedYear}`);
                                        } else {
                                            router.push(`/questions/practice?year=${selectedYear}&exam=${selectedExam}`);
                                        }
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

                {/* Filters Panel */}
                <Card className="border-border/80 bg-card/85 shadow-sm backdrop-blur-xs relative overflow-visible">
                    <div className="absolute top-0 right-0 h-32 w-32 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
                    <CardContent className="p-3 space-y-2.5">
                        {qbankStats && (
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-2.5 border-b border-border/40 pb-2">
                                <div className="space-y-1 text-left">
                                    {/* Hero title — deliberately NOT a duplicate of the page heading
                                        ("Question Bank") at the top of the page. Surface progress
                                        framing instead so users see momentum at a glance. */}
                                    <div className="flex items-center gap-3">
                                        <h2 className="text-lg font-bold text-foreground">
                                            🎯 Your {examSource} Prep
                                        </h2>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        {qbankStats.total} high-yield clinical MCQs and PYQs across every {examSource} subject.
                                    </p>
                                </div>

                                <div className="flex flex-1 max-w-md items-center gap-3">
                                    <div className="flex-1 space-y-0.5 min-w-0">
                                        <div className="flex justify-between text-xs font-semibold gap-2">
                                            <span className="truncate">Overall Progress</span>
                                            <span className="text-primary font-bold shrink-0">
                                                {qbankStats.total_solved} / {qbankStats.total} ({Math.round(qbankStats.total_solved / (qbankStats.total || 1) * 100)}%)
                                            </span>
                                        </div>
                                        <Progress value={Math.round(qbankStats.total_solved / (qbankStats.total || 1) * 100)} className="h-1.5" />
                                    </div>
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
                                <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-1.5 max-h-65 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                                    {(qbankStats.by_year || []).map((item: any) => {
                                        const solvedPct = Math.round(item.solved / (item.count || 1) * 100);
                                        const isSelected = selectedYear === String(item.year);
                                        const isComplete = item.count > 0 && item.solved >= item.count;
                                        return (
                                            <div key={item.year} className="relative group">
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        analytics.pyqYearOpen(selectedExam, item.year, item.solved || 0, item.count || 0);
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

                        <div className="flex flex-col gap-2 pt-1">
                            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2">
                                <div className="relative w-full sm:max-w-xs flex-1 min-w-0">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                                    <Input className="pl-10 h-8 text-[11px] w-full" placeholder="Search questions..."
                                        value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleSearch()} />
                                </div>
                                <div className="flex items-center gap-1 bg-muted/40 p-1.5 rounded-xl border border-border/60 shrink-0">
                                    <button
                                        type="button"
                                        onClick={() => setStudyMode('practice')}
                                        className={`px-4 py-2 text-xs font-bold rounded-lg transition-all ${studyMode === 'practice' ? 'bg-primary text-primary-foreground shadow-md ring-1 ring-primary/40' : 'text-muted-foreground hover:bg-muted/80 hover:text-foreground'}`}
                                    >
                                        <Play className="w-3.5 h-3.5 inline -mt-0.5 mr-1" />
                                        Practice Mode
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setStudyMode('exam')}
                                        className={`px-4 py-2 text-xs font-bold rounded-lg transition-all ${studyMode === 'exam' ? 'bg-indigo-600 text-white shadow-md ring-1 ring-indigo-400/60' : 'text-muted-foreground hover:bg-muted/80 hover:text-foreground'}`}
                                    >
                                        <Target className="w-3.5 h-3.5 inline -mt-0.5 mr-1" />
                                        Exam Mode
                                    </button>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_140px_120px_120px] gap-2 lg:gap-2 items-center">
                                <select
                                    aria-label="Filter by subject"
                                    className="input-field h-9 text-[11px] px-3 w-full min-w-0 truncate"
                                    value={selectedSubject}
                                    onChange={e => setSelectedSubject(e.target.value)}
                                >
                                    <option value="">All Subjects</option>
                                    {(() => {
                                        // Three display-side improvements over the raw API payload:
                                        //   1. The loader's "Expert Curated" Subject row exists in
                                        //      duplicate (id=291 with 1285 questions, id=309 with 541
                                        //      questions) because the management command to merge
                                        //      them has not been run in production. Collapse display
                                        //      duplicates by name, summing the question_count so users
                                        //      see ONE "Expert Curated (1826)" entry instead of two
                                        //      redundant rows.
                                        //   2. INI-CET rows that own 0 questions are not useful as
                                        //      filter chips for the CMS bank — selecting them would
                                        //      always return an empty result. Hide them.
                                        //   3. The "(INI-CET)" suffix on rows that actually own
                                        //      questions would confuse a CMS student, so we hide them
                                        //      too — the dedicated INI-CET player at
                                        //      /questions/inicet/practice renders its own subject
                                        //      filter from the same source.
                                        const byName = new Map<string, { id: number; name: string; count: number }>();
                                        for (const s of subjects) {
                                            const count = s.question_count || 0;
                                            // Skip non-CMS tracks entirely on the CMS bank.
                                            if (s.name.includes('(INI-CET)')) continue;
                                            if (s.name.includes('(NEET PG)')) continue;
                                            if (s.name.includes('(USMLE)')) continue;
                                            if (s.name.includes('(FMGE)')) continue;
                                            if (count <= 0) continue;
                                            const displayName = s.name === 'Imported' ? 'Expert Curated' : s.name;
                                            const existing = byName.get(displayName);
                                            if (!existing) {
                                                byName.set(displayName, { id: s.id, name: displayName, count });
                                            } else {
                                                existing.count += count;
                                            }
                                        }
                                        // Stable sort: real medical subjects first (alphabetical),
                                        // "Expert Curated" pinned last so the brand-new / practice pool
                                        // is clearly opt-in.
                                        return Array.from(byName.values())
                                            .sort((a, b) => {
                                                if (a.name === 'Expert Curated') return 1;
                                                if (b.name === 'Expert Curated') return -1;
                                                return a.name.localeCompare(b.name);
                                            })
                                            .map(s => (
                                                <option key={s.id} value={s.id}>
                                                    {s.name} ({s.count})
                                                </option>
                                            ));
                                    })()}
                                </select>
                                <select
                                    aria-label="Filter by difficulty"
                                    className="input-field h-9 text-[11px] px-3 w-full min-w-0"
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
                                    className="input-field h-9 text-[11px] px-3 w-full min-w-0"
                                    value={selectedYear}
                                    onChange={e => setSelectedYear(e.target.value)}
                                >
                                    <option value="">Year</option>
                                    {years.map(y => (
                                        <option key={y} value={y}>{y === 0 ? 'Expert Curated' : y}</option>
                                    ))}
                                </select>
                                <Button
                                    variant="neon"
                                    onClick={handleSearch}
                                    size="sm"
                                    className="h-9 px-3 w-full group"
                                >
                                    <Filter className="w-3.5 h-3.5 mr-1 group-hover:rotate-12 transition-transform" /> Filter
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Content */}
                <div className={`qbank-grid flex-1 min-h-0 ${selectedQuestion ? 'has-selected' : ''} ${studyMode === 'exam' ? 'qbank-mode-exam' : ''}`}>
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
                                    {questions.map(q => {
                                        // Freemium: backend annotates each row with `is_showcase`.
                                        // For non-showcase rows we render a blurred overlay + lock
                                        // badge so free users see the full catalog (better conversion
                                        // signal — "2,277 questions waiting") but cannot start the
                                        // question without subscribing. The backend still 403s on
                                        // /api/questions/{id}/ retrieve for free non-showcase users
                                        // as a hard server-side gate.
                                        const isLockedForFreeUser = !isPremium && !q.is_showcase;
                                        return (
                                        <Card key={q.id} className={`relative cursor-pointer border-border/80 bg-card/90 p-3 md:p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md ${selectedQuestion === q.id ? 'border-primary/70 ring-2 ring-inset ring-primary/60 shadow-md' : ''} ${isLockedForFreeUser ? 'overflow-hidden' : ''}`}
                                            onClick={() => {
                                                if (isLockedForFreeUser) {
                                                    showPaywall('PYQ answers');
                                                    return;
                                                }
                                                openQuestion(q.id);
                                            }}>
                                            <div className="flex justify-between items-start mb-2">
                                                <Badge variant="secondary" className="text-xs">
                                                    {/* Backend uses year=0 as a sentinel for "Expert Curated"
                                                        (no PYQ year). Hide it so we don't render "0 • Subject".
                                                        The "Imported" Subject row is renamed to "Expert Curated"
                                                        in the UI so users never see the raw loader literal. */}
                                                    {q.year && q.year > 0 ? (
                                                        <>{q.year} &bull; {q.subject_name}</>
                                                    ) : (
                                                        <>Expert Curated</>
                                                    )}
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
                                            <p className="text-sm leading-relaxed text-foreground line-clamp-3 md:line-clamp-none">{(() => {
                                                // Decode mojibake (e.g. "iÃ©iÃiÃ©") before display so list
                                                // cards on the bank show readable text. Falls back to a
                                                // generic placeholder when the row is still unreadable
                                                // after repair — matches the Similar-PYQs sidebar guard.
                                                const cleaned = decodeMojiB(sanitizeQuestionText(q.question_text));
                                                if (isLikelyGarbled(cleaned)) {
                                                    return <em className="italic text-muted-foreground">Question #{q.id}{q.year ? ` (${q.year})` : ''}</em>;
                                                }
                                                const preview = stripMarkdown(cleaned).slice(0, 150);
                                                return preview + (stripMarkdown(cleaned).length > 150 ? '...' : '');
                                            })()}</p>
                                            <div className="mt-2 flex flex-wrap gap-1.5">
                                                {q.topic_name ? (
                                                    <Badge variant="outline" className="text-xs bg-muted text-foreground border-border/80">{q.topic_name}</Badge>
                                                ) : (
                                                    // Skip the redundant "General <subject>" sub-badge when the
                                                    // top badge already conveys all the subject info. The legacy
                                                    // check only compared to the literal string 'Imported', but
                                                    // the serializer now rewrites that to 'Expert Curated' on the
                                                    // way out (see backend/questions/serializers.py), which made
                                                    // the guard useless and surfaced "General Expert Curated"
                                                    // under every Expert-Curated card.
                                                    q.subject_name &&
                                                    q.subject_name !== 'Imported' &&
                                                    q.subject_name !== 'Expert Curated' &&
                                                    q.year && q.year > 0 ? (
                                                        <Badge variant="outline" className="text-xs bg-muted text-muted-foreground border-border/80 italic">
                                                            {`General ${q.subject_name || 'Medicine'}`}
                                                        </Badge>
                                                    ) : null
                                                )}
                                                {q.year && q.year > 0 ? (
                                                    <Badge variant="outline" className="text-[10px] bg-muted text-foreground border-border/80">PYQ {q.year}</Badge>
                                                ) : null}
                                                {q.concept_tags?.includes('high_yield') && (
                                                    <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-[10px]">🔥 High Yield</Badge>
                                                )}
                                            </div>
                                            {isLockedForFreeUser && (
                                                <div
                                                    className="pointer-events-none absolute inset-0 flex items-center justify-center bg-background/60 backdrop-blur-[2px]"
                                                    aria-hidden="true"
                                                >
                                                    <div className="flex flex-col items-center gap-1 rounded-xl bg-card/95 px-4 py-3 shadow-lg ring-1 ring-amber-500/40">
                                                        <Lock className="w-5 h-5 text-amber-400" />
                                                        <span className="text-xs font-semibold text-foreground">Premium Question</span>
                                                        <LockedBadge size="sm" />
                                                    </div>
                                                </div>
                                            )}
                                        </Card>
                                        );
                                    })}
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

                                <div className="flex flex-wrap gap-2 text-[10px]">
                                    <LegendChip color="bg-emerald-500" label="Correct" />
                                    <LegendChip color="bg-red-500" label="Wrong" />
                                    <LegendChip color="bg-amber-400" label="Current" />
                                    <LegendChip color="bg-muted-foreground/40" label="Unseen" />
                                </div>

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
                            <div className="animate-fadeInUp space-y-3 px-1 py-0.5">
                                <div className="glass-card rounded-2xl border border-primary/40 shadow-[0_18px_40px_rgba(14,116,144,0.16)]">
                                    <div className="px-4 py-2 flex flex-wrap items-center gap-1.5 border-b border-border bg-slate-50 dark:bg-slate-800/40">
                                        {detail.year ? (
                                            <Badge variant="secondary" className="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 pointer-events-none">PYQ {String(detail.year)}</Badge>
                                        ) : (
                                            <Badge variant="secondary" className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 pointer-events-none">Expert Curated</Badge>
                                        )}
                                        {/* Subject badge: only render when the value gives the user new
                                            information. Skip when the API has already returned
                                            "Expert Curated" (which the serializer renames from "Imported"
                                            to keep the loader literal off the UI) — otherwise the detail
                                            header shows "Expert Curated" twice. Also skip empty / falsy
                                            values defensively. */}
                                        {detail.subject_name &&
                                         String(detail.subject_name).trim() !== '' &&
                                         String(detail.subject_name) !== 'Imported' &&
                                         String(detail.subject_name) !== 'Expert Curated' ? (
                                            <Badge variant="secondary" className="pointer-events-none">
                                                {String(detail.subject_name)}
                                            </Badge>
                                        ) : null}
                                        {detail.topic_name && <Badge variant="outline" className="pointer-events-none">{String(detail.topic_name)}</Badge>}
                                        {detail.difficulty && <Badge variant="outline" className="pointer-events-none capitalize">{detail.difficulty}</Badge>}
                                        {detail.is_verified_by_admin && (
                                            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 pointer-events-none">
                                                ✔ Verified by Admin
                                            </Badge>
                                        )}
                                    </div>

                                    <div className="p-4">
                                        {/* Resume banner — appears only when the student has a prior attempt
                                            for this question and hasn't picked a fresh option this session.
                                            Replaces the previous behaviour of silently flipping showAnswer=true
                                            on open, which was leaking the admin's explanation image (and the
                                            correct-answer card) before the student even read the stem. */}
                                        {detail.user_selected_answer && !showAnswer && (
                                            <div className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50/80 dark:bg-amber-950/30 dark:border-amber-800/60 px-3 py-1.5 text-xs text-amber-900 dark:text-amber-200">
                                                <span>
                                                    You answered{' '}
                                                    <span className="font-bold">
                                                        {detail.user_selected_answer}
                                                    </span>{' '}
                                                    last time
                                                    {detail.user_is_correct === false && ' (incorrect)'}
                                                    {detail.user_is_correct === true && ' (correct)'} — re-attempt
                                                    to see the explanation.
                                                </span>
                                                <button
                                                    type="button"
                                                    onClick={() => setShowAnswer(true)}
                                                    className="shrink-0 px-2.5 py-1 rounded-md bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700"
                                                >
                                                    Show answer
                                                </button>
                                            </div>
                                        )}

                                        {/* STEM + IMAGE LAYOUT
                                            When the question has attached images we render a
                                            60/40 split on desktop: stem + options on the left
                                            (60%) and a large sticky image pane on the right
                                            (40%) so the image takes a good amount of screen
                                            while solving. On mobile the image pane sits below
                                            the stem (stacked) so vertical scroll works. The
                                            options block remains full-width below this row.

                                            Bug fix 2026-08-01: prefer `detail.stem_images`
                                            (the backend's role-filtered list) so explanation
                                            images uploaded by the admin from the explanation
                                            editor stop leaking into the stem pane before the
                                            student attempts the question. We fall back to
                                            `detail.images` filtered by role for legacy rows
                                            that pre-date the `stem_images` field, so the fix
                                            works for both new and existing questions. The
                                            FULL `detail.images` array is still passed into
                                            `resolveImageTokensForMarkdown` below so the
                                            `[[img:N]]` tokens inside the explanation text
                                            continue to resolve. */}
                                        {((Array.isArray(detail.stem_images) && detail.stem_images.length > 0)
                                            || (Array.isArray(detail.images) && detail.images.some((img: any) => img.role !== 'explanation'))) ? (
                                            <div className="qbank-solve-layout flex flex-col lg:flex-row gap-4 mb-3">
                                                <div className="qbank-stem-pane lg:basis-3/5 lg:min-w-0">
                                                    <div className="text-base font-medium leading-relaxed">
                                                        <FormattedText
                                                            text={resolveImageTokensForMarkdown(sanitizeQuestionText(detail.question_text), detail.images)}
                                                        />
                                                    </div>
                                                </div>
                                                <div className="qbank-image-pane lg:basis-2/5 lg:min-w-0 lg:self-start lg:sticky lg:top-4">
                                                    <div className="grid grid-cols-1 gap-2">
                                                        {(
                                                            Array.isArray(detail.stem_images) && detail.stem_images.length > 0
                                                                ? detail.stem_images
                                                                : detail.images.filter((img: any) => img.role !== 'explanation')
                                                        ).map((img: any, idx: number) => {
                                                            const imgSrc = img.url || img.file_url;
                                                            return imgSrc ? (
                                                                <button
                                                                    key={img.id}
                                                                    type="button"
                                                                    onClick={() => setViewImageIdx(idx)}
                                                                    className="block w-full text-left rounded-xl overflow-hidden border border-border/60 hover:border-primary/60 transition-colors cursor-zoom-in bg-muted/20"
                                                                >
                                                                    <img src={imgSrc} alt={img.caption || 'Question image'}
                                                                        className="w-full h-auto max-h-[55vh] object-contain bg-muted/30" loading="lazy" />
                                                                    {img.caption && <p className="text-[10px] text-muted-foreground p-1.5">{img.caption}</p>}
                                                                </button>
                                                            ) : null;
                                                        })}
                                                        {/* Show a hint chip when the question declares images but none of them have a resolvable URL.
                                                           Avoids the confusing "broken-image icon + alt text" that previously rendered for image-questions
                                                           whose media files are still missing from /media (e.g. NEET PG recall imports). */}
                                                        {(
                                                            Array.isArray(detail.stem_images) && detail.stem_images.length > 0
                                                                ? detail.stem_images
                                                                : detail.images.filter((img: any) => img.role !== 'explanation')
                                                        ).every((img: any) => !(img.url || img.file_url)) && (
                                                            <div className="rounded-xl border border-dashed border-border/60 bg-muted/20 p-4 text-center">
                                                                <p className="text-xs text-muted-foreground">
                                                                    🖼️ Image unavailable — see question text below for the full stem.
                                                                </p>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-base font-medium leading-relaxed mb-3">
                                                <FormattedText
                                                    text={resolveImageTokensForMarkdown(sanitizeQuestionText(detail.question_text), detail.images)}
                                                />
                                            </div>
                                        )}

                                        <div className="space-y-2 mb-3">
                                            {['A', 'B', 'C', 'D'].map(opt => {
                                                const key = `option_${opt.toLowerCase()}`;
                                                const rawOption = detail[key] || detail[`option_${opt}`];
                                                const optionText = sanitizeOptionText(rawOption);
                                                if (!optionText) return null;
                                                const isCorrect = detail.correct_answer === opt;
                                                const isSelected = selectedAnswer === opt;
                                                const isWrong = isSelected && !isCorrect && showAnswer;

                                                return (
                                                    <div key={opt}
                                                        className={`flex items-start gap-3 p-3 rounded-xl border transition-all cursor-pointer ${
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
                                                        <div className="flex-1 min-w-0 text-sm font-medium wrap-break-word whitespace-pre-wrap leading-relaxed">{cleanOptionText(String(optionText))}</div>
                                                        {showAnswer && isCorrect && <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 shrink-0 self-center">✓ Correct</span>}
                                                        {isWrong && <span className="text-xs font-bold text-red-600 dark:text-red-400 shrink-0 self-center">✗ Wrong</span>}
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

                                {showAnswer && (
                                    <div className="space-y-3 animate-fadeInUp">
                                        <Card className="border-emerald-300 bg-emerald-50/80 dark:bg-emerald-950/30 dark:border-emerald-800/60">
                                            <CardContent className="p-4 space-y-2">
                                                <h4 className="text-sm font-bold text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
                                                    <CheckCircle className="w-4 h-4" /> Correct Answer: {detail.correct_answer}
                                                </h4>
                                                {detail.explanation && (
                                                    <div className="rounded-lg bg-white/80 dark:bg-slate-900/40 p-3 text-sm leading-relaxed text-foreground">
                                                        <FormattedText text={resolveImageTokensForMarkdown(extractAnalysisFromJson(String(detail.explanation)), detail.images)} />
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>

                                        {detail?.video_url && detail?.video_status === 'completed' && (
                                            <div className="explanation-card explanation-card-indigo animate-fadeInUp mt-4 mb-4 overflow-hidden">
                                                <div className="p-1">
                                                    <h4 className="explanation-card-title indigo px-4 py-2"><Play className="w-4 h-4" /> AI Video Explanation</h4>
                                                    <PremiumVideoPlayer
                                                        src={detail.video_url}
                                                        subtitlesSrc={detail.video_subtitles_url}
                                                        poster={detail.video_thumbnail}
                                                        className="w-full max-h-125"
                                                    />
                                                </div>
                                            </div>
                                        )}

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

                                        {!aiExplanation && !aiLoading && !tokenError && (
                                            <button onClick={() => {
                                                if (typeof window !== 'undefined' && (window as any).gtag) {
                                                    (window as any).gtag('event', 'ai_explain_request', { exam_slug: selectedExam });
                                                }
                                                fetchAiExplanation();
                                            }}
                                                className="w-full rounded-2xl border border-blue-200 bg-blue-50/50 dark:bg-blue-900/10 dark:border-blue-800/50 p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:bg-blue-50 dark:hover:bg-blue-900/20 mt-1">
                                                <Brain className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                                                <div className="text-left">
                                                    <span className="text-sm font-bold block text-blue-700 dark:text-blue-300">Generate AI Analysis</span>
                                                    <span className="text-xs text-muted-foreground">Click to get mnemonics, explanations, exam tips & more</span>
                                                </div>
                                            </button>
                                        )}

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

                                        {detail.book_name && !aiExplanation?.textbook_reference?.book && (
                                            <div className="glass-card p-4 flex items-start gap-3">
                                                <Bookmark className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#8b5cf6' }} />
                                                <div>
                                                    <h5 className="text-xs font-bold mb-0.5" style={{ color: '#8b5cf6' }}>📚 Textbook Reference</h5>
                                                    <p className="text-sm font-semibold">{String(detail.book_name)} {detail.chapter ? `— Ch: ${String(detail.chapter)}` : ''} {detail.page_number ? `(pg ${String(detail.page_number)})` : ''}</p>
                                                </div>
                                            </div>
                                        )}

                                        {detail.similar && (detail.similar as unknown[]).length > 0 && (
                                            <div className="glass-card p-4">
                                                <h5 className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--accent-primary)' }}>
                                                    <Target className="w-3.5 h-3.5" /> Similar PYQs from Database
                                                </h5>
                                                <div className="space-y-1.5">
                                                    {(detail.similar as Array<{ id: number; year: number; question_text: string }>).map((sq) => {
                                                        // Defence-in-depth: strip double-encoded UTF-8 mojibake
                                                        // (e.g. iÃ©iÃiÃ©) before rendering, and fall back to a
                                                        // generic "Question #N" placeholder when the text is
                                                        // still unreadable after cleanup. Mirrors the
                                                        // NeetPgPlayer guard (line ~977) so the same DB
                                                        // content renders cleanly across both surfaces.
                                                        const cleaned = decodeMojiB(sq.question_text || '');
                                                        const garbled = isLikelyGarbled(cleaned);
                                                        return (
                                                        <div key={sq.id} className="flex gap-2 items-start cursor-pointer p-2 rounded-lg transition-colors hover:bg-[rgba(6,182,212,0.05)]"
                                                            onClick={() => { openQuestion(sq.id); }}>
                                                            {sq.year ? (
                                                                <span className="text-xs font-bold px-1.5 py-0.5 rounded whitespace-nowrap shrink-0" style={{ background: 'rgba(6,182,212,0.1)', color: 'var(--accent-primary)' }}>PYQ {sq.year}</span>
                                                            ) : (
                                                                <span className="text-xs font-bold px-1.5 py-0.5 rounded whitespace-nowrap shrink-0" style={{ background: 'rgba(245,158,11,0.15)', color: '#b45309' }}>Expert Curated</span>
                                                            )}
                                                            <span className="text-xs line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
                                                                {garbled
                                                                    ? <em className="italic">Question #{sq.id}{sq.year ? ` (${sq.year})` : ''}</em>
                                                                    : cleaned}
                                                            </span>
                                                        </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}

                                        {aiLoading && (
                                            <div className="glass-card p-5 flex items-center gap-4 animate-pulse" style={{ borderColor: 'rgba(6,182,212,0.3)' }}>
                                                <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                                                <div>
                                                    <span className="text-sm font-bold transition-all duration-500" style={{ color: 'var(--accent-primary)' }}>{loadingMessages.current[loadingMsgIndex]}</span>
                                                    <span className="text-xs block mt-1" style={{ color: 'var(--text-secondary)' }}>Generating mnemonics, topic knowledge, exam tips & more</span>
                                                </div>
                                            </div>
                                        )}

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

                                        {aiExplanation && !aiLoading && (
                                            <div className="space-y-3">
                                                <div className="flex items-center gap-2 px-1 pt-1 opacity-80">
                                                    <Brain className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                                    <span className="font-bold text-xs tracking-wider text-blue-600 dark:text-blue-400 uppercase">AI-Powered Deep Analysis</span>
                                                    <div className="flex-1 h-px bg-border ml-2"></div>
                                                </div>

                                                {/* BUG FIX (2026-07-26): defence-in-depth fallback. If the
                                                    backend returns the ExplainQuestionView shape
                                                    (`{analysis, context, is_correct}`) instead of the
                                                    ExplainAfterAnswerView rich shape, every rich
                                                    panel collapses — the user sees only the header
                                                    above with nothing under it. Render `analysis`
                                                    markdown so the user always sees content. Only
                                                    fires when no rich fields are present so it
                                                    doesn't duplicate a normal rich response. */}
                                                {aiExplanation.analysis && !(
                                                    aiExplanation.mnemonic ||
                                                    aiExplanation.why_correct ||
                                                    aiExplanation.core_concept ||
                                                    aiExplanation.topic_deep_dive ||
                                                    aiExplanation.clinical_pearl ||
                                                    aiExplanation.exam_tip
                                                ) && (
                                                    <div className="glass-card p-4 space-y-2">
                                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1.5 text-blue-700 dark:text-blue-400">
                                                            <Brain className="w-3.5 h-3.5" /> AI Analysis
                                                        </h5>
                                                        <div className="text-sm leading-relaxed text-foreground prose prose-sm max-w-none">
                                                            <FormattedText text={cleanAiText(aiExplanation.analysis)} />
                                                        </div>
                                                    </div>
                                                )}

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
                                                                {aiExplanation.topic_deep_dive && (
                                                                    <div className="explanation-card explanation-card-indigo">
                                                                        <div className="explanation-card-accent indigo"></div>
                                                                        <div className="p-4 pl-5">
                                                                            <h4 className="explanation-card-title indigo"><BookOpen className="w-4 h-4" /> 📖 Topic Deep Dive — Learn the Bigger Picture</h4>
                                                                            <FormattedText text={cleanAiText(aiExplanation.topic_deep_dive)} />
                                                                        </div>
                                                                    </div>
                                                                )}

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

                                                                {aiExplanation.quick_revision && (
                                                                    <div className="quick-revision-card">
                                                                        <div className="absolute top-0 left-0 w-full h-1" style={{ background: 'var(--gradient-primary)' }}></div>
                                                                        <h5 className="text-xs font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1.5" style={{ color: 'var(--accent-primary)' }}>
                                                                            <Lightbulb className="w-3.5 h-3.5" /> 📝 Quick Revision — Read Before Exam
                                                                        </h5>
                                                                        <FormattedText text={cleanAiText(aiExplanation.quick_revision)} />
                                                                    </div>
                                                                )}

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

                                <DiscussionThread questionId={detail.id} />

                                <div className="flex flex-wrap items-center gap-3 px-2 py-2 text-[10px] text-muted-foreground">
                                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">A-D</kbd> answer</span>
                                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">N</kbd> next</span>
                                    <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">P</kbd> prev</span>
                                </div>
                            </div>
                        ) : (
                            <Card className="p-8 md:p-16 text-center min-h-[260px] md:h-125 flex flex-col items-center justify-center">
                                <BookOpen className="w-12 h-12 md:w-16 md:h-16 mx-auto mb-4 md:mb-6 text-muted-foreground/30" />
                                <p className="text-lg font-medium mb-2 text-foreground">Select a Question</p>
                                <p className="text-sm text-muted-foreground max-w-md mx-auto">Click any question from the bank to practice and review detailed AI-powered explanations.</p>
                            </Card>
                        )}
                    </div>
                </div>
            </div>

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

            {yearModalOpen && modalYear && (
                <div className="fixed inset-0 z-50 flex items-start sm:items-center justify-center bg-black/60 backdrop-blur-xs p-4 pt-16 sm:pt-4 overflow-y-auto animate-fadeIn">
                    <Card className="max-w-md w-full border-border/80 bg-card shadow-2xl relative overflow-hidden animate-fadeInUp">
                        <div className="absolute top-0 right-0 h-32 w-32 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
                        <CardContent className="p-6 space-y-6">
                            <div className="text-center space-y-2">
                                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-2 text-primary">
                                    <Target className="w-6 h-6 animate-pulse" />
                                </div>
                                <h3 className="text-xl font-bold text-foreground">{examSource} {modalYear} PYQs</h3>
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
                                <button
                                    onClick={() => {
                                        const slug = String(selectedExam).replace('_', '-');
                                        if (slug === 'neet-pg') {
                                            router.push(`/questions/neet-pg/practice?year=${modalYear}`);
                                        } else if (slug === 'ini-cet' || slug === 'ini_cet') {
                                            router.push(`/questions/inicet/practice?year=${modalYear}`);
                                        } else {
                                            router.push(`/questions/practice?year=${modalYear}&exam=${selectedExam}`);
                                        }
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
                                        <span className="text-[11px] text-muted-foreground mt-0.5 block">120 questions, 120-minute time limit, negative marking (-0.33). Experience the real {examSource} exam HUD.</span>
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

            {/* Image viewer modal — opens when the user clicks a thumbnail
                in the image carousel above. Reuses the same ImageViewer
                component the standalone NEET-PG / INI-CET players use, so
                pinch-zoom, side-by-side, and fullscreen all work. Previously
                the carousel used <a target="_blank"> which would leak
                potentially-short-lived presigned S3 URLs into a new tab. */}
            {viewImageIdx !== null && Array.isArray(detail?.stem_images) && detail.stem_images.length > 0 && (
                <ImageViewer
                    open
                    onClose={() => setViewImageIdx(null)}
                    startIndex={viewImageIdx}
                    images={(detail.stem_images as ViewerImage[]).map((img: ViewerImage | any) => ({
                        id: img.id,
                        file_url: img.file_url || img.url || null,
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
                />
            )}
        </div>
    );
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
    // Bug 2026-08-01 admin-uploaded explanation image shown next to
    // the question stem before any attempt. Added to mirror the
    // backend's role-filtered `stem_images` field so the typecheck
    // stays clean.
    stem_images?: QuestionImage[];
    // Freemium (UX update 2026-08-04): backend annotates each list row
    // with `is_showcase=true` when it is in accounts.FreeShowcaseQuestion.
    // Free users see ALL questions in the list, but rows where this is
    // false render a blurred lock overlay and trigger the paywall on click.
    is_showcase?: boolean;
}

interface QuestionImage {
    id: number;
    url?: string | null;
    file_url?: string | null;
    role?: 'primary' | 'option' | 'illustration' | 'explanation';
    caption?: string | null;
    page_number?: number;
    image_index_in_page?: number;
    modality?: string;
}

interface Subject {
    id: number;
    name: string;
    code: string;
    question_count: number;
}