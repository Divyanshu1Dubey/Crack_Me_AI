"use client";
/**
 * AiTutorPanel — Phase-6 AI Tutor.
 *
 * Wraps `aiAPI.explainQuestion(...)` and renders:
 *   - Custom prompt textarea (optional override — defaults to "Explain
 *     why the correct answer is right")
 *   - Quick-prompt chips (Why correct? / Mnemonic / Clinical pearl /
 *     Differential / Workup) — pre-fill the textarea
 *   - Streaming-ish reveal: chunks the explanation into paragraphs and
 *     progressively renders them so the user sees output arrive instead
 *     of waiting for the full response. (True token streaming requires
 *     server-side support; the round-robin currently returns the full
 *     body, so we approximate with progressive paragraph render.)
 *   - "Cached" badge + relative timestamp when the backend returned
 *     `cached: true` (24h TTL).
 *   - "Stop" button to abort the in-flight request via AbortController.
 *   - Retry on error with last prompt preserved.
 *
 * Backend contract (ai_engine.views.ExplainQuestionView):
 *   POST /api/ai/explain-question/<id>/
 *     body: { selected_answer?, question_text?, subject?, topic?,
 *             prompt?, force_regenerate? }
 *   resp: { explanation: <markdown>, cached: bool,
 *           question_id: int, ai_model?: str, ai_generated_at?: ISO }
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { aiAPI } from "@/lib/api";
import { FormattedText } from "@/components/FormattedText";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    AlertTriangle, Brain, Loader2, Sparkles, Square, Clock,
    RotateCcw, Send,
} from "lucide-react";

const QUICK_PROMPTS: Array<{ id: string; label: string; text: string }> = [
    { id: "why", label: "Why correct?", text: "Explain why the correct answer is right and the distractors are wrong." },
    { id: "mnem", label: "Mnemonic", text: "Give me a memorable mnemonic for the underlying concept." },
    { id: "pearl", label: "Clinical pearl", text: "Highlight a high-yield clinical pearl associated with this question." },
    { id: "diff", label: "Differential", text: "Build a differential diagnosis relevant to this case." },
    { id: "workup", label: "Workup", text: "Outline the next-step workup and management." },
];

function relativeAge(iso: string | undefined | null): string {
    if (!iso) return "";
    const t = Date.parse(iso);
    if (isNaN(t)) return "";
    const dt = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (dt < 60) return `${dt}s ago`;
    if (dt < 3600) return `${Math.round(dt / 60)}m ago`;
    if (dt < 86400) return `${Math.round(dt / 3600)}h ago`;
    return `${Math.round(dt / 86400)}d ago`;
}

interface AiTutorPanelProps {
    questionId: number;
    questionText?: string;
    correctAnswer?: string;
    subject?: string | null;
    topic?: string | null;
    selectedAnswer?: string | null;
}

export default function AiTutorPanel({
    questionId, questionText, correctAnswer,
    subject, topic, selectedAnswer,
}: AiTutorPanelProps) {
    const [prompt, setPrompt] = useState<string>("");
    const [activeChip, setActiveChip] = useState<string | null>(null);
    const [explanation, setExplanation] = useState<string>("");
    const [revealedChars, setRevealedChars] = useState<number>(0);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [cached, setCached] = useState<boolean>(false);
    const [aiModel, setAiModel] = useState<string | null>(null);
    const [aiGeneratedAt, setAiGeneratedAt] = useState<string | null>(null);

    const abortRef = useRef<AbortController | null>(null);
    const revealTimerRef = useRef<number | null>(null);

    // Reset state when the question changes so we never show stale AI
    // output for a different question.
    useEffect(() => {
        setPrompt("");
        setActiveChip(null);
        setExplanation("");
        setRevealedChars(0);
        setLoading(false);
        setError(null);
        setCached(false);
        setAiModel(null);
        setAiGeneratedAt(null);
        if (abortRef.current) { try { abortRef.current.abort(); } catch {} abortRef.current = null; }
        if (revealTimerRef.current) { window.clearInterval(revealTimerRef.current); revealTimerRef.current = null; }
    }, [questionId]);

    // Auto-stop the reveal ticker once we've shown the whole body.
    useEffect(() => {
        if (!loading && revealedChars >= explanation.length && revealTimerRef.current) {
            window.clearInterval(revealTimerRef.current);
            revealTimerRef.current = null;
        }
    }, [loading, revealedChars, explanation.length]);

    // Cleanup on unmount.
    useEffect(() => () => {
        if (abortRef.current) try { abortRef.current.abort(); } catch {}
        if (revealTimerRef.current) window.clearInterval(revealTimerRef.current);
    }, []);

    const pickChip = useCallback((chipId: string) => {
        const chip = QUICK_PROMPTS.find((c) => c.id === chipId);
        if (!chip) return;
        setActiveChip(chipId);
        setPrompt(chip.text);
    }, []);

    const requestExplanation = useCallback(async (override?: { prompt?: string; forceRegenerate?: boolean }) => {
        if (loading) return;
        setLoading(true);
        setError(null);
        setExplanation("");
        setRevealedChars(0);

        const ctrl = new AbortController();
        abortRef.current = ctrl;

        const payload: Record<string, unknown> = {
            selected_answer: selectedAnswer || "",
            question_text: questionText || "",
            correct_answer: correctAnswer || "",
            subject: subject || "",
            topic: topic || "",
        };
        if (override?.prompt) payload.prompt = override.prompt;
        else if (prompt) payload.prompt = prompt;
        if (override?.forceRegenerate) payload.force_regenerate = true;

        try {
            const r: any = await aiAPI.explainQuestion(questionId, payload, { signal: ctrl.signal });
            const text = (r?.explanation ?? r?.text ?? r?.markdown ?? "") as string;
            setCached(!!r?.cached);
            setAiModel(r?.ai_model ?? null);
            setAiGeneratedAt(r?.ai_generated_at ?? null);
            setExplanation(text);
            // Progressive reveal — ~30 chars per 30ms tick → ~1000 chars/s.
            if (revealTimerRef.current) window.clearInterval(revealTimerRef.current);
            revealTimerRef.current = window.setInterval(() => {
                setRevealedChars((c) => Math.min(text.length, c + 24));
            }, 30);
        } catch (e: any) {
            if (e?.name === "CanceledError" || e?.code === "ERR_CANCELED") {
                // user-initiated stop — silent
            } else {
                setError(e?.response?.data?.error || e?.message || "AI Tutor is unavailable right now");
            }
        } finally {
            setLoading(false);
            abortRef.current = null;
        }
    }, [questionId, questionText, correctAnswer, subject, topic, selectedAnswer, prompt, loading]);

    const stop = useCallback(() => {
        try { abortRef.current?.abort(); } catch {}
        if (revealTimerRef.current) {
            window.clearInterval(revealTimerRef.current);
            revealTimerRef.current = null;
            // Snap to fully revealed so the user sees what arrived.
            setRevealedChars(explanation.length);
        }
    }, [explanation.length]);

    const visible = useMemo(
        () => explanation.slice(0, revealedChars),
        [explanation, revealedChars],
    );

    return (
        <div className="bg-gradient-to-br from-violet-50 via-white to-fuchsia-50 rounded-2xl border border-violet-100 shadow-sm overflow-hidden">
            <div className="px-4 py-3 flex items-center justify-between border-b border-violet-100/60">
                <span className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-violet-600" />
                    <span className="text-sm font-bold text-slate-800">AI Tutor</span>
                    {cached ? (
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-medium border-emerald-300 text-emerald-700 bg-emerald-50">
                            <Clock className="w-3 h-3 mr-1" /> Cached{aiGeneratedAt ? ` · ${relativeAge(aiGeneratedAt)}` : ""}
                        </Badge>
                    ) : null}
                    {aiModel ? (
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-medium border-slate-200 text-slate-600 bg-white/60">
                            {aiModel}
                        </Badge>
                    ) : null}
                </span>
            </div>

            <div className="px-4 pb-4 space-y-3">
                {/* Quick-prompt chips */}
                <div className="flex flex-wrap gap-1.5 pt-3">
                    {QUICK_PROMPTS.map((c) => (
                        <button
                            key={c.id}
                            type="button"
                            onClick={() => pickChip(c.id)}
                            disabled={loading}
                            className={`text-[11px] px-2 py-1 rounded-full border transition-colors
                                        ${activeChip === c.id
                                            ? "bg-violet-600 text-white border-violet-600"
                                            : "bg-white text-slate-700 border-slate-200 hover:border-violet-300"}`}
                        >
                            {c.label}
                        </button>
                    ))}
                </div>

                {/* Custom-prompt textarea */}
                <textarea
                    value={prompt}
                    onChange={(e) => { setPrompt(e.target.value); setActiveChip(null); }}
                    rows={2}
                    placeholder="Optional: ask anything — 'What's the second-line agent?', 'Why is B wrong?'…"
                    disabled={loading}
                    className="w-full resize-none rounded-lg border border-violet-200 bg-white px-3 py-2 text-xs leading-relaxed text-slate-800 placeholder:text-slate-400 focus:border-violet-400 focus:outline-none"
                />

                {/* Action row */}
                <div className="flex items-center gap-2">
                    <Button
                        onClick={() => requestExplanation()}
                        disabled={loading}
                        size="sm"
                        className="flex-1 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white font-semibold"
                        data-testid="ai-tutor-submit"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Thinking…
                            </>
                        ) : (
                            <>
                                <Send className="w-3.5 h-3.5 mr-2" />
                                {explanation ? "Re-run with prompt" : "Explain with AI"}
                            </>
                        )}
                    </Button>
                    {loading ? (
                        <Button onClick={stop} size="sm" variant="outline" className="border-rose-200 text-rose-700 hover:bg-rose-50">
                            <Square className="w-3.5 h-3.5 mr-1" /> Stop
                        </Button>
                    ) : explanation ? (
                        <Button
                            onClick={() => requestExplanation({ forceRegenerate: true })}
                            size="sm"
                            variant="outline"
                            className="border-violet-200 text-violet-700 hover:bg-violet-50"
                            data-testid="ai-tutor-regenerate"
                        >
                            <RotateCcw className="w-3.5 h-3.5 mr-1" /> Regenerate
                        </Button>
                    ) : null}
                </div>

                {error ? (
                    <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700 flex items-start gap-2" role="alert">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        <div className="flex-1">
                            <p>{error}</p>
                            <button
                                type="button"
                                onClick={() => requestExplanation()}
                                className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-rose-700 hover:underline"
                            >
                                <RotateCcw className="w-3 h-3" /> Retry
                            </button>
                        </div>
                    </div>
                ) : null}

                {explanation ? (
                    <div
                        className="rounded-lg border border-violet-100 bg-white/70 p-3 prose prose-sm max-w-none text-slate-700 text-[13px] leading-relaxed"
                        data-testid="ai-tutor-output"
                    >
                        <FormattedText text={visible} />
                        {revealedChars < explanation.length ? (
                            <span className="inline-block w-1.5 h-3.5 align-middle bg-violet-500 ml-0.5 animate-pulse" aria-hidden />
                        ) : null}
                    </div>
                ) : !loading && !error ? (
                    <p className="text-xs text-slate-500">
                        Pick a quick prompt or write your own, then hit <span className="font-semibold">Explain with AI</span>.
                    </p>
                ) : null}
            </div>
        </div>
    );
}
