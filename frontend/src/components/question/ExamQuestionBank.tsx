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
 * `defaultYear`, `initialSubject`, `initialQueryId`, `initialBookmarkOnly`
 * pre-seed the initial filter state from URL params so links like
 * `/questions/neet-pg/practice?year=2025&q=12345` or
 * `/questions?exam=cms&subject=medicine` open the right view immediately.
 *
 * Settings > Customise (useQuestionBankPreferences): the mode the bank opens
 * in, and the tools shown with a question (`shows(...)`). The answer flow
 * and "Flag Issue" are never hidden; the defaults render while the
 * preferences load.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { questionsAPI, aiAPI, testsAPI, extractApiErrorMessage } from '@/lib/api';
import {
    BookOpen, Search, Filter, Bookmark, ChevronLeft, ChevronRight,
    ChevronDown, Loader2, Brain, Sparkles, CheckCircle, ArrowRight,
    Flag, Target, Zap, GraduationCap, Lightbulb, Play, Calendar, ListChecks,
    Lock, SlidersHorizontal,
} from 'lucide-react';
import DiscussionThread from '@/components/DiscussionThread';
import { useQuestionBankPreferences } from '@/components/customize/useQuestionBankPreferences';
import type { StudyMode } from '@/lib/preferences';
import StudentCitations from '@/components/evidence/StudentCitations';
import { ExamTrackProvider, useExamTrack } from '@/components/ExamTrackProvider';
import ImageViewer, { type ViewerImage } from '@/components/image/ImageViewer';
import FigureImage from '@/components/question/FigureImage';
import { figureSrc, sidePaneFigures } from '@/lib/figureSrc';
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
import {
    aiFailureNotice, answerLetter, attemptVerdict, classifyAiFailure, collectPages, detailFailureKind, errorStatus,
    fetchPageScreenshot, isPremiumUser, normaliseTextbookReferences, normaliseYears, pickExplanation, resolveSubjectParam,
    retryAfterSeconds, summariseBankStats, upgradeRequiredFeature, type SubjectOption, type TextbookReference,
} from '@/components/question/practiceData';

/** Bank metadata loaded next to the list (filters + stats strip). */
type MetaPart = 'subjects' | 'years' | 'stats';
const META_PARTS: MetaPart[] = ['subjects', 'years', 'stats'];
const NO_META_FAILED: Record<MetaPart, boolean> = { subjects: false, years: false, stats: false };

// The global `.input-field` rule is unlayered CSS (10px vertical padding,
// 14px font), so it beat these selects' Tailwind utilities and clipped
// their text inside the 36px height. Same look, from theme tokens.
const FILTER_SELECT_CLS =
    'h-9 w-full min-w-0 rounded-[var(--radius)] border border-input bg-card px-3 text-[11px] text-foreground ' +
    'transition-colors focus:outline-none focus:border-ring focus:ring-[3px] focus:ring-ring/20';

/**
 * Every subject row. The endpoint used to page at 20 rows (clipping
 * 'Expert Curated', alphabetically last, into page 2), so follow `next`;
 * a bare array (unpaginated) ends the loop after one request. The hard cap
 * protects against a backend that returns an unbounded `next` pointer.
 */
async function fetchAllSubjects(): Promise<Subject[]> {
    const collected: Subject[] = [];
    let page = 1;
    while (page <= 10) {
        const res = await questionsAPI.getSubjects({ page, page_size: 100 });
        const results = res.data?.results || res.data || [];
        if (!Array.isArray(results) || results.length === 0) break;
        collected.push(...results);
        if (!res.data?.next) break;
        page += 1;
    }
    return collected;
}

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
    /**
     * Optional subject to pre-select from `?subject=` — an id, name, code or
     * public-page slug (`medicine`, `obg`, `General Medicine`); resolved
     * against the subject list once it loads.
     */
    initialSubject?: string | null;
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
    initialSubject = null,
    initialQueryId = null,
    initialBookmarkOnly = false,
}: ExamQuestionBankProps) {
    return (
        <ExamTrackProvider>
            <ExamQuestionBankInner
                examType={examType}
                examSource={examSource}
                defaultYear={defaultYear}
                initialSubject={initialSubject}
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
    initialSubject,
    initialQueryId,
    initialBookmarkOnly,
}: ExamQuestionBankProps) {
    const { isAuthenticated, loading: authLoading, user } = useAuth();
    const { activeTrack } = useExamTrack();
    const { setContextQuestionId } = useDock();
    const { show: showPaywall } = usePaywall();
    // Freemium: a user is "premium" if they have an active subscription OR
    // are admin/staff — mirrors backend `accounts.utils.is_premium` (the
    // same helper the practice pages use).
    const isPremium = isPremiumUser(user);
    // Broadcast whether a question is currently being solved so the
    // SidebarAutoHide controller can keep the sidebar collapsed for the
    // entire /questions session while a question is open.
    const { setQuestionFocused } = useQuestionFocus();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    // `examType` is the source of truth for which bank we're showing. We
    // intentionally do NOT honour `?exam=` overrides here — the route URL
    // is authoritative. (The standalone `/questions` page has its own
    // override behaviour; see `QuestionsBankSlim` below.)
    const [selectedExam, setSelectedExam] = useState<string>(examType);
    // /questions?exam=… keeps this component mounted when only the query
    // changes, so follow the prop instead of keeping the first exam.
    if (examType !== selectedExam) {
        setSelectedExam(examType);
    }

    const [questions, setQuestions] = useState<Question[]>([]);
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedSubject, setSelectedSubject] = useState('');
    const [selectedDifficulty, setSelectedDifficulty] = useState('');
    const [selectedYear, setSelectedYear] = useState<string>(defaultYear ?? '');
    const [years, setYears] = useState<number[]>([]);
    const [qbankStats, setQbankStats] = useState<any>(null);
    // Metadata parts whose request failed for good (after the one automatic
    // retry of a 429): the filter card offers a Retry for them.
    const [metaFailed, setMetaFailed] = useState<Record<MetaPart, boolean>>(NO_META_FAILED);
    // Years and stats belong to one exam: drop the previous exam's values
    // when /questions?exam=… switches banks without remounting.
    const metaScope = `${examType}|${examSource}`;
    const [metaScopeShown, setMetaScopeShown] = useState(metaScope);
    if (metaScope !== metaScopeShown) {
        setMetaScopeShown(metaScope);
        setYears([]);
        setQbankStats(null);
        setMetaFailed(NO_META_FAILED);
    }
    // The open question's detail request failed (premium question on the
    // free plan, removed question, network): shown instead of a skeleton.
    const [detailError, setDetailError] = useState<{ id: number; error: unknown } | null>(null);
    // The server refused to grade this question on the free plan (402).
    const [answerLockedId, setAnswerLockedId] = useState<number | null>(null);
    const [listError, setListError] = useState<string | null>(null);
    // Shown over the list skeleton while a rate-limited (429) list request
    // waits to retry.
    const [listNotice, setListNotice] = useState<string | null>(null);
    // 'failed' lets a `?subject=` link stop waiting for the subject list.
    const [subjectsStatus, setSubjectsStatus] = useState<'loading' | 'ok' | 'failed'>('loading');
    const [selectedQuestion, setSelectedQuestion] = useState<number | null>(
        initialQueryId ? Number(initialQueryId) : null,
    );
    const [questionDetail, setQuestionDetail] = useState<any>(null);
    const [showAnswer, setShowAnswer] = useState(false);
    const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
    // Practice (the answer shows on a pick) or exam (pick, then Submit). The
    // bank follows the student's default (Settings > Customise) until they
    // switch modes or answer here; practice while the preferences load.
    const questionBankPrefs = useQuestionBankPreferences();
    const { shows } = questionBankPrefs;
    const [studyModeChoice, setStudyMode] = useState<StudyMode | null>(null);
    const studyMode: StudyMode = studyModeChoice ?? questionBankPrefs.studyMode;
    // An answer keeps the mode it was given in (a late preference never flips it).
    const keepStudyMode = () => {
        if (studyModeChoice === null) setStudyMode(studyMode);
    };
    // isCorrect null: the question has no answer key, so the pick is ungraded.
    const [examAnswers, setExamAnswers] = useState<Record<number, { selected: string; isCorrect: boolean | null; answeredAt: number }>>({});
    const [examPaletteOpen, setExamPaletteOpen] = useState(true);
    const [page, setPage] = useState(1);
    const [totalCount, setTotalCount] = useState(0);
    const [aiExplanation, setAiExplanation] = useState<any>(null);
    const [aiLoading, setAiLoading] = useState(false);
    const [tokenError, setTokenError] = useState(false);
    // Short notice for a failed AI request (503 ai_unavailable, rate limit, …).
    const [aiError, setAiError] = useState<{ title: string; message: string } | null>(null);
    const [flagOpen, setFlagOpen] = useState(false);
    const [flagCategory, setFlagCategory] = useState('wrong_answer');
    const [flagComment, setFlagComment] = useState('');
    const [flagSubmitting, setFlagSubmitting] = useState(false);
    const [flagSuccess, setFlagSuccess] = useState(false);
    const [flagError, setFlagError] = useState<string | null>(null);
    const [showAiDeepDive, setShowAiDeepDive] = useState(false);
    const [bookmarkedOnly, setBookmarkedOnly] = useState<boolean>(initialBookmarkOnly ?? false);
    // `?year=` / `?bookmarked=1` can change while this component stays
    // mounted (a link to the same route with a new query). Re-seed the
    // filters when the URL-derived props change; the user's own filter
    // edits don't touch the URL, so they are left alone otherwise.
    const [seededYear, setSeededYear] = useState(defaultYear ?? '');
    if ((defaultYear ?? '') !== seededYear) {
        setSeededYear(defaultYear ?? '');
        setSelectedYear(defaultYear ?? '');
    }
    const [seededBookmarkOnly, setSeededBookmarkOnly] = useState(!!initialBookmarkOnly);
    if (!!initialBookmarkOnly !== seededBookmarkOnly) {
        setSeededBookmarkOnly(!!initialBookmarkOnly);
        setBookmarkedOnly(!!initialBookmarkOnly);
    }

    // The subject filter's options. Three display-side improvements over
    // the raw API payload:
    //   1. The loader's "Expert Curated" Subject row exists in duplicate
    //      (id=291 with 1285 questions, id=309 with 541 questions) because
    //      the management command to merge them has not been run in
    //      production. Collapse display duplicates by name, summing the
    //      question_count so users see ONE "Expert Curated (1826)" entry.
    //   2. Track-specific rows that own 0 questions are not useful as
    //      filter chips — selecting them would always return an empty
    //      result. Hide them.
    //   3. The "(INI-CET)" / "(NEET PG)" / … suffixed rows would confuse a
    //      CMS student, so they are hidden too — the dedicated INI-CET
    //      player at /questions/inicet/practice renders its own subject
    //      filter from the same source.
    // Real medical subjects come first (alphabetical); "Expert Curated" is
    // pinned last so the practice pool is clearly opt-in.
    const subjectOptions = useMemo<SubjectOption[]>(() => {
        const byName = new Map<string, SubjectOption>();
        for (const s of subjects) {
            const count = s.question_count || 0;
            if (s.name.includes('(INI-CET)')) continue;
            if (s.name.includes('(NEET PG)')) continue;
            if (s.name.includes('(USMLE)')) continue;
            if (s.name.includes('(FMGE)')) continue;
            if (count <= 0) continue;
            const displayName = s.name === 'Imported' ? 'Expert Curated' : s.name;
            const existing = byName.get(displayName);
            if (!existing) {
                byName.set(displayName, { id: s.id, name: displayName, code: s.code, count });
            } else {
                existing.count += count;
            }
        }
        return Array.from(byName.values()).sort((a, b) => {
            if (a.name === 'Expert Curated') return 1;
            if (b.name === 'Expert Curated') return -1;
            return a.name.localeCompare(b.name);
        });
    }, [subjects]);

    // `?subject=` (public pages link /questions?exam=<slug>&subject=<slug>)
    // becomes the subject filter once the subject list is known, and again
    // whenever the URL value changes. Until then the first list request
    // waits, so the unfiltered bank doesn't flash first.
    const subjectParam = (initialSubject ?? '').trim();
    const [appliedSubjectParam, setAppliedSubjectParam] = useState('');
    if (subjectParam !== appliedSubjectParam && (subjectsStatus !== 'loading' || !subjectParam)) {
        setAppliedSubjectParam(subjectParam);
        const subjectId = subjectParam ? resolveSubjectParam(subjectParam, subjectOptions) : null;
        setSelectedSubject(subjectId ? String(subjectId) : '');
    }
    const subjectPending = subjectParam !== appliedSubjectParam;
    // Image viewer modal state — null when closed. Clicking a thumbnail
    // in the question image carousel opens ImageViewer at the right index,
    // the same viewer the timed test player (/tests/[id]) uses.
    const [viewImageIdx, setViewImageIdx] = useState<number | null>(null);

    const [yearModalOpen, setYearModalOpen] = useState(false);
    const [modalYear, setModalYear] = useState<string | null>(null);
    const [startingSimulation, setStartingSimulation] = useState(false);
    const [simulationError, setSimulationError] = useState<string | null>(null);
    const [showStatsDetail, setShowStatsDetail] = useState(false);

    const [examQuestions, setExamQuestions] = useState<Question[]>([]);
    const [examQuestionsLoading, setExamQuestionsLoading] = useState(false);

    // `{references: TextbookReference[]}` after a lookup, `{error: true}` on failure.
    const [textbookRef, setTextbookRef] = useState<any>(null);
    const [textbookLoading, setTextbookLoading] = useState(false);
    const [textbookScreenshot, setTextbookScreenshot] = useState<string | null>(null);
    // The page image is being fetched from /ai/screenshot/ (the question has
    // no stored one, or the stored one failed to load).
    const [textbookShotLoading, setTextbookShotLoading] = useState(false);
    // Question id the in-flight textbook lookup belongs to; a response for
    // a question the student has since left is dropped.
    const textbookRequestFor = useRef<number | null>(null);
    // The question /ai/screenshot/ was asked for (once per opened question),
    // and a counter that lets only the newest screenshot request write.
    const screenshotAskedFor = useRef<number | null>(null);
    const screenshotSeq = useRef(0);
    useEffect(() => {
        const seq = screenshotSeq;
        return () => { seq.current += 1; };
    }, []);
    // Same for the AI analysis request.
    const aiRequestFor = useRef<number | null>(null);
    // Same for the question detail: the open question's id.
    const detailRequestFor = useRef<number | null>(null);

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
    }, [questionDetail, showAnswer, questions, selectedQuestion, page, totalCount, studyMode]);

    useEffect(() => {
        if (!aiLoading) return;
        setLoadingMsgIndex(0);
        const interval = setInterval(() => {
            setLoadingMsgIndex(prev => (prev + 1) % loadingMessages.current.length);
        }, 3000);
        return () => clearInterval(interval);
    }, [aiLoading]);

    // Stats + subjects + years ("meta"). Each request settles on its own so
    // a slow or failing /stats/ never blocks the filters or the list. A
    // rate-limited (429) part is retried once after Retry-After, like the
    // list; a part that still fails shows a "Retry" link in the filter card
    // (a 429 used to leave the strip and the dropdowns empty, and a
    // ?subject= link unfiltered, until a full reload).
    // Subjects are NOT filtered by exam_type: the Question → Subject FK
    // model uses the same medical subject names across CMS / NEET PG /
    // INI-CET tracks, and the loader's "Imported" bucket is itself tagged
    // exam_type='cms'. Filtering by exam_type=cms therefore hides every real
    // medical subject (Anatomy, Surgery, etc.) and leaves only the two
    // "Expert Curated" rows. Years ARE the bank's exam's (contract C11).
    const metaSeq = useRef<Record<MetaPart, number>>({ subjects: 0, years: 0, stats: 0 });
    const metaRetryTimers = useRef<Partial<Record<MetaPart, ReturnType<typeof setTimeout>>>>({});
    useEffect(() => {
        const timers = metaRetryTimers.current;
        return () => { Object.values(timers).forEach(t => { if (t) clearTimeout(t); }); };
    }, []);
    const loadMeta = useCallback((parts: MetaPart[] = META_PARTS) => {
        const run = (part: MetaPart, isRetry: boolean) => {
            const pendingRetry = metaRetryTimers.current[part];
            if (pendingRetry) {
                clearTimeout(pendingRetry);
                delete metaRetryTimers.current[part];
            }
            // Only the newest request of a part may write it (an older
            // exam's response, or a request a Retry replaced, is dropped).
            const seq = ++metaSeq.current[part];
            const isCurrent = () => seq === metaSeq.current[part];
            setMetaFailed(prev => (prev[part] ? { ...prev, [part]: false } : prev));
            let request: Promise<void>;
            if (part === 'subjects') {
                setSubjectsStatus(prev => (prev === 'ok' ? prev : 'loading'));
                request = fetchAllSubjects().then(list => {
                    if (!isCurrent()) return;
                    setSubjects(list);
                    setSubjectsStatus('ok');
                });
            } else if (part === 'years') {
                // This exam's years only; the endpoint never lists year 0.
                request = questionsAPI.getYears({ exam_type: examType }).then(res => {
                    if (isCurrent()) setYears(normaliseYears(res.data));
                });
            } else {
                request = questionsAPI.getStats({ exam_source: examSource }).then(res => {
                    if (isCurrent()) setQbankStats(res.data);
                });
            }
            request.catch((err: unknown) => {
                if (!isCurrent()) return;
                if (!isRetry && errorStatus(err) === 429) {
                    // Usually the same burst that rate-limits the list; the
                    // subjects stay 'loading' so a ?subject= link keeps waiting
                    // (with the list's "busy" note over its skeleton).
                    const wait = retryAfterSeconds(err);
                    if (part === 'subjects') setListNotice(`The question bank is busy right now. Retrying in ${wait}s…`);
                    metaRetryTimers.current[part] = setTimeout(() => {
                        delete metaRetryTimers.current[part];
                        run(part, true);
                    }, wait * 1000);
                    return;
                }
                if (part === 'subjects') setSubjectsStatus(prev => (prev === 'ok' ? prev : 'failed'));
                setMetaFailed(prev => ({ ...prev, [part]: true }));
            });
        };
        parts.forEach(part => run(part, false));
    }, [examSource, examType]);

    // The question list itself is loaded by the filter effect below so the
    // first request already carries ?year= / ?bookmarked=1 — previously this
    // effect fetched an unfiltered page that usually resolved last (it also
    // waited for /stats/) and replaced the filtered list.
    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            // Keep the deep link (path + query) so login returns here.
            const query = searchParams.toString();
            const next = `${pathname || '/questions'}${query ? `?${query}` : ''}`;
            router.replace(`/login?next=${encodeURIComponent(next)}`);
            return;
        }
        if (isAuthenticated) loadMeta();
        // searchParams / pathname only shape the login redirect.
    }, [authLoading, isAuthenticated, router, loadMeta]); // eslint-disable-line react-hooks/exhaustive-deps

    // Honour `?q=ID` once per value: after the first list load, and again
    // when a link changes it while the bank stays mounted. (A question whose
    // detail failed — e.g. a premium one on the free plan — used to be
    // re-requested on every list reload, and a new ?q= was ignored once any
    // question had been open.)
    const openedQueryId = useRef<string | null>(null);
    useEffect(() => {
        if (!initialQueryId || openedQueryId.current === initialQueryId) return;
        const id = Number(initialQueryId);
        if (!Number.isFinite(id) || id <= 0) return;
        if (loading || !isAuthenticated) return;
        if (questions.some(q => q.id === id) || page === 1) {
            openedQueryId.current = initialQueryId;
            openQuestion(id);
        }
    }, [initialQueryId, loading, isAuthenticated, questions, page]); // eslint-disable-line react-hooks/exhaustive-deps

    // Only the newest list request may write the list: a slower response
    // for an older filter set must not replace the current one.
    const listRequestSeq = useRef(0);
    // Pending automatic retry after a 429; any newer list request cancels it.
    const listRetryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => () => {
        if (listRetryTimer.current) clearTimeout(listRetryTimer.current);
    }, []);
    const fetchQuestions = (params: Record<string, string | number>, isRetry = false) => {
        if (listRetryTimer.current) {
            clearTimeout(listRetryTimer.current);
            listRetryTimer.current = null;
        }
        const seq = ++listRequestSeq.current;
        let retryScheduled = false;
        setLoading(true);
        setListError(null);
        // A new filter / page request replaces a pending "busy, retrying" note.
        if (!isRetry) setListNotice(null);
        questionsAPI.list(params).then(res => {
            if (seq !== listRequestSeq.current) return;
            const d = res.data;
            setQuestions(d.results || d || []);
            setTotalCount(d.count || (d.results || d || []).length);
        }).catch((err: unknown) => {
            if (seq !== listRequestSeq.current) return;
            if (errorStatus(err) === 429) {
                // The question-bank rate limiter: not the student's fault and
                // usually gone in seconds, so wait and retry once.
                if (!isRetry) {
                    const wait = retryAfterSeconds(err);
                    retryScheduled = true;
                    setListNotice(`The question bank is busy right now. Retrying in ${wait}s…`);
                    listRetryTimer.current = setTimeout(() => {
                        listRetryTimer.current = null;
                        fetchQuestions(params, true);
                    }, wait * 1000);
                    return;
                }
                setListError('The question bank is busy right now. Please wait a few seconds and try again.');
                return;
            }
            const apiError = err as { response?: { data?: unknown } };
            if (apiError.response?.data) {
                setListError(extractApiErrorMessage(apiError.response.data, 'Unable to load questions right now.'));
                return;
            }
            setListError('Unable to load questions right now. Please refresh and try again.');
        }).finally(() => {
            if (seq !== listRequestSeq.current || retryScheduled) return;
            setLoading(false);
            setListNotice(null);
        });
    };

    // List load: runs once auth resolves (so ?year= / ?subject= /
    // ?bookmarked=1 apply to the very first request) and again whenever a
    // filter changes.
    useEffect(() => {
        if (!isAuthenticated || subjectPending) return;
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
    }, [isAuthenticated, subjectPending, selectedSubject, selectedDifficulty, selectedYear, selectedExam, searchQuery, bookmarkedOnly]);

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

        const params: Record<string, string | number> = { page_size: 100 };
        if (selectedYear) params.year = selectedYear;
        if (selectedSubject) params.subject = selectedSubject;
        if (selectedDifficulty) params.difficulty = selectedDifficulty;
        if (searchQuery) params.search = searchQuery;
        if (bookmarkedOnly) params.bookmarked = 'true';
        params.exam_type = selectedExam;

        setExamQuestionsLoading(true);
        let cancelled = false;
        const HARD_CAP = 600;
        const MAX_PAGES = 30;

        // Follow the API's `next` links instead of assuming the server used
        // page_size=100 (it used to send 20 rows, which ended the old
        // `items.length < 100` loop after the first page).
        collectPages<Question>(
            (pageNum) => questionsAPI.list({ ...params, page: pageNum }).then(res => res.data),
            { maxItems: HARD_CAP, maxPages: MAX_PAGES, isCancelled: () => cancelled },
        )
            .then(({ items }) => {
                if (cancelled) return;
                setExamQuestions(items);
                setExamQuestionsLoading(false);
            })
            .catch(() => {
                if (cancelled) return;
                setExamQuestions([]);
                setExamQuestionsLoading(false);
            });

        return () => { cancelled = true; };
    }, [studyMode, selectedYear, selectedSubject, selectedDifficulty, selectedExam, searchQuery, isAuthenticated, bookmarkedOnly]);

    // When the open question was shown; answers report the time spent so
    // the server can record per-subject study time.
    const questionOpenedAt = useRef<number>(0);
    const secondsOnQuestion = () =>
        questionOpenedAt.current ? Math.max(0, Math.round((Date.now() - questionOpenedAt.current) / 1000)) : 0;

    const openQuestion = useCallback((id: number) => {
        questionOpenedAt.current = Date.now();
        detailRequestFor.current = id;
        setSelectedQuestion(id);
        setDetailError(null);
        setAnswerLockedId(null);
        setShowAnswer(false);
        setSelectedAnswer(null);
        setAiExplanation(null);
        setAiLoading(false);
        setTokenError(false);
        setAiError(null);
        setTextbookRef(null);
        setTextbookScreenshot(null);
        setTextbookShotLoading(false);
        setTextbookLoading(false);
        textbookRequestFor.current = null;
        screenshotAskedFor.current = null;
        screenshotSeq.current += 1;
        aiRequestFor.current = null;
        // Responses for a question the student has since left are dropped
        // (a slow one used to replace the newer question's detail).
        const isCurrent = () => detailRequestFor.current === id;
        Promise.all([
            questionsAPI.get(id),
            questionsAPI.getSimilar(id),
        ]).then(([qRes, sRes]) => {
            if (!isCurrent()) return;
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
            if (!isCurrent()) return;
            questionsAPI.get(id).then(res => {
                if (!isCurrent()) return;
                setQuestionDetail(res.data);
                if (res.data.user_selected_answer) {
                    setSelectedAnswer(res.data.user_selected_answer);
                }
            }).catch((err: unknown) => {
                // A premium question on the free plan (the detail endpoint
                // only serves the free showcase to free accounts), a removed
                // question or a failed request: the pane says which (it
                // used to show a loading skeleton forever).
                if (isCurrent()) setDetailError({ id, error: err });
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

    // The attempt was refused on the free plan (402 upgrade_required): undo
    // the pick and show the upgrade prompt instead of the reveal (C13).
    const relockIfUpgradeRequired = (qId: number, err: unknown) => {
        const feature = upgradeRequiredFeature(err);
        if (!feature) return;
        setExamAnswers(prev => {
            if (!(qId in prev)) return prev;
            const next = { ...prev };
            delete next[qId];
            return next;
        });
        if (detailRequestFor.current === qId) {
            setShowAnswer(false);
            setSelectedAnswer(null);
            setAnswerLockedId(qId);
        }
        // The api.ts interceptor opens it too; showing it twice is a no-op.
        showPaywall(feature);
    };

    const handleSelectOption = (opt: string) => {
        if (!questionDetail) return;
        // The previous question stays on screen until the next one's detail
        // arrives: never record a pick against it.
        if (questionDetail.id !== selectedQuestion) return;
        if (showAnswer) return;
        if (answerLockedId === questionDetail.id) {
            showPaywall('PYQ answers');
            return;
        }
        keepStudyMode();
        setSelectedAnswer(opt);

        if (studyMode === 'practice') {
            setShowAnswer(true);
            const qId = questionDetail.id;
            questionsAPI.attempt(qId, { selected_answer: opt, time_spent_seconds: secondsOnQuestion() }).then((res) => {
                // Mark the row answered in the list (previously only when a
                // token was earned, so most answers never showed up there),
                // with the server's verdict — null when the question has no
                // answer key (nothing recorded; the row says "Attempted",
                // it used to say "Incorrect").
                const verdict = attemptVerdict(opt, res?.data);
                setQuestions(prev => prev.map(q => q.id === qId ? { ...q, user_selected_answer: opt, user_is_correct: verdict } : q));
            }).catch((err: unknown) => relockIfUpgradeRequired(qId, err));
        }
    };

    const handleSubmitExamModeAnswer = () => {
        if (!questionDetail || !selectedAnswer || showAnswer) return;
        if (questionDetail.id !== selectedQuestion) return;
        keepStudyMode();
        setShowAnswer(true);
        const qId = questionDetail.id;
        const picked = selectedAnswer;
        // Graded against the detail's key until the server answers; without
        // a key the pick is ungraded (null), not wrong.
        const key = answerLetter(questionDetail.correct_answer);
        const isCorrect = key ? picked === key : null;
        questionsAPI.attempt(qId, { selected_answer: picked, time_spent_seconds: secondsOnQuestion() }).then((res) => {
            const verdict = attemptVerdict(picked, res?.data);
            setQuestions(prev => prev.map(q => q.id === qId ? { ...q, user_selected_answer: picked, user_is_correct: verdict } : q));
            setExamAnswers(prev => (prev[qId] ? { ...prev, [qId]: { ...prev[qId], isCorrect: verdict } } : prev));
        }).catch((err: unknown) => relockIfUpgradeRequired(qId, err));
        setExamAnswers(prev => ({ ...prev, [qId]: { selected: picked, isCorrect, answeredAt: Date.now() } }));
    };

    const fetchAiExplanation = () => {
        if (!questionDetail || aiLoading) return;
        const d = questionDetail as any;
        // Consent-gated (the button used to also call window.gtag directly,
        // which fired before analytics consent).
        analytics.aiExplanationOpen(d.id, String(d.subject_name || ''));
        setAiLoading(true);
        setAiExplanation(null);
        setTokenError(false);
        setAiError(null);
        // `question_id` lets the server use the stored question (its answer
        // key, stored explanation and the cached analysis) and check the
        // student's entitlement; the text fields are a fallback only.
        const payload: Parameters<typeof aiAPI.explainAfterAnswer>[0] = {
            question_id: d.id,
            question_text: sanitizeQuestionText(d.question_text),
            options: {
                A: sanitizeOptionText(d.option_a || d.option_A || ''),
                B: sanitizeOptionText(d.option_b || d.option_B || ''),
                C: sanitizeOptionText(d.option_c || d.option_C || ''),
                D: sanitizeOptionText(d.option_d || d.option_D || ''),
            },
            correct_answer: answerLetter(d.correct_answer),
            selected_answer: selectedAnswer || '',
            subject: d.subject_name || '',
            topic: d.topic_name || '',
        };
        const reqId = d.id;
        aiRequestFor.current = reqId;
        aiAPI.explainAfterAnswer(payload).then(res => {
            // The student opened another question meanwhile: drop it.
            if (aiRequestFor.current !== reqId) return;
            setAiExplanation(res.data);
            setAiLoading(false);
        }).catch((err) => {
            if (aiRequestFor.current !== reqId) return;
            setAiLoading(false);
            const failure = classifyAiFailure(err);
            if (failure === 'upgrade') {
                // Free plan on a premium question: the paywall, not an AI
                // outage (the api.ts interceptor opens it too; a no-op twice).
                showPaywall(upgradeRequiredFeature(err) || 'PYQ answers');
            } else if (failure === 'tokens') {
                setTokenError(true);
            } else {
                // 503 ai_unavailable → "AI is unavailable right now" (never
                // charged); a throttle 429 is not an empty wallet. Never the
                // server's raw error text. No silent automatic retry: an AI
                // call can take up to the full timeout, and the card below
                // offers a Retry button.
                setAiError(aiFailureNotice(failure, err));
                setAiExplanation(null);
            }
        });
    };

    // The textbook page image from /ai/screenshot/ (it renders the cited
    // page on the server and answers {screenshot_url}; a 202 "rendering" is
    // asked once more, a 404 means no image, a 402 opens the paywall through
    // the api.ts interceptor). At most once per opened question, and only
    // from the "Find in Textbook" click. False when it was already asked.
    const requestTextbookScreenshot = (qid: number): boolean => {
        if (screenshotAskedFor.current === qid) return false;
        screenshotAskedFor.current = qid;
        const seq = ++screenshotSeq.current;
        const isCurrent = () => seq === screenshotSeq.current && textbookRequestFor.current === qid;
        setTextbookShotLoading(true);
        void fetchPageScreenshot(aiAPI.getScreenshot, qid, { isCurrent }).then(url => {
            if (!isCurrent()) return;
            setTextbookShotLoading(false);
            setTextbookScreenshot(url);
        });
        return true;
    };

    // The page image failed to load (e.g. a stored file lost on a redeploy):
    // ask /ai/screenshot/ once, which renders the page again; a second
    // failure just hides the image.
    const handleTextbookScreenshotError = () => {
        setTextbookScreenshot(null);
        const qid = (questionDetail as any)?.id;
        if (typeof qid === 'number' && textbookRequestFor.current === qid) requestTextbookScreenshot(qid);
    };

    // "Find in Textbook": the book / chapter / page covering the question.
    const lookupTextbook = () => {
        const d = questionDetail as any;
        if (!d) return;
        const qid = d.id;
        textbookRequestFor.current = qid;
        setTextbookLoading(true);
        setTextbookRef(null);
        setTextbookScreenshot(null);
        setTextbookShotLoading(false);
        aiAPI.textbookReference({ question_text: d.question_text })
            .then(res => {
                if (textbookRequestFor.current !== qid) return;
                // The endpoint returns {references: [{book, page, excerpt, …}]}.
                setTextbookRef({ references: normaliseTextbookReferences(res.data) });
                // The page screenshot stored on the question, else the one
                // /ai/screenshot/ renders (it answers a URL now, not the
                // server filesystem path it used to).
                const storedShot = typeof d.page_screenshot === 'string' ? d.page_screenshot.trim() : '';
                if (storedShot) setTextbookScreenshot(storedShot);
                else requestTextbookScreenshot(qid);
            })
            .catch((err: unknown) => {
                if (textbookRequestFor.current !== qid) return;
                const feature = upgradeRequiredFeature(err);
                if (feature) {
                    // Premium question on the free plan: the paywall, and the
                    // button again (not "no textbook mapping").
                    showPaywall(feature);
                    return;
                }
                setTextbookRef({ error: true });
            })
            .finally(() => {
                if (textbookRequestFor.current === qid) setTextbookLoading(false);
            });
    };

    const handleBookmark = (id: number, e: React.MouseEvent) => {
        e.stopPropagation();
        questionsAPI.bookmark(id).then(() => {
            setQuestions(prev => prev.map(q => q.id === id ? { ...q, is_bookmarked: !q.is_bookmarked } : q));
            if (questionDetail?.id === id) {
                setQuestionDetail((prev: any) => prev ? { ...prev, is_bookmarked: !prev.is_bookmarked } : prev);
            }
        }).catch(() => { /* toggle failed: the icon keeps its current state */ });
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

    // Reload whatever bank metadata (subjects, years, stats strip) failed or
    // is still missing.
    const retryMeta = () => {
        // A `?subject=` link whose subject list never loaded gets resolved again.
        if (subjectsStatus === 'failed' && subjectParam) setAppliedSubjectParam('');
        const missing: Record<MetaPart, boolean> = {
            subjects: subjectsStatus === 'failed' || subjects.length === 0,
            years: years.length === 0,
            stats: !qbankStats,
        };
        const parts = META_PARTS.filter(part => metaFailed[part] || missing[part]);
        if (parts.length > 0) loadMeta(parts);
    };

    // List error "Retry": the list plus the metadata that failed with it —
    // the same burst that fails the list usually fails those too.
    const retryListAndMeta = () => {
        retryMeta();
        handleSearch();
    };
    const metaRetryNeeded = metaFailed.subjects || metaFailed.years || metaFailed.stats;

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

    // Fullscreen year practice (/questions/practice) for the current exam.
    const fullscreenPracticeHref = (year: string | null) => {
        const params = new URLSearchParams();
        if (year) params.set('year', year);
        params.set('exam', selectedExam);
        return `/questions/practice?${params.toString()}`;
    };

    const diffBadge = (d: string) => {
        const cls = d === 'easy' ? 'badge-easy' : d === 'hard' ? 'badge-hard' : 'badge-medium';
        return <span className={`badge ${cls}`}>{d}</span>;
    };

    const detail = questionDetail as any;
    const totalPages = Math.ceil(totalCount / PAGE_SIZE);
    // Curated explanation (an admin override first when the detail flags
    // one), else the effective (AI) one.
    const detailExplanation = detail ? (pickExplanation(detail) || '') : '';
    // The open question's answer key ('' when it has none).
    const detailKey = detail ? answerLetter(detail.correct_answer) : '';
    // The stem's figures: `stem_images` (the backend's role-filtered list), else `images` without
    // explanation figures for rows that pre-date it. The side pane (and its zoom viewer) shows the
    // ones the stem does not already show inline (`[[img:N]]` where the author placed it), so a
    // figure never appears twice.
    const stemFigures: any[] = !detail ? [] : Array.isArray(detail.stem_images) && detail.stem_images.length > 0
        ? detail.stem_images
        : (Array.isArray(detail.images) ? detail.images.filter((img: any) => img.role !== 'explanation') : []);
    const paneFigures: any[] = sidePaneFigures(stemFigures, detail?.question_text);
    // Why the selected question's detail could not be shown (or null).
    const detailFailure = selectedQuestion && detailError?.id === selectedQuestion
        ? detailFailureKind(detailError.error, isPremium)
        : null;
    // One PYQ definition (rows with a real year; year 0 is the Expert
    // Curated sentinel) for the headline AND the progress bar.
    const bankStats = summariseBankStats(qbankStats);
    const pyqCount = bankStats.pyqTotal;
    const pyqProgressPct = pyqCount > 0 ? Math.round((bankStats.pyqSolved / pyqCount) * 100) : 0;
    // The year tiles: PYQ years only (no "0" tile for the undated pool).
    const yearStatRows: any[] = Array.isArray(qbankStats?.by_year)
        ? qbankStats.by_year.filter((b: any) => Number(b?.year) > 0)
        : [];
    // Stats that cover no question at all (e.g. an exam the stats endpoint
    // does not map yet) would only claim "0 PYQs" next to a full list.
    const showBankStats = !!qbankStats && bankStats.hasRows;
    const filtersActive = !!(selectedSubject || selectedDifficulty || selectedYear || searchQuery || bookmarkedOnly);

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
                                        // Every exam opens the fullscreen one-question player. The
                                        // NEET PG branch used to push /questions/neet-pg/practice —
                                        // the bank route already on screen — so the button only
                                        // changed the URL.
                                        router.push(fullscreenPracticeHref(selectedYear));
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
                        {showBankStats && (
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
                                    {/* The stats count PYQs by exam_source while the list
                                        below (exam_type) also holds the Expert Curated pool, so
                                        say which number is which instead of "2277 MCQs and
                                        PYQs" above a 277-page list of curated cards. The
                                        "incl. Expert Curated" note only when the stats do
                                        have undated rows (it used to appear on banks with
                                        none). */}
                                    <p className="text-xs text-muted-foreground">
                                        {pyqCount.toLocaleString('en-IN')} {examSource} PYQs
                                        {!filtersActive && bankStats.undatedTotal > 0 && totalCount > pyqCount
                                            ? ` · ${totalCount.toLocaleString('en-IN')} questions incl. Expert Curated`
                                            : ''}
                                    </p>
                                </div>

                                <div className="flex flex-1 max-w-md items-center gap-3">
                                    <div className="flex-1 space-y-0.5 min-w-0">
                                        {/* Same PYQ count as the headline (it used to divide by
                                            a total that also counted the undated rows). */}
                                        <div className="flex justify-between text-xs font-semibold gap-2">
                                            <span className="truncate">PYQ Progress</span>
                                            <span className="text-primary font-bold shrink-0">
                                                {bankStats.pyqSolved.toLocaleString('en-IN')} / {pyqCount.toLocaleString('en-IN')} ({pyqProgressPct}%)
                                            </span>
                                        </div>
                                        <Progress value={pyqProgressPct} className="h-1.5" />
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

                        {showBankStats && showStatsDetail && (
                            <div
                                id="year-stats-panel"
                                className="pt-1 pb-3 border-b border-border/40 animate-fadeIn space-y-2"
                            >
                                <div className="flex items-center justify-between">
                                    <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                                        Tap a year to filter · long-press / right-click for the Practice & Exam modal
                                    </p>
                                    <p className="text-[10px] text-muted-foreground">
                                        {yearStatRows.length} years
                                    </p>
                                </div>
                                <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-1.5 max-h-65 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
                                    {yearStatRows.map((item: any) => {
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
                                <div className="flex items-center gap-2 shrink-0">
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
                                    {/* Settings > Customise: the default mode and which tools show. */}
                                    {questionBankPrefs.signedIn && (
                                        <Link
                                            href="/settings#customise-question-bank"
                                            prefetch={false}
                                            aria-label="Customise the question bank"
                                            title="Customise the question bank"
                                            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-muted/40 text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        >
                                            <SlidersHorizontal className="w-4 h-4" aria-hidden="true" />
                                        </Link>
                                    )}
                                </div>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_140px_120px_120px] gap-2 lg:gap-2 items-center">
                                <select
                                    aria-label="Filter by subject"
                                    className={`${FILTER_SELECT_CLS} truncate`}
                                    value={selectedSubject}
                                    onChange={e => setSelectedSubject(e.target.value)}
                                >
                                    <option value="">All Subjects</option>
                                    {subjectOptions.map(s => (
                                        <option key={s.id} value={s.id}>
                                            {s.name} ({s.count.toLocaleString('en-IN')})
                                        </option>
                                    ))}
                                </select>
                                <select
                                    aria-label="Filter by difficulty"
                                    className={FILTER_SELECT_CLS}
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
                                    className={FILTER_SELECT_CLS}
                                    value={selectedYear}
                                    onChange={e => setSelectedYear(e.target.value)}
                                >
                                    <option value="">Year</option>
                                    {/* This exam's PYQ years (the endpoint never lists year 0). */}
                                    {years.map(y => (
                                        <option key={y} value={y}>{y}</option>
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
                            {metaRetryNeeded && (
                                <div role="status" className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                                    <span>
                                        {metaFailed.subjects || metaFailed.years
                                            ? "Some filters couldn't load."
                                            : "Your progress stats couldn't load."}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={retryMeta}
                                        className="font-semibold text-primary hover:underline underline-offset-2"
                                    >
                                        Retry
                                    </button>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Content */}
                <div className={`qbank-grid flex-1 min-h-0 ${selectedQuestion ? 'has-selected' : ''} ${studyMode === 'exam' ? 'qbank-mode-exam' : ''}`}>
                    <div className="qbank-list lg:overflow-y-auto lg:overscroll-contain lg:pr-2" style={{ scrollbarWidth: 'thin' }}>
                        <div className="space-y-3 px-1 py-0.5">
                            {loading ? (
                                <div className="space-y-3">
                                    {listNotice && (
                                        <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground">
                                            <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" /> {listNotice}
                                        </p>
                                    )}
                                    {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
                                </div>
                            ) : listError ? (
                                <Card className="p-8 text-center">
                                    <p className="text-destructive text-sm mb-3">{listError}</p>
                                    <button
                                      type="button"
                                      onClick={retryListAndMeta}
                                      className="text-xs font-semibold bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 rounded-lg transition-colors"
                                    >
                                      Retry
                                    </button>
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
                                                    {q.user_selected_answer && (q.user_is_correct == null ? (
                                                        // Picked, but ungraded (the question has no answer key).
                                                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground border border-border">
                                                            Attempted
                                                        </span>
                                                    ) : (
                                                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${q.user_is_correct ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}`}>
                                                            {q.user_is_correct ? '✓ Solved' : '✗ Incorrect'}
                                                        </span>
                                                    ))}
                                                    {diffBadge(q.difficulty)}
                                                    {/* p-2 -m-2: a 32px tap target (the bare 16px icon
                                                        sat inside a clickable card, so near misses
                                                        opened the question) without shifting layout. */}
                                                    <button
                                                        type="button"
                                                        onClick={(e) => handleBookmark(q.id, e)}
                                                        className="p-2 -m-2 rounded-full hover:scale-110 transition-transform"
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
                                            <Button variant="outline" size="sm" onClick={() => handlePageChange(page - 1)} disabled={page <= 1} aria-label="Previous page">
                                                <ChevronLeft className="w-4 h-4" aria-hidden="true" />
                                            </Button>
                                            <span className="text-sm px-3 text-muted-foreground">
                                                Page {page} of {totalPages}
                                            </span>
                                            <Button variant="outline" size="sm" onClick={() => handlePageChange(page + 1)} disabled={page >= totalPages} aria-label="Next page">
                                                <ChevronRight className="w-4 h-4" aria-hidden="true" />
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
                                                ? ans.isCorrect === null ? 'answered' : ans.isCorrect ? 'correct' : 'wrong'
                                                : isCurrent ? 'current' : 'unseen';
                                            const statusClass = {
                                                correct: 'bg-emerald-500 text-white border-emerald-500',
                                                wrong: 'bg-red-500 text-white border-red-500',
                                                // Picked, but the question has no answer key.
                                                answered: 'bg-primary/15 text-primary border-primary/40',
                                                current: 'bg-amber-400 text-amber-950 border-amber-400 ring-2 ring-amber-400/40',
                                                unseen: 'bg-muted text-muted-foreground border-border hover:bg-muted/80',
                                            }[status];
                                            return (
                                                <button
                                                    key={q.id}
                                                    type="button"
                                                    onClick={() => {
                                                        // Same rule as the list cards: a premium row on the
                                                        // free plan opens the paywall, not a detail request.
                                                        if (!isPremium && !q.is_showcase) {
                                                            showPaywall('PYQ answers');
                                                            return;
                                                        }
                                                        openQuestion(q.id);
                                                    }}
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
                        {selectedQuestion && detailFailure === 'locked' ? (
                            // Premium question on the free plan (a ?q= link, the
                            // exam palette, N / P, a similar-PYQ link).
                            <Card className="p-6 md:p-10 text-center border-amber-300 bg-amber-50/80 dark:bg-amber-950/30 dark:border-amber-800/60 animate-fadeIn">
                                <Lock className="w-10 h-10 mx-auto mb-3 text-amber-600 dark:text-amber-400" />
                                <p className="text-base font-semibold text-foreground mb-1">This is a premium question</p>
                                <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">
                                    Upgrade to practise it and see its answer and explanation.
                                </p>
                                <Button size="sm" onClick={() => showPaywall('PYQ answers')}>Upgrade</Button>
                            </Card>
                        ) : selectedQuestion && detailFailure ? (
                            <Card role="alert" className="p-6 md:p-10 text-center animate-fadeIn">
                                <p className="text-sm text-foreground mb-3">
                                    {detailFailure === 'missing'
                                        ? 'This question is no longer available.'
                                        : 'Unable to load question details. Please try again.'}
                                </p>
                                {detailFailure === 'error' && (
                                    <Button size="sm" variant="outline" onClick={() => openQuestion(selectedQuestion)}>
                                        Retry
                                    </Button>
                                )}
                            </Card>
                        ) : selectedQuestion && !detail ? (
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
                                        {detail.user_selected_answer && !showAnswer && answerLockedId !== detail.id && (
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
                                        {paneFigures.length > 0 ? (
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
                                                        {/* figureSrc: the API's address, or the image endpoint (never a retired
                                                           storage host); FigureImage retries once, then shows a clear placeholder. */}
                                                        {paneFigures.map((img: any, idx: number) => (
                                                            <button
                                                                key={img.id}
                                                                type="button"
                                                                onClick={() => setViewImageIdx(idx)}
                                                                className="block w-full text-left rounded-xl overflow-hidden border border-border/60 hover:border-primary/60 transition-colors cursor-zoom-in bg-muted/20"
                                                            >
                                                                <FigureImage src={figureSrc(img)} alt={img.caption || 'Question figure'}
                                                                    className="w-full h-auto max-h-[55vh] object-contain bg-muted/30" loading="lazy"
                                                                    placeholderClassName="m-3" />
                                                                {img.caption && <p className="text-[10px] text-muted-foreground p-1.5">{img.caption}</p>}
                                                            </button>
                                                        ))}
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
                                                const isCorrect = detailKey === opt;
                                                const isSelected = selectedAnswer === opt;
                                                // Without an answer key a pick can't be marked wrong.
                                                const isWrong = !!detailKey && isSelected && !isCorrect && showAnswer;

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

                                        {/* The server refused to grade it on the free plan (402). */}
                                        {answerLockedId === detail.id && (
                                            <div className="mb-3 flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl border border-amber-300 bg-amber-50/80 dark:bg-amber-950/30 dark:border-amber-800/60 p-3">
                                                <Lock className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
                                                <p className="flex-1 text-sm text-amber-900 dark:text-amber-200">
                                                    This is a premium question. Upgrade to see its answer and explanation.
                                                </p>
                                                <Button size="sm" onClick={() => showPaywall('PYQ answers')}>Upgrade</Button>
                                            </div>
                                        )}

                                        {!showAnswer && !selectedAnswer && studyMode === 'practice' && answerLockedId !== detail.id && (
                                            <p className="text-xs text-center py-2 text-muted-foreground">👆 Select an option to reveal the answer & detailed analysis</p>
                                        )}

                                        {!showAnswer && studyMode === 'exam' && answerLockedId !== detail.id && (
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
                                        <Card className={detailKey
                                            ? 'border-emerald-300 bg-emerald-50/80 dark:bg-emerald-950/30 dark:border-emerald-800/60'
                                            : 'border-border bg-muted/40'}>
                                            <CardContent className="p-4 space-y-2">
                                                {detailKey ? (
                                                    <h4 className="text-sm font-bold text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
                                                        <CheckCircle className="w-4 h-4" /> Correct Answer: {detailKey}
                                                    </h4>
                                                ) : (
                                                    // No key in the bank (it used to read "Correct Answer:" and nothing).
                                                    <h4 className="text-sm font-bold text-foreground">
                                                        Answer key not available for this question. Use “Flag Issue” to let us know.
                                                    </h4>
                                                )}
                                                {/* The curated explanation (or a flagged admin
                                                    override), else the effective (AI) one. */}
                                                {detailExplanation && (
                                                    <div className="rounded-lg bg-white/80 dark:bg-slate-900/40 p-3 text-sm leading-relaxed text-foreground">
                                                        <FormattedText text={resolveImageTokensForMarkdown(extractAnalysisFromJson(detailExplanation), detail.images)} />
                                                    </div>
                                                )}
                                                {/* The key was corrected and the old explanation is withheld until rewritten. */}
                                                {typeof detail?.explanation_notice === 'string' && detail.explanation_notice && (
                                                    <p className="text-xs text-muted-foreground">{detail.explanation_notice}</p>
                                                )}
                                            </CardContent>
                                        </Card>

                                        {/* Accepted textbook citations (snippets only; nothing when there are none). */}
                                        {shows('citations') && <StudentCitations questionId={detail.id} revealed={showAnswer} />}

                                        {shows('video') && detail?.video_url && detail?.video_status === 'completed' && (
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

                                        {shows('ai-analysis') && !aiExplanation && !aiLoading && !tokenError && (
                                            <button onClick={() => {
                                                    // The GA4 "ai_explain_request" conversion (consent-gated).
                                                    analytics.aiExplainRequest(detail.id, selectedExam, 'question_bank');
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

                                        {shows('mnemonic') && detail.mnemonic && !aiExplanation?.mnemonic && (
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

                                        {shows('textbook-reference') && detail.book_name && !aiExplanation?.textbook_reference?.book && (
                                            <div className="glass-card p-4 flex items-start gap-3">
                                                <Bookmark className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#8b5cf6' }} />
                                                <div>
                                                    <h5 className="text-xs font-bold mb-0.5" style={{ color: '#8b5cf6' }}>📚 Textbook Reference</h5>
                                                    <p className="text-sm font-semibold">{String(detail.book_name)} {detail.chapter ? `— Ch: ${String(detail.chapter)}` : ''} {detail.page_number ? `(pg ${String(detail.page_number)})` : ''}</p>
                                                </div>
                                            </div>
                                        )}

                                        {shows('similar-pyqs') && detail.similar && (detail.similar as unknown[]).length > 0 && (
                                            <div className="glass-card p-4">
                                                <h5 className="text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: 'var(--accent-primary)' }}>
                                                    <Target className="w-3.5 h-3.5" /> Similar PYQs from Database
                                                </h5>
                                                <div className="space-y-1.5">
                                                    {(detail.similar as Array<{ id: number; year: number; question_text: string }>).map((sq) => {
                                                        // Defence-in-depth: strip double-encoded UTF-8 mojibake
                                                        // (e.g. iÃ©iÃiÃ©) before rendering, and fall back to a
                                                        // generic "Question #N" placeholder when the text is
                                                        // still unreadable after cleanup (the same guard the
                                                        // list cards above use).
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

                                        {shows('ai-analysis') && aiLoading && (
                                            <div className="glass-card p-5 flex items-center gap-4 animate-pulse" style={{ borderColor: 'rgba(6,182,212,0.3)' }}>
                                                <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--accent-primary)' }} />
                                                <div>
                                                    <span className="text-sm font-bold transition-all duration-500" style={{ color: 'var(--accent-primary)' }}>{loadingMessages.current[loadingMsgIndex]}</span>
                                                    <span className="text-xs block mt-1" style={{ color: 'var(--text-secondary)' }}>Generating mnemonics, topic knowledge, exam tips & more</span>
                                                </div>
                                            </div>
                                        )}

                                        {shows('ai-analysis') && tokenError && (
                                            <div className="token-depleted-banner mt-3">
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

                                        {shows('ai-analysis') && aiError && !tokenError && (
                                            <div className="glass-card p-4 mt-3" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
                                                <div className="flex items-start gap-3">
                                                    <Brain className="w-5 h-5 mt-0.5 shrink-0" style={{ color: '#f59e0b' }} />
                                                    <div role="status">
                                                        <h5 className="text-sm font-bold" style={{ color: '#f59e0b' }}>{aiError.title}</h5>
                                                        <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{aiError.message}</p>
                                                        <button onClick={() => fetchAiExplanation()} className="text-xs mt-2 font-bold" style={{ color: 'var(--accent-primary)' }}>
                                                            Retry
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                        {shows('ai-analysis') && aiExplanation && !aiLoading && (
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
                                                                <CheckCircle className="w-3.5 h-3.5" /> {detailKey ? `Why ${detailKey} is Correct` : 'Why this is correct'}
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

                                {showAnswer && detail && shows('find-in-textbook') && (
                                    <div className="space-y-2">
                                        {!textbookRef && !textbookLoading && (
                                            <button
                                                onClick={lookupTextbook}
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
                                        {textbookRef && !textbookRef.error && (textbookRef.references.length > 0 || textbookScreenshot || textbookShotLoading) && (
                                            <Card className="border-indigo-200 bg-indigo-50/30 dark:bg-indigo-950/10 dark:border-indigo-900/30">
                                                <CardContent className="p-4 space-y-2">
                                                    <h5 className="text-xs font-bold text-indigo-700 dark:text-indigo-400 flex items-center gap-1.5">
                                                        <Bookmark className="w-3.5 h-3.5" /> 📖 Textbook Reference
                                                    </h5>
                                                    {textbookRef.references.map((ref: TextbookReference, i: number) => (
                                                        <div key={`${ref.book}-${ref.page}-${i}`} className={i > 0 ? 'pt-2 border-t border-indigo-200/60 dark:border-indigo-900/40' : ''}>
                                                            {ref.book && <p className="text-sm font-semibold">{ref.book}</p>}
                                                            {ref.chapter && <p className="text-xs text-muted-foreground">Chapter: {ref.chapter}</p>}
                                                            {ref.page && <p className="text-xs text-muted-foreground">Page: {ref.page}</p>}
                                                            {ref.excerpt && (
                                                                <p className="text-xs leading-relaxed mt-1 italic text-muted-foreground">
                                                                    &quot;{ref.excerpt}{ref.excerpt.length >= 300 ? '…' : ''}&quot;
                                                                </p>
                                                            )}
                                                        </div>
                                                    ))}
                                                    {textbookScreenshot ? (
                                                        <div className="mt-2 rounded-lg overflow-hidden border border-border/40 bg-white">
                                                            <img
                                                                src={textbookScreenshot}
                                                                alt="Textbook page screenshot"
                                                                width={800}
                                                                height={1000}
                                                                loading="lazy"
                                                                className="w-full h-auto"
                                                                onError={handleTextbookScreenshotError}
                                                            />
                                                            <p className="text-[10px] text-center text-muted-foreground py-1 bg-muted/30">Screenshot from textbook page</p>
                                                        </div>
                                                    ) : textbookShotLoading ? (
                                                        <div role="status" className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                            Loading the textbook page…
                                                        </div>
                                                    ) : null}
                                                </CardContent>
                                            </Card>
                                        )}
                                        {textbookRef && textbookRef.error && (
                                            // A failed lookup is not "no mapping": offer a retry.
                                            <Card className="border-border/60">
                                                <CardContent className="p-3 text-center text-xs text-muted-foreground">
                                                    Couldn&apos;t look up textbook references right now.{' '}
                                                    <button type="button" onClick={lookupTextbook} className="font-semibold text-primary hover:underline underline-offset-2">
                                                        Retry
                                                    </button>
                                                </CardContent>
                                            </Card>
                                        )}
                                        {textbookRef && !textbookRef.error && textbookRef.references.length === 0 && !textbookScreenshot && !textbookShotLoading && (
                                            <Card className="border-border/60">
                                                <CardContent className="p-3 text-center text-xs text-muted-foreground">
                                                    No textbook mapping available for this question.
                                                </CardContent>
                                            </Card>
                                        )}
                                    </div>
                                )}

                                {shows('discussion') && <DiscussionThread questionId={detail.id} />}

                                {shows('shortcuts') && (
                                    <div className="flex flex-wrap items-center gap-3 px-2 py-2 text-[10px] text-muted-foreground">
                                        <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">A-D</kbd> answer</span>
                                        <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">N</kbd> next</span>
                                        <span><kbd className="px-1.5 py-0.5 rounded border border-border bg-muted font-mono">P</kbd> prev</span>
                                    </div>
                                )}
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
                                        // Open the fullscreen player for every exam. The NEET PG /
                                        // INI-CET branches pushed the bank route already on screen,
                                        // so the click only changed the URL and left the modal open.
                                        setYearModalOpen(false);
                                        setSimulationError(null);
                                        router.push(fullscreenPracticeHref(modalYear));
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
                                        // The backend defaults to a CMS paper; the NEET PG and
                                        // INI-CET banks must ask for their own exam (C3).
                                        testsAPI.pyqSimulation({ year: Number(modalYear), exam_type: selectedExam })
                                            .then(res => {
                                                router.push(`/tests/${res.data.id}`);
                                            })
                                            .catch(err => {
                                                setStartingSimulation(false);
                                                const feature = upgradeRequiredFeature(err);
                                                if (feature) {
                                                    // Free plan: the upgrade prompt, not a red error
                                                    // under it in this modal.
                                                    setYearModalOpen(false);
                                                    showPaywall(feature);
                                                    return;
                                                }
                                                setSimulationError(extractApiErrorMessage(err.response?.data || err.message, 'Failed to generate simulation. Make sure there are enough questions in the database.'));
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
                component the timed test player (/tests/[id]) uses, so
                pinch-zoom, side-by-side, and fullscreen all work. Previously
                the carousel used <a target="_blank"> which would leak
                potentially-short-lived presigned S3 URLs into a new tab. */}
            {viewImageIdx !== null && paneFigures.length > 0 && (
                <ImageViewer
                    open
                    onClose={() => setViewImageIdx(null)}
                    startIndex={viewImageIdx}
                    // The side pane's figures, in its order (its index opens the same figure).
                    images={(paneFigures as ViewerImage[]).map((img: ViewerImage | any) => ({
                        id: img.id,
                        file_url: figureSrc(img) || null,
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
    // null: no verdict (an ungraded pick, or hidden on a locked row).
    user_is_correct?: boolean | null;
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