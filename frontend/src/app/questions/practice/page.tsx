/**
 * questions/practice/page.tsx — Immersive fullscreen year-wise practice mode.
 * One-question-at-a-time view without sidebar/header for distraction-free study.
 * Loads questions filtered by year, supports answer selection, AI explanation,
 * and a compact question navigation palette.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { Suspense, useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { questionsAPI, aiAPI } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import {
  BookOpen, ChevronLeft, ChevronRight, Loader2, Brain, Sparkles,
  CheckCircle, X, Bookmark, ArrowLeft, Target, Lightbulb, Flag
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

function FormattedText({ text, className = '' }: { text: string; className?: string }) {
    if (!text) return null;
    const cleaned = text
        .replace(/^\s*\d+\.\s*/, '') // Strip leading scraped question numbers like "26. "
        .replace(/\*\s+(?=[IVXLC]+\.\s)/g, '\n* ')
        .replace(/\*\s*\*\*Codes/g, '\n\n**Codes')
        .replace(/\*\s+\(/g, '\n* (');
    const md = cleaned.split('\n').map(line => {
        if (!line.trim()) return line;
        if (line.endsWith('  ') || line.endsWith('\\')) return line;
        return line + '  ';
    }).join('\n');
    return (
        <div className={`formatted-text ${className}`} style={{ whiteSpace: 'pre-wrap' }}>
            <ReactMarkdown>{md}</ReactMarkdown>
        </div>
    );
}

function cleanOptionText(text: string): string {
    return text.replace(/\s*\*+\s*$/, '').trim();
}

export default function PracticePage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="text-center space-y-3">
                    <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
                    <p className="text-sm text-muted-foreground font-medium">Loading Practice Session...</p>
                </div>
            </div>
        }>
            <PracticeContent />
        </Suspense>
    );
}

function PracticeContent() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const year = searchParams.get('year');

    const [questions, setQuestions] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [currentIdx, setCurrentIdx] = useState(0);
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const [showAnswer, setShowAnswer] = useState(false);
    const [aiExplanation, setAiExplanation] = useState<any>(null);
    const [aiLoading, setAiLoading] = useState(false);
    const [aiError, setAiError] = useState<string | null>(null);
    const [tokenError, setTokenError] = useState(false);
    const [showPalette, setShowPalette] = useState(false);
    const [bookmarked, setBookmarked] = useState<Set<number>>(new Set());

    const [flagOpen, setFlagOpen] = useState(false);
    const [flagCategory, setFlagCategory] = useState('wrong_answer');
    const [flagComment, setFlagComment] = useState('');
    const [flagSubmitting, setFlagSubmitting] = useState(false);
    const [flagSuccess, setFlagSuccess] = useState(false);
    const [flagError, setFlagError] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (!year) { router.push('/questions'); return; }
        if (isAuthenticated && year) {
            questionsAPI.list({ year, page_size: 200 }).then(res => {
                const qs = res.data.results || res.data || [];
                setQuestions(qs);
            }).catch(() => {
                setQuestions([]);
            }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router, year]);

    const currentQ = questions[currentIdx];
    const totalQ = questions.length;
    const answeredCount = Object.keys(answers).length;
    const correctCount = Object.values(answers).filter((a, i) => {
        const q = questions[i];
        return q && a === (q.correct_answer || '');
    }).length;

    const handleSelectOption = (opt: string) => {
        if (!currentQ || answers[currentQ.id]) return;
        setAnswers(prev => ({ ...prev, [currentQ.id]: opt }));
        setShowAnswer(true);
        // Log attempt
        questionsAPI.attempt(currentQ.id, { selected_answer: opt }).catch(() => {});
    };

    const goToQuestion = useCallback((idx: number) => {
        if (idx < 0 || idx >= totalQ) return;
        setCurrentIdx(idx);
        setShowAnswer(!!answers[questions[idx]?.id]);
        setAiExplanation(null);
        setAiLoading(false);
        setAiError(null);
        setTokenError(false);
        setShowPalette(false);
    }, [totalQ, answers, questions]);

    const handleNext = () => goToQuestion(currentIdx + 1);
    const handlePrev = () => goToQuestion(currentIdx - 1);

    const fetchAiExplanation = () => {
        if (!currentQ || aiLoading) return;
        setAiLoading(true);
        setAiExplanation(null);
        setTokenError(false);
        setAiError(null);
        aiAPI.explainAfterAnswer({
            question_text: currentQ.question_text,
            options: {
                A: currentQ.option_a || currentQ.option_A || '',
                B: currentQ.option_b || currentQ.option_B || '',
                C: currentQ.option_c || currentQ.option_C || '',
                D: currentQ.option_d || currentQ.option_D || '',
            },
            correct_answer: currentQ.correct_answer || '',
            selected_answer: answers[currentQ.id] || '',
            subject: currentQ.subject_name || '',
            topic: currentQ.topic_name || '',
        }).then(res => {
            setAiExplanation(res.data);
            setAiLoading(false);
        }).catch(err => {
            if (err?.response?.status === 429) {
                setTokenError(true);
            } else {
                setAiError('AI service unavailable. Please try again.');
            }
            setAiLoading(false);
        });
    };

    const handleBookmark = () => {
        if (!currentQ) return;
        questionsAPI.bookmark(currentQ.id).then(() => {
            setBookmarked(prev => {
                const n = new Set(prev);
                if (n.has(currentQ.id)) n.delete(currentQ.id);
                else n.add(currentQ.id);
                return n;
            });
        }).catch(err => console.error(err));
    };

    const handleFlagSubmit = () => {
        if (!currentQ || !flagComment.trim()) return;
        setFlagSubmitting(true);
        setFlagError(null);
        questionsAPI.submitFeedback({
            question: currentQ.id,
            category: flagCategory,
            comment: flagComment.trim(),
        }).then(() => {
            setFlagSuccess(true);
            setTimeout(() => { setFlagOpen(false); setFlagSuccess(false); setFlagComment(''); setFlagError(null); }, 2000);
        }).catch((err: any) => {
            setFlagError('Unable to submit feedback right now. Please try again.');
        }).finally(() => {
            setFlagSubmitting(false);
        });
    };

    // Keyboard shortcuts
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'ArrowRight' || e.key === 'n') handleNext();
            if (e.key === 'ArrowLeft' || e.key === 'p') handlePrev();
            if (['a', 'b', 'c', 'd'].includes(e.key.toLowerCase()) && !answers[currentQ?.id]) {
                handleSelectOption(e.key.toUpperCase());
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    });

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="text-center space-y-3">
                    <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
                    <p className="text-sm text-muted-foreground font-medium">Loading {year} PYQs...</p>
                </div>
            </div>
        );
    }

    if (questions.length === 0) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <Card className="max-w-md p-8 text-center space-y-4">
                    <BookOpen className="w-12 h-12 text-muted-foreground mx-auto" />
                    <h2 className="text-lg font-bold">No Questions Found</h2>
                    <p className="text-sm text-muted-foreground">No questions available for year {year}.</p>
                    <Button onClick={() => router.push('/questions')}>
                        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Question Bank
                    </Button>
                </Card>
            </div>
        );
    }

    const selectedAnswer = answers[currentQ?.id] || null;
    const isCorrect = selectedAnswer === currentQ?.correct_answer;

    return (
        <div className="min-h-screen bg-background flex flex-col">
            {/* Top Bar */}
            <div className="sticky top-0 z-50 bg-card/95 backdrop-blur-md border-b border-border/60 px-4 py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button onClick={() => router.push('/questions')} className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
                        <ArrowLeft className="w-4 h-4" /> Exit Practice
                    </button>
                    <div className="h-5 w-px bg-border/60" />
                    <Badge variant="secondary" className="text-xs font-bold">📖 {year} PYQ Practice</Badge>
                </div>

                <div className="flex items-center gap-4">
                    <div className="hidden md:flex items-center gap-2 text-xs">
                        <span className="text-muted-foreground font-medium">Progress:</span>
                        <span className="font-bold text-primary">{answeredCount}/{totalQ}</span>
                        <Progress value={(answeredCount / totalQ) * 100} className="h-1.5 w-24" />
                    </div>
                    <button
                        onClick={() => setShowPalette(!showPalette)}
                        className="flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border border-border/80 hover:bg-muted/50 transition-colors cursor-pointer"
                    >
                        <Target className="w-3.5 h-3.5" />
                        Q {currentIdx + 1}/{totalQ}
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex relative">
                {/* Question Area */}
                <div className="flex-1 overflow-y-auto p-4 md:p-8 lg:px-16 xl:px-24">
                    <div className="max-w-3xl mx-auto space-y-6">
                        {/* Question Number + Meta */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-extrabold text-primary bg-primary/10 px-2.5 py-1 rounded-lg">Q{currentIdx + 1}</span>
                                <Badge variant="secondary" className="text-xs">{currentQ.subject_name}</Badge>
                                {currentQ.topic_name && <Badge variant="outline" className="text-xs">{currentQ.topic_name}</Badge>}
                                {currentQ.difficulty && <Badge variant="outline" className="text-xs capitalize">{currentQ.difficulty}</Badge>}
                            </div>
                            <div className="flex items-center gap-2">
                                <button onClick={handleBookmark} className="p-1.5 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer" title="Bookmark">
                                    <Bookmark className={`w-4 h-4 ${bookmarked.has(currentQ.id) || currentQ.is_bookmarked ? 'text-amber-500 fill-amber-500' : 'text-muted-foreground'}`} />
                                </button>
                            </div>
                        </div>

                        {/* Question Text */}
                        <div className="glass-card rounded-2xl border border-primary/30 shadow-lg p-6">
                            <div className="text-base font-medium leading-relaxed">
                                <FormattedText text={String(currentQ.question_text)} />
                            </div>
                        </div>

                        {/* Options */}
                        <div className="space-y-3">
                            {['A', 'B', 'C', 'D'].map(opt => {
                                const key = `option_${opt.toLowerCase()}`;
                                const optionText = currentQ[key] || currentQ[`option_${opt}`];
                                if (!optionText) return null;
                                const isCorrectOpt = currentQ.correct_answer === opt;
                                const isSelected = selectedAnswer === opt;
                                const isWrong = isSelected && !isCorrectOpt && showAnswer;

                                return (
                                    <button
                                        key={opt}
                                        className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all text-left cursor-pointer ${
                                            showAnswer
                                                ? (isCorrectOpt ? 'border-emerald-500 bg-emerald-500/5 shadow-sm' : isWrong ? 'border-red-500/50 bg-red-500/5 opacity-80' : 'border-border/60 bg-muted/20 opacity-70')
                                                : (isSelected ? 'border-primary bg-primary/5 ring-2 ring-primary/40' : 'border-border/70 hover:border-primary/40 hover:bg-muted/30')
                                        }`}
                                        onClick={() => handleSelectOption(opt)}
                                    >
                                        <div className={`w-9 h-9 shrink-0 flex items-center justify-center rounded-full text-sm font-bold transition-colors ${
                                            showAnswer
                                                ? (isCorrectOpt ? 'bg-emerald-500 text-white' : isWrong ? 'bg-red-500 text-white' : 'bg-muted text-muted-foreground')
                                                : (isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')
                                        }`}>{opt}</div>
                                        <span className="flex-1 text-sm font-medium">{cleanOptionText(String(optionText))}</span>
                                        {showAnswer && isCorrectOpt && <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 shrink-0">✓ Correct</span>}
                                        {isWrong && <span className="text-xs font-bold text-red-600 dark:text-red-400 shrink-0">✗ Wrong</span>}
                                    </button>
                                );
                            })}
                        </div>

                        {!showAnswer && !selectedAnswer && (
                            <p className="text-xs text-center py-2 text-muted-foreground">👆 Select an option to reveal the answer • Use A/B/C/D keys for quick selection</p>
                        )}

                        {/* Answer Analysis */}
                        {showAnswer && (
                            <div className="space-y-4 animate-fadeInUp">
                                {/* Result Banner */}
                                <Card className={`${isCorrect ? 'border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-900/50' : 'border-red-200 bg-red-50 dark:bg-red-950/20 dark:border-red-900/50'}`}>
                                    <CardContent className="p-4">
                                        <h4 className={`text-sm font-bold flex items-center gap-2 ${isCorrect ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}`}>
                                            <CheckCircle className="w-4 h-4" />
                                            {isCorrect ? 'Correct!' : `Incorrect — Answer: ${currentQ.correct_answer}`}
                                        </h4>
                                        {currentQ.explanation && (
                                            <p className="text-sm leading-relaxed mt-2 opacity-80">{String(currentQ.explanation)}</p>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Mnemonic */}
                                {currentQ.mnemonic && !aiExplanation?.mnemonic && (
                                    <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50/50 dark:bg-amber-950/10 dark:border-amber-900/30">
                                        <Lightbulb className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                                        <div>
                                            <h5 className="text-sm font-bold text-amber-700 dark:text-amber-400">🧠 Memory Trick</h5>
                                            <p className="text-sm leading-relaxed mt-1">{String(currentQ.mnemonic)}</p>
                                        </div>
                                    </div>
                                )}

                                {/* 🚩 Flag Wrong Answer */}
                                <div className="flex justify-end mt-4">
                                    <button onClick={() => { setFlagOpen(!flagOpen); setFlagSuccess(false); setFlagError(null); }}
                                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                                        <Flag className="w-3.5 h-3.5" /> Flag Issue
                                    </button>
                                </div>
                                {flagOpen && (
                                    <div className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl mt-2 space-y-3 animate-fadeInUp">
                                        <h5 className="text-sm font-bold flex items-center gap-2 text-red-500">
                                            <Flag className="w-4 h-4" /> Report an Issue
                                        </h5>
                                        {flagSuccess ? (
                                            <p className="text-sm text-emerald-500 font-medium">✓ Thanks! Your feedback has been submitted. You'll earn 2 tokens if accepted.</p>
                                        ) : (
                                            <>
                                                {flagError && <p className="text-sm text-red-500">{flagError}</p>}
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

                                {/* Generate AI Analysis button */}
                                {!aiExplanation && !aiLoading && !tokenError && (
                                    <button onClick={fetchAiExplanation}
                                        className="w-full rounded-2xl border border-blue-200 bg-blue-50/50 dark:bg-blue-900/10 dark:border-blue-800/50 p-4 flex items-center justify-center gap-3 cursor-pointer transition-all hover:bg-blue-50 dark:hover:bg-blue-900/20">
                                        <Brain className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                                        <div className="text-left">
                                            <span className="text-sm font-bold block text-blue-700 dark:text-blue-300">Generate AI Analysis</span>
                                            <span className="text-xs text-muted-foreground">Mnemonics, explanations, exam tips & textbook references</span>
                                        </div>
                                    </button>
                                )}

                                {/* AI Loading */}
                                {aiLoading && (
                                    <div className="flex items-center justify-center gap-3 p-6 rounded-xl border border-blue-200 bg-blue-50/30 dark:bg-blue-900/10">
                                        <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                                        <span className="text-sm font-medium text-blue-600 dark:text-blue-400">Analyzing question with AI...</span>
                                    </div>
                                )}

                                {/* Token Error */}
                                {tokenError && (
                                    <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20">
                                        <CardContent className="p-4 text-center">
                                            <p className="text-sm font-bold text-amber-700 dark:text-amber-400">Daily AI tokens exhausted</p>
                                            <p className="text-xs text-muted-foreground mt-1">Get more tokens or wait for daily refill.</p>
                                        </CardContent>
                                    </Card>
                                )}

                                {/* AI Error */}
                                {aiError && (
                                    <Card className="border-red-200 bg-red-50 dark:bg-red-950/20">
                                        <CardContent className="p-3 text-center text-sm text-red-600">{aiError}</CardContent>
                                    </Card>
                                )}

                                {/* AI Explanation Panels */}
                                {aiExplanation && (
                                    <div className="space-y-3 animate-fadeInUp">
                                        {aiExplanation.why_correct && (
                                            <Card className="border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5 mb-2"><CheckCircle className="w-3.5 h-3.5" /> Why Correct</h5>
                                                <div className="text-sm leading-relaxed"><ReactMarkdown>{String(aiExplanation.why_correct)}</ReactMarkdown></div>
                                            </CardContent></Card>
                                        )}
                                        {aiExplanation.mnemonic && (
                                            <Card className="border-amber-200 bg-amber-50/50 dark:bg-amber-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-amber-700 dark:text-amber-400 flex items-center gap-1.5 mb-2"><Lightbulb className="w-3.5 h-3.5" /> AI Mnemonic</h5>
                                                <div className="text-sm leading-relaxed"><ReactMarkdown>{String(aiExplanation.mnemonic)}</ReactMarkdown></div>
                                            </CardContent></Card>
                                        )}
                                        {aiExplanation.textbook_reference && (
                                            <Card className="border-blue-200 bg-blue-50/50 dark:bg-blue-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-blue-700 dark:text-blue-400 flex items-center gap-1.5 mb-2"><Bookmark className="w-3.5 h-3.5" /> Textbook Reference</h5>
                                                <div className="text-sm leading-relaxed">
                                                    {typeof aiExplanation.textbook_reference === 'string'
                                                        ? <ReactMarkdown>{aiExplanation.textbook_reference}</ReactMarkdown>
                                                        : (
                                                            <div className="space-y-0.5">
                                                                {aiExplanation.textbook_reference.book && <p className="font-semibold">{aiExplanation.textbook_reference.book}</p>}
                                                                {aiExplanation.textbook_reference.chapter && <p className="text-muted-foreground">Ch: {aiExplanation.textbook_reference.chapter}</p>}
                                                                {aiExplanation.textbook_reference.page && <p className="text-muted-foreground">Pg: {aiExplanation.textbook_reference.page}</p>}
                                                            </div>
                                                        )
                                                    }
                                                </div>
                                            </CardContent></Card>
                                        )}
                                        {aiExplanation.exam_tip && (
                                            <Card className="border-purple-200 bg-purple-50/50 dark:bg-purple-950/10"><CardContent className="p-4">
                                                <h5 className="text-xs font-bold text-purple-700 dark:text-purple-400 flex items-center gap-1.5 mb-2"><Sparkles className="w-3.5 h-3.5" /> Exam Tip</h5>
                                                <div className="text-sm leading-relaxed"><ReactMarkdown>{String(aiExplanation.exam_tip)}</ReactMarkdown></div>
                                            </CardContent></Card>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Navigation */}
                        <div className="flex items-center justify-between pt-4 pb-8 border-t border-border/40">
                            <Button variant="outline" size="sm" onClick={handlePrev} disabled={currentIdx <= 0}>
                                <ChevronLeft className="w-4 h-4 mr-1" /> Previous
                            </Button>
                            <span className="text-xs text-muted-foreground font-medium">
                                Question {currentIdx + 1} of {totalQ}
                            </span>
                            <Button variant="outline" size="sm" onClick={handleNext} disabled={currentIdx >= totalQ - 1}>
                                Next <ChevronRight className="w-4 h-4 ml-1" />
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Question Palette Overlay */}
                {showPalette && (
                    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center" onClick={() => setShowPalette(false)}>
                        <div className="bg-card rounded-2xl border border-border/80 shadow-2xl p-6 max-w-md w-full max-h-[80vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-sm font-bold">Question Palette — {year} PYQs</h3>
                                <button onClick={() => setShowPalette(false)} className="p-1 rounded-lg hover:bg-muted cursor-pointer">
                                    <X className="w-4 h-4" />
                                </button>
                            </div>
                            <div className="grid grid-cols-8 gap-1.5">
                                {questions.map((q, i) => {
                                    const hasAnswer = !!answers[q.id];
                                    const isCurrent = i === currentIdx;
                                    return (
                                        <button
                                            key={q.id}
                                            onClick={() => goToQuestion(i)}
                                            className={`w-8 h-8 rounded-lg text-[10px] font-bold flex items-center justify-center transition-all cursor-pointer ${
                                                isCurrent ? 'bg-primary text-primary-foreground ring-2 ring-primary/50' :
                                                hasAnswer ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30' :
                                                'bg-muted/30 text-muted-foreground border border-border/40 hover:bg-muted/60'
                                            }`}
                                        >
                                            {i + 1}
                                        </button>
                                    );
                                })}
                            </div>
                            <div className="flex items-center gap-4 mt-4 pt-3 border-t border-border/40 text-[10px] text-muted-foreground">
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-primary" /> Current</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/20 border border-emerald-500/30" /> Answered</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-muted/30 border border-border/40" /> Not Attempted</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
