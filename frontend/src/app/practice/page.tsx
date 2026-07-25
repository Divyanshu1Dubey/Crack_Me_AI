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
 * Backend dispatcher: `/api/questions/practice_queue/?mode=...&count=...
 * &year=...&subject_id=...&topic_id=...&difficulty=...&is_image_based=...
 * &has_ai_enrichment=...`
 */
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { FormattedText } from "@/components/FormattedText";
import RecallBadge from "@/components/recall/RecallBadge";
import ImageGallery from "@/components/recall/ImageGallery";
import ProvenanceList from "@/components/recall/ProvenanceList";
import QuestionToolbar, { type QuestionState } from "@/components/question/QuestionToolbar";
import QuestionTimer from "@/components/question/QuestionTimer";
import PracticeExamTimer from "@/components/question/PracticeExamTimer";
import RevealExplanation from "@/components/question/RevealExplanation";
import RelatedPanel from "@/components/question/RelatedPYQs";
import api, { questionsAPI } from "@/lib/api";
import { Loader2, Settings2, ChevronDown, ChevronUp, Filter, Shuffle } from "lucide-react";

interface QRow {
  id: number;
  question_text?: string;
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  correct_answer?: string;
  explanation?: string;
  page_screenshot?: string | null;
  recall_status?: string;
  year?: number;
  session?: string;
  subject_name?: string;
  topic_name?: string;
  is_image_based?: boolean;
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
const YEARS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018];
const DIFFICULTIES = ["", "easy", "medium", "hard"];

function PracticeInner() {
    const router = useRouter();
    const params = useSearchParams();
    const initialMode = params.get("mode") || "random";
    const initialId = Number(params.get("id")) || null;

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
    const [eliminated, setEliminated] = useState<string[]>([]);
    const [revealed, setRevealed] = useState(false);
    const [picked, setPicked] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [showFilters, setShowFilters] = useState(false);

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

    // Re-build queue when mode or filter scope changes.
    useEffect(() => {
        let alive = true;
        setLoading(true);
        setQueue([]);
        setIdx(0);
        (async () => {
            try {
                const r = await api.get(`/api/questions/practice_queue/`, { params: buildParams() });
                if (!alive) return;
                const ids: number[] = r.data?.question_ids || [];
                setQueue(ids);
                setIdx(initialId ? Math.max(0, ids.indexOf(initialId)) : 0);
            } catch {
                if (alive) setQueue([]);
            } finally {
                if (alive) setLoading(false);
            }
        })();
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [JSON.stringify(buildParams())]);

    const qid = queue[idx];

    useEffect(() => {
        if (!qid) { setQ(null); return; }
        let alive = true;
        (async () => {
            try {
                const r = await api.get(`/api/questions/${qid}/`);
                if (alive) setQ(r.data);
            } catch {
                if (alive) setQ(null);
            }
        })();
        setRevealed(false); setPicked(""); setEliminated([]);
        if (typeof window !== "undefined") {
            const u = new URL(window.location.href);
            u.searchParams.set("id", String(qid));
            u.searchParams.set("mode", mode);
            window.history.replaceState({}, "", u.toString());
        }
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [qid, mode]);

    const submit = useCallback(async (answer: string) => {
        if (!q) return;
        setPicked(answer);
        setBusy(true);
        try {
            await api.post(`/api/questions/${q.id}/practice/attempt/`, { answer });
            setRevealed(true);
        } catch {/* swallow */} finally { setBusy(false); }
    }, [q]);

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

    return (
        <main className="mx-auto max-w-5xl px-4 py-6 text-slate-100">
            <header className="mb-3 flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold">Practice</h1>
                <select value={mode} onChange={(e) => setMode(e.target.value)}
                    className="rounded bg-slate-800 px-2 py-1 text-sm">
                    {MODES.map((m) => <option key={m.k} value={m.k}>{m.label}</option>)}
                </select>
                <select value={String(count)} onChange={(e) => setCount(Number(e.target.value))}
                    className="rounded bg-slate-800 px-2 py-1 text-sm">
                    {COUNTS.map((c) => <option key={c} value={c}>{c} questions</option>)}
                </select>
                <button
                    type="button"
                    onClick={() => setShowFilters((s) => !s)}
                    className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-sm hover:bg-slate-700"
                >
                    <Filter className="h-3.5 w-3.5" />
                    {showFilters ? "Hide" : "Scope"}
                    {showFilters ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
                <span className="text-xs text-slate-400">{total} questions</span>
                {mode === "timed" ? (
                    <span className="rounded bg-amber-700/60 px-2 py-0.5 text-xs">⏱ Timed — 1 min / question</span>
                ) : null}
            </header>

            {showScopePanel && showFilters ? (
                <section className="mb-3 rounded-lg border border-slate-700/40 bg-slate-900/40 p-3">
                    <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
                        {modeSpec.scopes.includes("year") || mode === "custom" ? (
                            <label className="flex flex-col gap-1">
                                <span className="text-xs text-slate-400">Year</span>
                                <select value={year} onChange={(e) => setYear(e.target.value)}
                                    className="rounded bg-slate-800 px-2 py-1 text-sm">
                                    <option value="">Any</option>
                                    {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
                                </select>
                            </label>
                        ) : null}
                        {modeSpec.scopes.includes("subject") || mode === "custom" ? (
                            <label className="flex flex-col gap-1">
                                <span className="text-xs text-slate-400">Subject</span>
                                <select value={subjectId} onChange={(e) => { setSubjectId(e.target.value); setTopicId(""); }}
                                    className="rounded bg-slate-800 px-2 py-1 text-sm">
                                    <option value="">Any</option>
                                    {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                                </select>
                            </label>
                        ) : null}
                        {(modeSpec.scopes.includes("topic") || mode === "custom") ? (
                            <label className="flex flex-col gap-1">
                                <span className="text-xs text-slate-400">Topic</span>
                                <select value={topicId} onChange={(e) => setTopicId(e.target.value)}
                                    className="rounded bg-slate-800 px-2 py-1 text-sm">
                                    <option value="">Any</option>
                                    {filteredTopics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                                </select>
                            </label>
                        ) : null}
                        {mode === "custom" ? (
                            <>
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-slate-400">Difficulty</span>
                                    <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}
                                        className="rounded bg-slate-800 px-2 py-1 text-sm">
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
                <article className="rounded-lg border border-slate-700/40 bg-slate-900/40 p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                        <RecallBadge status={q.recall_status} />
                        {q.year ? <span className="rounded bg-slate-700/60 px-2 py-0.5 text-xs">NEET PG {q.year}</span> : null}
                        {q.session ? <span className="rounded bg-slate-700/60 px-2 py-0.5 text-xs">{q.session}</span> : null}
                        {q.subject_name ? <span className="rounded bg-slate-700/60 px-2 py-0.5 text-xs">{q.subject_name}</span> : null}
                        {q.topic_name ? <span className="rounded bg-slate-700/40 px-2 py-0.5 text-xs">{q.topic_name}</span> : null}
                        {q.is_image_based ? <span className="rounded bg-sky-500/70 px-2 py-0.5 text-xs text-white">Image</span> : null}
                    </div>

                    <div className="my-3">
                        <FormattedText text={q.question_text || ""} />
                    </div>

                    {q.id ? (
                        <ImageGallery questionId={q.id} fallbackImage={q.page_screenshot} />
                    ) : null}

                    <div className="mt-4 grid gap-2 sm:grid-cols-2">
                        {opts.map((o) => {
                            const isCorrect = (q.correct_answer || "").toUpperCase() === o.k;
                            const isElim = eliminated.includes(o.k);
                            const wasPicked = picked === o.k;
                            return (
                                <button
                                    key={o.k}
                                    onClick={() => submit(o.k)}
                                    disabled={busy || !!picked}
                                    className={`flex w-full items-start gap-3 rounded border p-3 text-left
                                                ${isElim ? "opacity-40 line-through" : ""}
                                                ${picked ? (isCorrect ? "border-emerald-500 bg-emerald-900/20" :
                                                            wasPicked ? "border-rose-500 bg-rose-900/20" : "border-slate-700/40") : "border-slate-700/40 hover:bg-slate-800/60"}`}
                                >
                                    <span className="rounded bg-slate-700/60 px-2 py-0.5 text-sm font-bold">{o.k}</span>
                                    <FormattedText text={o.v} />
                                </button>
                            );
                        })}
                    </div>

                    <RevealExplanation
                        questionId={q.id}
                        fallbackExplanation={q.explanation}
                        open={revealed}
                    />

                    <div className="mt-4">
                        <QuestionToolbar
                            questionId={q.id}
                            index={idx}
                            total={total}
                            onPrev={() => setIdx(Math.max(0, idx - 1))}
                            onNext={() => setIdx(Math.min(total - 1, idx + 1))}
                            onJump={(i) => setIdx(i)}
                            onEliminationChange={setEliminated}
                            onStateChange={onState}
                        />
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                        <section>
                            <h3 className="mb-2 text-sm font-semibold text-slate-300">Provenance</h3>
                            <ProvenanceList questionId={q.id} />
                        </section>
                        <section>
                            <h3 className="mb-2 text-sm font-semibold text-slate-300">Related PYQs</h3>
                            <RelatedPanel questionId={q.id} kind="related_pyqs" />
                        </section>
                        <section>
                            <h3 className="mb-2 text-sm font-semibold text-slate-300">Related topics</h3>
                            <RelatedPanel questionId={q.id} kind="related_topics" />
                        </section>
                    </div>
                </article>
            ) : loading ? (
                <p className="flex items-center gap-2 text-slate-400">
                    <Loader2 className="h-4 w-4 animate-spin" /> Building queue…
                </p>
            ) : (
                <p className="text-slate-400">No questions for this mode yet. Try another mode.</p>
            )}

            <p className="mt-6 text-center text-xs text-slate-500">
                Press <kbd className="rounded bg-slate-800 px-1">Esc</kbd> to clear reveals.
            </p>
        </main>
    );
}

export default function PracticePage() {
    return (
        <Suspense fallback={<p className="p-6 text-slate-400">Loading…</p>}>
            <PracticeInner />
        </Suspense>
    );
}
