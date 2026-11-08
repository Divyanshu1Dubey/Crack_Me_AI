"use client";
/**
 * Practice page — Phase-3 question experience + Phase-4 mode scaffolding.
 *
 * Wires:
 *  - QuestionToolbar (prev/next/jump/flag/confidence/eliminate/reveal)
 *  - QuestionTimer (per-question auto-pause aware)
 *  - PracticeExamTimer (whole-session countdown for `timed` mode)
 *  - RevealExplanation (3-tier AI reveal)
 *  - ImageGallery (lazy + zoom + captions)
 *  - ProvenanceList
 *  - RecallBadge
 *  - RelatedPanel (related_pyqs + related_topics)
 *  - Mode-specific scope pickers (year / subject / topic / count)
 *  - Custom mode (multi-filter form: year, subject, topic, difficulty,
 *    is_image_based, has_ai_enrichment)
 *
 * Backend dispatcher: `/questions/practice_queue/?mode=...&count=...
 * &year=...&subject_id=...&topic_id=...&difficulty=...&is_image_based=...
 * &has_ai_enrichment=...`
 *
 * `?id=N` (recall search "Practice →", related-PYQ links) opens question N
 * first, even when the mode's random queue doesn't contain it.
 *
 * The pick is graded from the `practice/attempt/` response (`correct_answer`,
 * explanation) when it carries one, else from the question detail.
 *
 * The toolbar's Reveal (like the timed mode's time-out) shows the current
 * question's answer and explanation from what the server already sent, and
 * then takes no pick for that question, so a revealed answer is never
 * recorded as an attempt.
 *
 * Settings > Customise (useQuestionBankPreferences) hides the toolbar tools
 * and side panels a student switched off; navigation, the options, Reveal and
 * the explanation always show.
 *
 * Colours come from the theme tokens (bg-card, text-foreground, …) so the
 * page reads correctly in both light and dark themes.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { FormattedText, FormattedOptionText } from "@/components/FormattedText";
import RecallBadge from "@/components/recall/RecallBadge";
import ImageGallery from "@/components/recall/ImageGallery";
import ProvenanceList from "@/components/recall/ProvenanceList";
import QuestionToolbar, { type QuestionState } from "@/components/question/QuestionToolbar";
import QuestionTimer from "@/components/question/QuestionTimer";
import PracticeExamTimer from "@/components/question/PracticeExamTimer";
import RevealExplanation from "@/components/question/RevealExplanation";
import RelatedPanel from "@/components/question/RelatedPYQs";
import { useQuestionBankPreferences } from "@/components/customize/useQuestionBankPreferences";
import {
    answerLetter, errorStatus, examYearChip, isPremiumUser, openInQueue, pickExplanation,
    placeInQueue, retryTimeSpent, upgradeRequiredFeature,
} from "@/components/question/practiceData";
import api, { questionsAPI } from "@/lib/api";
import { Loader2, ChevronDown, ChevronUp, Filter, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useRequireAuth } from "@/lib/hooks/useRequireAuth";
import DroppedByUpscBadge from "@/components/question/DroppedByUpscBadge";

interface QRow {
  id: number;
  question_text?: string;
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  correct_answer?: string;
  explanation?: string;
  effective_explanation?: string | null;
  exam_source?: string;
  page_screenshot?: string | null;
  recall_status?: string;
  year?: number;
  session?: string;
  subject_name?: string;
  topic_name?: string;
  is_image_based?: boolean;
  /** UPSC dropped it from evaluation: shown, never scored. */
  dropped_by_upsc?: boolean;
  ai_explanation?: string;
  ai_mnemonic?: string;
  ai_clinical_pearl?: string;
}

interface Subject { id: number; name: string; }
interface Topic { id: number; name: string; subject_id?: number; }

const MODES: { k: string; label: string; scopes: Array<"year" | "subject" | "topic" | "count"> }[] = [
    { k: "random",         label: "Random",         scopes: ["count"] },
    { k: "year_wise",      label: "Year-wise",      scopes: ["year", "count"] },
    { k: "subject_wise",   label: "Subject-wise",   scopes: ["subject", "count"] },
    { k: "topic_wise",     label: "Topic-wise",     scopes: ["subject", "topic", "count"] },
    { k: "weak_topics",    label: "Weak topics",    scopes: ["count"] },
    { k: "bookmarked",     label: "Bookmarked",     scopes: ["count"] },
    { k: "wrong",          label: "Wrong",          scopes: ["count"] },
    { k: "image_only",     label: "Image-only",     scopes: ["count"] },
    { k: "rapid_revision", label: "Rapid revision", scopes: ["count"] },
    { k: "high_yield",     label: "High yield",     scopes: ["count"] },
    { k: "clinical_cases", label: "Clinical cases", scopes: ["count"] },
    { k: "timed",          label: "Timed mock",     scopes: ["count"] },
    { k: "custom",         label: "Custom",         scopes: ["count"] },
];

const COUNTS = [10, 20, 30, 50];
// UPSC CMS papers in the bank: 2014-2026 (2014-2017 from questions.0049).
const YEARS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014];
const DIFFICULTIES = ["", "easy", "medium", "hard"];

// Shared control styles (theme tokens, readable in light and dark).
const SELECT_CLS = "rounded border border-border bg-background px-2 py-1 text-sm text-foreground";
const CHIP_CLS = "rounded bg-muted px-2 py-0.5 text-xs text-foreground";

function PracticeInner() {
    const router = useRouter();
    const params = useSearchParams();
    const initialMode = params.get("mode") || "random";
    // Current `?id=` (this page keeps it in sync with the open question).
    const initialId = Number(params.get("id")) || null;
    const { user } = useAuth();
    // Practice endpoints (queue, state, attempts) require an account; send
    // logged-out visitors to /login?next=... instead of loading a queue
    // the API will refuse.
    const { ready } = useRequireAuth();
    // Tools the student switched off in Settings > Customise (all shown while loading).
    const { shows } = useQuestionBankPreferences();

    const [mode, setMode] = useState(initialMode);
    const [count, setCount] = useState<number>(30);
    const [year, setYear] = useState<string>("");
    const [subjectId, setSubjectId] = useState<string>("");
    const [topicId, setTopicId] = useState<string>("");
    const [difficulty, setDifficulty] = useState<string>("");
    const [imageOnly, setImageOnly] = useState(false);
    const [aiOnly, setAiOnly] = useState(false);

    const [queue, setQueue] = useState<number[]>([]);
    const [idx, setIdx] = useState(0);
    const [q, setQ] = useState<QRow | null>(null);
    const [qError, setQError] = useState<string | null>(null);
    const [qImages, setQImages] = useState<Array<{ id: number; url?: string | null; file?: string | null; caption?: string | null }>>([]);
    const [eliminated, setEliminated] = useState<string[]>([]);
    const [revealed, setRevealed] = useState(false);
    const [picked, setPicked] = useState<string>("");
    const [loading, setLoading] = useState(true);
    // The queue request failed (shown as an error, not as "no questions").
    const [queueError, setQueueError] = useState(false);
    // Server-reported free plan (queue limited to the curated showcase).
    const [freemium, setFreemium] = useState(false);
    // Bumped by the queue error's Retry button to rebuild the queue.
    const [reloadKey, setReloadKey] = useState(0);
    const [busy, setBusy] = useState(false);
    // A failed save of the current pick; `retryTime` is re-sent on Retry.
    const [submitError, setSubmitError] = useState<{ answer: string; retryTime: number } | null>(null);
    // What the practice/attempt response said about the current pick.
    const [attemptResult, setAttemptResult] = useState<{ key: string; explanation?: string } | null>(null);
    const [showFilters, setShowFilters] = useState(false);
    // The id from the URL when the page opened (a deep link). Consumed by
    // the first queue build.
    const deepLinkRef = useRef<number | null>(initialId);

    // Cached reference data for filter UI.
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [topics, setTopics] = useState<Topic[]>([]);

    useEffect(() => {
        // Best-effort cache — endpoints are public read.
        (async () => {
            try {
                const s = await questionsAPI.getSubjects();
                const sBody: any = s?.data ?? s;
                const sList: Subject[] = (Array.isArray(sBody) ? sBody : sBody?.results || []).map((x: any) => ({ id: x.id, name: x.name }));
                setSubjects(sList);
            } catch { /* tolerant */ }
            try {
                const t = await questionsAPI.getTopics();
                const tBody: any = t?.data ?? t;
                const tList: Topic[] = (Array.isArray(tBody) ? tBody : tBody?.results || []).map((x: any) => ({
                    id: x.id, name: x.name, subject_id: x.subject_id ?? x.subject,
                }));
                setTopics(tList);
            } catch { /* tolerant */ }
        })();
    }, []);

    // Pickers for the current mode.
    const modeSpec = useMemo(() => MODES.find((m) => m.k === mode) || MODES[0], [mode]);
    const filteredTopics = useMemo(
        () => (subjectId ? topics.filter((t) => String(t.subject_id) === String(subjectId)) : topics),
        [topics, subjectId],
    );

    const buildParams = useCallback(() => {
        const p: Record<string, string | number> = { mode, count };
        if (modeSpec.scopes.includes("year") && year) p.year = year;
        if (modeSpec.scopes.includes("subject") && subjectId) p.subject_id = subjectId;
        if (modeSpec.scopes.includes("topic") && topicId) p.topic_id = topicId;
        if (mode === "custom") {
            if (year) p.year = year;
            if (subjectId) p.subject_id = subjectId;
            if (topicId) p.topic_id = topicId;
            if (difficulty) p.difficulty = difficulty;
            if (imageOnly) p.is_image_based = "true";
            if (aiOnly) p.has_ai_enrichment = "true";
        }
        return p;
    }, [mode, count, year, subjectId, topicId, difficulty, imageOnly, aiOnly, modeSpec]);

    // Re-build queue when mode or filter scope changes (or on Retry).
    useEffect(() => {
        if (!ready) return;
        let alive = true;
        setLoading(true);
        setQueueError(false);
        setQueue([]);
        setIdx(0);
        (async () => {
            try {
                const r = await api.get(`/questions/practice_queue/`, { params: buildParams() });
                if (!alive) return;
                const ids: number[] = Array.isArray(r.data?.question_ids) ? r.data.question_ids : [];
                // A deep link opens its question first even when the mode's
                // (random) queue doesn't contain it — previously the page
                // fell back to index 0 and showed an unrelated question.
                // Later rebuilds keep the current question if it's queued.
                const deepLink = deepLinkRef.current;
                deepLinkRef.current = null;
                const placed = placeInQueue(ids, deepLink ?? initialId, deepLink !== null);
                setQueue(placed.ids);
                setIdx(placed.index);
                setFreemium(r.data?.freemium === true);
            } catch (err) {
                if (alive) {
                    // Still open a deep-linked question when the queue fails.
                    const deepLink = deepLinkRef.current;
                    deepLinkRef.current = null;
                    setQueue(deepLink ? [deepLink] : []);
                    setQueueError(true);
                    console.error('[practice] Failed to load practice queue:', err);
                }
            } finally {
                if (alive) setLoading(false);
            }
        })();
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ready, reloadKey, JSON.stringify(buildParams())]);

    // A link to /practice?id=N while this page is open (related PYQs):
    // jump to N, inserting it after the current question when it isn't
    // queued. The page's own replaceState (below) always points `id` at
    // the open question, which this ignores.
    useEffect(() => {
        if (!initialId || loading) return;
        if (queue[idx] === initialId) return;
        const placed = openInQueue(queue, idx, initialId);
        if (placed.ids !== queue) setQueue(placed.ids);
        setIdx(placed.index);
        // Only URL changes should move the queue position (queue / idx are
        // read, not dependencies).
    }, [initialId]);

    const qid = queue[idx];
    // When the current question was shown (time spent feeds study time).
    const shownAt = useRef<number>(Date.now());

    useEffect(() => {
        shownAt.current = Date.now();
        setQError(null);
        if (!qid) { setQ(null); setQImages([]); return; }
        let alive = true;
        (async () => {
            try {
                const r = await api.get(`/questions/${qid}/`);
                if (alive) {
                    setQ(r.data);
                    // Load images so [[img:N]] tokens resolve inline
                    const imgs = r.data?.images || [];
                    setQImages(imgs);
                }
            } catch (err) {
                if (alive) {
                    setQ(null); setQImages([]);
                    const status = errorStatus(err);
                    if (upgradeRequiredFeature(err) || status === 402 || status === 403
                        || (status === 404 && !isPremiumUser(user))) {
                        // Free plan: the detail endpoint only serves the
                        // curated showcase questions (402/403 also opens the
                        // upgrade modal via the api.ts interceptor).
                        setQError("This question is part of the premium bank.");
                    } else if (status === 404) {
                        setQError("This question is no longer available.");
                    } else {
                        setQError("Couldn't load this question. Check your connection and try again.");
                    }
                }
            }
        })();
        setRevealed(false); setPicked(""); setEliminated([]);
        setAttemptResult(null); setSubmitError(null);
        if (typeof window !== "undefined") {
            const u = new URL(window.location.href);
            u.searchParams.set("id", String(qid));
            u.searchParams.set("mode", mode);
            window.history.replaceState({}, "", u.toString());
        }
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [qid, mode]);

    /** Save the pick; `retryTime` (seconds) replaces the measured time on a Retry. */
    const submit = useCallback(async (answer: string, retryTime?: number) => {
        // `q` still holds the previous question until the next one's detail
        // arrives; never record a pick against it.
        if (!q || q.id !== qid) return;
        setPicked(answer);
        setBusy(true);
        const timeSpent = retryTime ?? Math.max(0, Math.round((Date.now() - shownAt.current) / 1000));
        try {
            const r = await api.post(`/questions/${q.id}/practice/attempt/`, {
                answer,
                time_spent: timeSpent,
            });
            // Grade from the server's answer when the response carries it.
            setAttemptResult({ key: answerLetter(r.data?.correct_answer), explanation: pickExplanation(r.data) });
            setRevealed(true);
            setSubmitError(null);
        } catch (err) {
            if (upgradeRequiredFeature(err)) {
                // Premium question on the free plan: the api.ts interceptor
                // opens the upgrade modal; undo the pick instead of
                // reporting a failed save.
                setPicked("");
                setSubmitError(null);
                return;
            }
            // The save failed, but the question detail already carries the
            // answer: reveal it anyway (the options were disabled with no way
            // forward before) and offer a Retry for the save. Without an HTTP
            // response the server may have stored the attempt already, so the
            // retry sends 0 seconds instead of counting the time twice.
            setRevealed(true);
            setSubmitError({ answer, retryTime: retryTimeSpent(err, timeSpent) });
            // eslint-disable-next-line no-console
            console.error('practice attempt failed', err);
        } finally {
            setBusy(false);
        }
    }, [q, qid]);

    const onState = useCallback((s: QuestionState) => {
        setEliminated(s.eliminated || []);
    }, []);

    const opts = useMemo(() => {
        if (!q) return [];
        return [
            { k: "A", v: q.option_a || "" },
            { k: "B", v: q.option_b || "" },
            { k: "C", v: q.option_c || "" },
            { k: "D", v: q.option_d || "" },
        ];
    }, [q]);

    const total = queue.length;
    const showScopePanel = modeSpec.scopes.some((s) => s !== "count") || mode === "custom";
    // The key from the attempt response, else from the question detail.
    const answerKey = attemptResult?.key || answerLetter(q?.correct_answer);
    // Curated explanation, else the effective (admin / AI) one; a blank
    // string no longer hides an explanation that exists.
    const explanationText = attemptResult?.explanation?.trim()
        ? attemptResult.explanation
        : (pickExplanation(q) || undefined);

    // The route layout wraps the page in AppShell, whose .page-container
    // already pads it.
    return (
        <div className="mx-auto max-w-5xl px-4 py-6 [.page-container_&]:p-0 text-foreground">
            <header className="mb-3 flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold">Practice</h1>
                <select value={mode} onChange={(e) => setMode(e.target.value)}
                    aria-label="Practice mode"
                    className={SELECT_CLS}>
                    {MODES.map((m) => <option key={m.k} value={m.k}>{m.label}</option>)}
                </select>
                <select value={String(count)} onChange={(e) => setCount(Number(e.target.value))}
                    aria-label="Number of questions"
                    className={SELECT_CLS}>
                    {COUNTS.map((c) => <option key={c} value={c}>{c} questions</option>)}
                </select>
                {/* Modes whose only scope is the count have nothing to open. */}
                {showScopePanel ? (
                    <button
                        type="button"
                        onClick={() => setShowFilters((s) => !s)}
                        aria-expanded={showFilters}
                        className="inline-flex items-center gap-1 rounded border border-border bg-muted px-2 py-1 text-sm text-foreground hover:bg-muted/70"
                    >
                        <Filter className="h-3.5 w-3.5" />
                        {showFilters ? "Hide" : "Scope"}
                        {showFilters ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    </button>
                ) : null}
                {!loading && !queueError ? (
                    <span className="text-xs text-muted-foreground">{total} {total === 1 ? "question" : "questions"}</span>
                ) : null}
                {mode === "timed" ? (
                    <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-800 dark:text-amber-200">⏱ Timed — 1 min / question</span>
                ) : null}
            </header>

            {showScopePanel && showFilters ? (
                <section className="mb-3 rounded-lg border border-border bg-card p-3">
                    <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
                        {modeSpec.scopes.includes("year") || mode === "custom" ? (
                            <label className="flex flex-col gap-1">
                                <span className="text-xs text-muted-foreground">Year</span>
                                <select value={year} onChange={(e) => setYear(e.target.value)}
                                    className={SELECT_CLS}>
                                    <option value="">Any</option>
                                    {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
                                </select>
                            </label>
                        ) : null}
                        {modeSpec.scopes.includes("subject") || mode === "custom" ? (
                            <label className="flex flex-col gap-1">
                                <span className="text-xs text-muted-foreground">Subject</span>
                                <select value={subjectId} onChange={(e) => { setSubjectId(e.target.value); setTopicId(""); }}
                                    className={SELECT_CLS}>
                                    <option value="">Any</option>
                                    {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                                </select>
                            </label>
                        ) : null}
                        {(modeSpec.scopes.includes("topic") || mode === "custom") ? (
                            <label className="flex flex-col gap-1">
                                <span className="text-xs text-muted-foreground">Topic</span>
                                <select value={topicId} onChange={(e) => setTopicId(e.target.value)}
                                    className={SELECT_CLS}>
                                    <option value="">Any</option>
                                    {filteredTopics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                                </select>
                            </label>
                        ) : null}
                        {mode === "custom" ? (
                            <>
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-muted-foreground">Difficulty</span>
                                    <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}
                                        className={SELECT_CLS}>
                                        {DIFFICULTIES.map((d) => <option key={d} value={d}>{d || "Any"}</option>)}
                                    </select>
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                    <input type="checkbox" checked={imageOnly} onChange={(e) => setImageOnly(e.target.checked)} />
                                    Image-only
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                    <input type="checkbox" checked={aiOnly} onChange={(e) => setAiOnly(e.target.checked)} />
                                    Has AI explanation
                                </label>
                            </>
                        ) : null}
                    </div>
                </section>
            ) : null}

            {/* Whole-exam timer for `timed` mode — auto-pause-aware per-question timer is below. */}
            {mode === "timed" && total > 0 ? (
                <PracticeExamTimer totalSeconds={total * 60} onExpire={() => {
                    // Auto-reveal current Q when time runs out.
                    setRevealed(true);
                }} />
            ) : null}
            {qid ? <QuestionTimer questionId={qid} /> : null}

            {q ? (
                <article className="rounded-lg border border-border bg-card p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                        <RecallBadge status={q.recall_status} />
                        {/* Was hard-coded "NEET PG" for every question. */}
                        {q.year ? <span className={CHIP_CLS}>{examYearChip(q.exam_source, q.year)}</span> : null}
                        {q.session ? <span className={CHIP_CLS}>{q.session}</span> : null}
                        {q.subject_name ? <span className={CHIP_CLS}>{q.subject_name}</span> : null}
                        {q.topic_name ? <span className="rounded bg-muted/60 px-2 py-0.5 text-xs text-muted-foreground">{q.topic_name}</span> : null}
                        {q.is_image_based ? <span className="rounded bg-sky-600 px-2 py-0.5 text-xs text-white">Image</span> : null}
                        {q.dropped_by_upsc ? <DroppedByUpscBadge /> : null}
                    </div>

                    <div className="my-3">
                        <FormattedText text={q.question_text || ""} images={qImages} />
                    </div>

                    {q.id ? (
                        <ImageGallery questionId={q.id} fallbackImage={q.page_screenshot} />
                    ) : null}

                    {submitError ? (
                        <div
                            role="alert"
                            className="mt-3 flex flex-col gap-2 rounded border border-amber-500/60 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 sm:flex-row sm:items-center dark:text-amber-100"
                        >
                            <span className="flex-1">
                                Your answer couldn&apos;t be saved to your progress. Check your connection and try again.
                            </span>
                            <Button
                                size="sm"
                                variant="outline"
                                className="shrink-0 text-foreground"
                                disabled={busy}
                                onClick={() => { void submit(submitError.answer, submitError.retryTime); }}
                            >
                                <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Retry
                            </Button>
                        </div>
                    ) : null}

                    <div className="mt-4 grid gap-2 sm:grid-cols-2">
                        {opts.map((o) => {
                            const isCorrect = answerKey === o.k;
                            // Struck-out options only while the strike tool shows (it is the way back).
                            const isElim = shows("strike") && eliminated.includes(o.k);
                            const wasPicked = picked === o.k;
                            // Without an answer key the pick can't be marked wrong.
                            const pickedCls = !answerKey
                                ? (wasPicked ? "border-primary bg-primary/5" : "border-border")
                                : isCorrect ? "border-emerald-500 bg-emerald-500/10"
                                : wasPicked ? "border-rose-500 bg-rose-500/10" : "border-border";
                            return (
                                <button
                                    key={o.k}
                                    onClick={() => submit(o.k)}
                                    // A revealed answer (Reveal, the timed mode's time-out) takes no pick.
                                    disabled={busy || !!picked || revealed || q.id !== qid}
                                    className={`flex w-full items-start gap-3 rounded border p-3 text-left
                                                ${isElim ? "opacity-40 line-through" : ""}
                                                ${picked || revealed ? pickedCls : "border-border hover:bg-muted/60"}`}
                                >
                                    <span className="rounded bg-muted px-2 py-0.5 text-sm font-bold">{o.k}</span>
                                    <FormattedOptionText text={o.v} images={qImages} />
                                </button>
                            );
                        })}
                    </div>

                    {revealed && !answerKey ? (
                        <p className="mt-3 rounded border border-border bg-muted/60 px-3 py-2 text-sm text-muted-foreground">
                            No answer key is available for this question yet.
                        </p>
                    ) : null}

                    <RevealExplanation
                        questionId={q.id}
                        fallbackExplanation={explanationText}
                        open={revealed}
                        images={qImages}
                    />

                    <div className="mt-4">
                        <QuestionToolbar
                            questionId={q.id}
                            index={idx}
                            total={total}
                            onPrev={() => setIdx(Math.max(0, idx - 1))}
                            onNext={() => setIdx(Math.min(total - 1, idx + 1))}
                            onJump={(i) => setIdx(i)}
                            revealed={revealed}
                            onReveal={() => setRevealed(true)}
                            shows={shows}
                            onEliminationChange={setEliminated}
                            onStateChange={onState}
                        />
                    </div>

                    {shows("provenance") || shows("related-pyqs") || shows("related-topics") ? (
                        <div className="mt-4 grid gap-4 md:grid-cols-2">
                            {shows("provenance") ? (
                                <section>
                                    <h3 className="mb-2 text-sm font-semibold text-foreground">Provenance</h3>
                                    <ProvenanceList questionId={q.id} />
                                </section>
                            ) : null}
                            {shows("related-pyqs") ? (
                                <section>
                                    <h3 className="mb-2 text-sm font-semibold text-foreground">Related PYQs</h3>
                                    <RelatedPanel questionId={q.id} kind="related_pyqs" />
                                </section>
                            ) : null}
                            {shows("related-topics") ? (
                                <section>
                                    <h3 className="mb-2 text-sm font-semibold text-foreground">Related topics</h3>
                                    <RelatedPanel questionId={q.id} kind="related_topics" />
                                </section>
                            ) : null}
                        </div>
                    ) : null}
                </article>
            ) : loading ? (
                <p className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Building queue…
                </p>
            ) : queueError && total === 0 ? (
                // The queue request failed: say so instead of "no questions"
                // plus an upgrade pitch. (A deep-linked question still opens.)
                <div role="alert" className="rounded-lg border border-border bg-card p-6 text-center">
                    <p className="mb-3 text-sm text-foreground">
                        Couldn&apos;t load questions. Check your connection and try again.
                    </p>
                    <Button size="sm" onClick={() => setReloadKey((k) => k + 1)}>
                        <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Retry
                    </Button>
                </div>
            ) : qError && total > 0 ? (
                <div className="rounded-lg border border-border bg-card p-6 text-center">
                    <p className="mb-3 text-sm text-foreground">{qError}</p>
                    <div className="flex flex-wrap justify-center gap-2">
                        {idx > 0 ? (
                            <Button onClick={() => setIdx(idx - 1)} variant="outline" size="sm">‹ Previous</Button>
                        ) : null}
                        {idx < total - 1 ? (
                            <Button onClick={() => setIdx(idx + 1)} variant="default" size="sm">Next question ›</Button>
                        ) : null}
                        {!isPremiumUser(user) ? (
                            <Button onClick={() => router.push('/subscription')} variant="outline" size="sm">
                                Upgrade for Full Access
                            </Button>
                        ) : null}
                    </div>
                </div>
            ) : total === 0 && !loading ? (
                <div className="text-center py-12">
                    <p className="text-muted-foreground mb-3">No questions available for this mode.</p>
                    {user ? (
                        <div className="space-y-3">
                            <p className="text-xs text-muted-foreground">
                                {freemium ? (
                                    <>
                                        Free users see a curated set of questions per year.
                                        {mode !== 'random' ? <> Try switching to <strong>Random</strong> mode or a different year.</> : null}
                                    </>
                                ) : (
                                    "Try adjusting your filters or switching to a different mode."
                                )}
                            </p>
                            {mode !== 'random' || freemium ? (
                                <div className="flex flex-wrap justify-center gap-2">
                                    {mode !== 'random' ? (
                                        <Button onClick={() => setMode('random')} variant="default" size="sm">
                                            Switch to Random Mode
                                        </Button>
                                    ) : null}
                                    {freemium ? (
                                        <Button onClick={() => router.push('/subscription')} variant="outline" size="sm">
                                            Upgrade for Full Access
                                        </Button>
                                    ) : null}
                                </div>
                            ) : null}
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground mb-4">
                            Sign in to access practice questions and track your progress.
                        </p>
                    )}
                    {!user && (
                        <Button onClick={() => router.push('/login')} variant="default" size="sm">
                            Sign In to Continue
                        </Button>
                    )}
                </div>
            ) : (
                // Queue loaded, the current question's detail is still on its
                // way (this used to flash "No questions available").
                <p className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading question…
                </p>
            )}
            {/* The "Press Esc to clear reveals" hint was removed: no Esc
                handler exists on this page, so it advertised a shortcut that
                did nothing (and showed under empty / error states too). */}
        </div>
    );
}

export default function PracticePage() {
    return (
        <Suspense fallback={<p className="p-6 [.page-container_&]:px-0 text-muted-foreground">Loading…</p>}>
            <PracticeInner />
        </Suspense>
    );
}
