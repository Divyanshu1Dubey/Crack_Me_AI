/**
 * /generate — AI Question Generator.
 *
 * Track-aware (NEET PG / INI-CET / CMS / USMLE / FMGE) MCQ generator.
 * This page is a thin orchestrator: it wires the `useGenerate` state
 * machine + `useExamTrack` + `useTokenWallet` and renders the new
 * composer components extracted under `components/QuestionComposer/`.
 *
 * Why split this: the original page was ~944 lines doing presentation,
 * state, side-effects, and progress-bar animation all in one file.
 * After this refactor every concern lives in a focused module:
 *   - State + AI call:  `useGenerate`
 *   - Per-track config: `constants.ts`
 *   - Composers + cards: `components/QuestionComposer/*`
 *   - Token balance:    `hooks/useTokenWallet`
 */
'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Coins } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { useAuth } from '@/lib/auth';
import { useExamTrack } from '@/components/ExamTrackProvider';
import { questionsAPI } from '@/lib/api';
import {
  FALLBACK_SUBJECTS_BY_TRACK,
  GenerateControls,
  GenerateEmptyState,
  GenerateHero,
  GenerateResultsHeader,
  QuestionCard,
  ScoreCard,
  TRACK_META,
  useGenerate,
} from '@/components/QuestionComposer';
import type { ComposerSubject, Difficulty } from '@/components/QuestionComposer';
import { useTokenWallet } from '@/hooks/useTokenWallet';

export default function GeneratePage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const { activeTrack, hydrated } = useExamTrack();
    const router = useRouter();
    const [subjects, setSubjects] = useState<ComposerSubject[]>([]);
    // Track the user's explicit pick separately so we can derive
    // `selectedSubject` against `activeTrack` without setState-in-effect.
    const [userPickedSubject, setUserPickedSubject] = useState<string | null>(null);
    const [topic, setTopic] = useState('');
    const [difficulty, setDifficulty] = useState<Difficulty>('medium');
    const [count, setCount] = useState(5);

    const gen = useGenerate();
    const { wallet } = useTokenWallet();

    // Auth gate.
    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    // Track-aware subject fetch. On a track change we invalidate the
    // user's prior pick so the derived `selectedSubject` falls back to
    // the new track's default.
    useEffect(() => {
        if (!isAuthenticated || !hydrated) return;
        let cancelled = false;
        questionsAPI.getSubjects({ exam_type: activeTrack })
            .then(res => {
                if (cancelled) return;
                const list = res.data?.results || res.data;
                if (Array.isArray(list) && list.length > 0) {
                    setSubjects(list);
                }
            })
            .catch(() => { /* keep fallback list */ });
        return () => { cancelled = true; };
    }, [isAuthenticated, hydrated, activeTrack]);

    // Derived subject — no setState-in-effect. If the user has explicitly
    // picked a subject, use that; otherwise use the active track's default.
    // When the track changes, the explicit pick is reset by the
    // user-facing onSubjectChange handler (or by switching tracks).
    const selectedSubject = useMemo(() => {
        if (userPickedSubject) return userPickedSubject;
        const meta = TRACK_META[activeTrack] || TRACK_META.cms;
        return meta.defaultSubject;
    }, [userPickedSubject, activeTrack]);

    const handleSubjectChange = useCallback((s: string) => {
        setUserPickedSubject(s);
    }, []);

    const subjectOptions = useMemo(() => {
        if (subjects.length > 0) return subjects.map(s => s.name);
        return FALLBACK_SUBJECTS_BY_TRACK[activeTrack] || FALLBACK_SUBJECTS_BY_TRACK.cms;
    }, [subjects, activeTrack]);

    const trackMeta = TRACK_META[activeTrack] || TRACK_META.cms;

    const handleGenerate = () => gen.generate({
        subject: selectedSubject,
        topic: topic || undefined,
        difficulty,
        count,
    });

    if (authLoading || !hydrated) return null;

    // Score derived state.
    const answeredCount = Object.keys(gen.selectedAnswers).length;
    const correctCount = Object.entries(gen.selectedAnswers).filter(
        ([idx, ans]) => ans === gen.questions[Number(idx)]?.correct_answer,
    ).length;
    const quizComplete = gen.questions.length > 0 && answeredCount === gen.questions.length;

    // Surplus-token hint for the cost line (purely informational).
    const insufficientTokens = wallet
        ? wallet.balance !== undefined && wallet.balance < count
        : false;

    return (
        <>
            <Sidebar />
            <div className="main-content">
                <Header />
                <main className="page-container p-6 md:p-8">
                    <div className="max-w-5xl mx-auto space-y-6">
                        <GenerateHero trackMeta={trackMeta} />

                        {insufficientTokens && (
                            <div className="flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
                                <Coins className="h-4 w-4 mt-0.5 shrink-0" />
                                <span>
                                    You have {wallet?.balance ?? 0} tokens but this quiz costs {count}.
                                    Generation will still run, but the AI explanation step may exhaust your quota.
                                </span>
                            </div>
                        )}

                        <GenerateControls
                            subjectOptions={subjectOptions}
                            selectedSubject={selectedSubject}
                            onSubjectChange={handleSubjectChange}
                            topic={topic}
                            onTopicChange={setTopic}
                            difficulty={difficulty}
                            onDifficultyChange={setDifficulty}
                            count={count}
                            onCountChange={setCount}
                            generating={gen.generating}
                            progress={gen.progress}
                            onGenerate={handleGenerate}
                        />

                        {gen.errorBanner && (
                            <div className="flex items-start gap-3 rounded-lg border border-red-500/40 bg-red-500/10 p-4">
                                <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
                                <div className="text-sm text-red-700 dark:text-red-300">{gen.errorBanner}</div>
                            </div>
                        )}

                        {gen.questions.length > 0 && (
                            <GenerateResultsHeader
                                total={gen.questions.length}
                                answeredCount={answeredCount}
                                regenerating={gen.generating}
                                onRegenerate={handleGenerate}
                            />
                        )}

                        {quizComplete && (
                            <ScoreCard correctCount={correctCount} total={gen.questions.length} />
                        )}

                        <div className="space-y-4">
                            {gen.questions.map((q, idx) => (
                                <QuestionCard
                                    key={idx}
                                    index={idx}
                                    question={q}
                                    selectedAnswer={gen.selectedAnswers[idx]}
                                    showExplanation={Boolean(gen.showExplanations[idx])}
                                    aiExplanation={gen.aiExplanations[idx]}
                                    aiLoading={gen.aiLoadingIdx === idx}
                                    onPickAnswer={gen.pickAnswer}
                                />
                            ))}
                        </div>

                        {!gen.generating && gen.questions.length === 0 && !gen.errorBanner && (
                            <GenerateEmptyState count={count} trackMeta={trackMeta} />
                        )}
                    </div>
                </main>
            </div>
        </>
    );
}