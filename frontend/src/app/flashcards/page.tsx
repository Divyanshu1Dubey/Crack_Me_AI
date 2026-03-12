/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { flashcardsAPI } from '@/lib/api';
import {
    Layers, Plus, RotateCcw, CheckCircle, Clock,
    ChevronLeft, ChevronRight, Brain, Trash2, X
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';

interface Flashcard {
    id: number;
    front: string;
    back: string;
    difficulty: string;
    subject_name: string;
    next_review: string;
    review_count: number;
    interval_days: number;
    ease_factor: number;
    created_at: string;
}

const difficultyColors: Record<string, string> = {
    easy: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
    medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
    hard: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

const qualityLabels = [
    { q: 0, label: 'Blackout', color: 'bg-red-500 hover:bg-red-600', desc: 'No idea' },
    { q: 1, label: 'Wrong', color: 'bg-red-400 hover:bg-red-500', desc: 'Incorrect' },
    { q: 2, label: 'Hard', color: 'bg-orange-500 hover:bg-orange-600', desc: 'Barely recalled' },
    { q: 3, label: 'Good', color: 'bg-amber-500 hover:bg-amber-600', desc: 'Some hesitation' },
    { q: 4, label: 'Easy', color: 'bg-emerald-500 hover:bg-emerald-600', desc: 'Quick recall' },
    { q: 5, label: 'Perfect', color: 'bg-green-500 hover:bg-green-600', desc: 'Instant' },
];

export default function FlashcardsPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [cards, setCards] = useState<Flashcard[]>([]);
    const [dueCards, setDueCards] = useState<Flashcard[]>([]);
    const [loading, setLoading] = useState(true);
    const [mode, setMode] = useState<'browse' | 'review' | 'create'>('browse');
    const [currentIndex, setCurrentIndex] = useState(0);
    const [flipped, setFlipped] = useState(false);
    const [showCreate, setShowCreate] = useState(false);
    const [form, setForm] = useState({ front: '', back: '', difficulty: 'medium' });
    const [submitting, setSubmitting] = useState(false);
    const [analytics, setAnalytics] = useState<{
        total_cards: number; cards_due_today: number; retention_rate: number;
        avg_ease_factor: number; avg_interval: number;
        interval_distribution: Record<string, number>;
    } | null>(null);

    const fetchCards = useCallback(() => {
        setLoading(true);
        Promise.all([
            flashcardsAPI.list().catch(() => ({ data: [] })),
            flashcardsAPI.list({ due: 'true' }).catch(() => ({ data: [] })),
            flashcardsAPI.analytics().catch(() => ({ data: null })),
        ]).then(([allRes, dueRes, analyticsRes]) => {
            const all = Array.isArray(allRes.data) ? allRes.data : allRes.data?.results || [];
            const due = Array.isArray(dueRes.data) ? dueRes.data : dueRes.data?.results || [];
            setCards(all);
            setDueCards(due);
            if (analyticsRes.data) setAnalytics(analyticsRes.data);
            setLoading(false);
        });
    }, []);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) fetchCards();
    }, [isAuthenticated, authLoading, router, fetchCards]);

    const handleCreate = async () => {
        if (!form.front.trim() || !form.back.trim()) return;
        setSubmitting(true);
        try {
            await flashcardsAPI.create({ front: form.front, back: form.back, difficulty: form.difficulty });
            setForm({ front: '', back: '', difficulty: 'medium' });
            setShowCreate(false);
            fetchCards();
        } catch { /* ignore */ }
        setSubmitting(false);
    };

    const handleReview = async (quality: number) => {
        const card = dueCards[currentIndex];
        if (!card) return;
        try {
            await flashcardsAPI.review(card.id, quality);
            const updated = [...dueCards];
            updated.splice(currentIndex, 1);
            setDueCards(updated);
            setFlipped(false);
            if (currentIndex >= updated.length && updated.length > 0) {
                setCurrentIndex(updated.length - 1);
            }
            if (updated.length === 0) setMode('browse');
        } catch { /* ignore */ }
    };

    const handleDelete = async (id: number) => {
        try {
            await flashcardsAPI.delete(id);
            setCards(cards.filter(c => c.id !== id));
            setDueCards(dueCards.filter(c => c.id !== id));
        } catch { /* ignore */ }
    };

    const startReview = () => {
        if (dueCards.length === 0) return;
        setCurrentIndex(0);
        setFlipped(false);
        setMode('review');
    };

    if (authLoading) return null;

    const currentCard = dueCards[currentIndex];

    return (
        <div className="min-h-screen bg-background flex">
            <Sidebar />
            <div className="flex-1 flex flex-col">
                <Header />
                <main className="flex-1 p-6 page-container space-y-6">
                    {/* Title */}
                    <div className="flex items-center justify-between flex-wrap gap-3">
                        <div className="flex items-center gap-3">
                            <Layers className="w-7 h-7 text-primary" />
                            <div>
                                <h1 className="text-2xl font-bold">Flashcards</h1>
                                <p className="text-sm text-muted-foreground">Spaced repetition study cards</p>
                            </div>
                        </div>
                        <div className="flex gap-2">
                            {mode === 'review' ? (
                                <Button variant="outline" onClick={() => { setMode('browse'); setFlipped(false); }}>
                                    <X className="w-4 h-4 mr-1" /> Exit Review
                                </Button>
                            ) : (
                                <>
                                    <Button variant="outline" onClick={() => setShowCreate(!showCreate)}>
                                        <Plus className="w-4 h-4 mr-1" /> Create
                                    </Button>
                                    <Button onClick={startReview} disabled={dueCards.length === 0}>
                                        <Brain className="w-4 h-4 mr-1" /> Review ({dueCards.length} due)
                                    </Button>
                                </>
                            )}
                        </div>
                    </div>

                    {/* Stats */}
                    {mode !== 'review' && (
                        <div className="grid grid-cols-3 gap-4">
                            <Card>
                                <CardContent className="p-4 flex items-center gap-3">
                                    <Layers className="w-8 h-8 text-blue-500" />
                                    <div>
                                        <p className="text-2xl font-bold">{cards.length}</p>
                                        <p className="text-xs text-muted-foreground">Total Cards</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="p-4 flex items-center gap-3">
                                    <Clock className="w-8 h-8 text-amber-500" />
                                    <div>
                                        <p className="text-2xl font-bold">{dueCards.length}</p>
                                        <p className="text-xs text-muted-foreground">Due for Review</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="p-4 flex items-center gap-3">
                                    <CheckCircle className="w-8 h-8 text-emerald-500" />
                                    <div>
                                        <p className="text-2xl font-bold">{cards.length - dueCards.length}</p>
                                        <p className="text-xs text-muted-foreground">Reviewed</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {/* SR Analytics */}
                    {mode !== 'review' && analytics && analytics.total_cards > 0 && (
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center gap-2"><Brain className="w-4 h-4 text-primary" /> Spaced Repetition Analytics</CardTitle>
                            </CardHeader>
                            <CardContent className="pb-4">
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                                    <div className="p-2 rounded-lg bg-muted/50">
                                        <p className="text-lg font-bold text-emerald-600">{Math.round(analytics.retention_rate * 100)}%</p>
                                        <p className="text-[10px] text-muted-foreground">Retention Rate</p>
                                    </div>
                                    <div className="p-2 rounded-lg bg-muted/50">
                                        <p className="text-lg font-bold text-blue-600">{analytics.avg_ease_factor}</p>
                                        <p className="text-[10px] text-muted-foreground">Avg Ease Factor</p>
                                    </div>
                                    <div className="p-2 rounded-lg bg-muted/50">
                                        <p className="text-lg font-bold text-amber-600">{analytics.avg_interval}d</p>
                                        <p className="text-[10px] text-muted-foreground">Avg Interval</p>
                                    </div>
                                    <div className="p-2 rounded-lg bg-muted/50">
                                        <p className="text-lg font-bold text-purple-600">{analytics.cards_due_today}</p>
                                        <p className="text-[10px] text-muted-foreground">Due Today</p>
                                    </div>
                                </div>
                                {analytics.interval_distribution && (
                                    <div className="mt-3 flex gap-1 h-3">
                                        {[
                                            { key: '1_day', color: 'bg-red-400', label: '1d' },
                                            { key: '2_7_days', color: 'bg-amber-400', label: '2-7d' },
                                            { key: '8_30_days', color: 'bg-emerald-400', label: '8-30d' },
                                            { key: '30_plus_days', color: 'bg-blue-400', label: '30d+' },
                                        ].map(({ key, color }) => {
                                            const count = analytics.interval_distribution[key] || 0;
                                            const pct = analytics.total_cards > 0 ? (count / analytics.total_cards) * 100 : 0;
                                            return pct > 0 ? <div key={key} className={`${color} rounded-full`} style={{ width: `${pct}%` }} title={`${key}: ${count} cards`} /> : null;
                                        })}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {/* Create Form */}
                    {showCreate && mode !== 'review' && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Create New Flashcard</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div>
                                    <label className="text-sm font-medium mb-1 block">Front (Question / Term)</label>
                                    <textarea
                                        className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                                        placeholder="What do you want to remember?"
                                        value={form.front}
                                        onChange={e => setForm({ ...form, front: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="text-sm font-medium mb-1 block">Back (Answer / Definition)</label>
                                    <textarea
                                        className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                                        placeholder="The answer or explanation"
                                        value={form.back}
                                        onChange={e => setForm({ ...form, back: e.target.value })}
                                    />
                                </div>
                                <div className="flex items-center gap-3">
                                    <select
                                        className="rounded-md border bg-background px-3 py-2 text-sm"
                                        value={form.difficulty}
                                        onChange={e => setForm({ ...form, difficulty: e.target.value })}
                                    >
                                        <option value="easy">Easy</option>
                                        <option value="medium">Medium</option>
                                        <option value="hard">Hard</option>
                                    </select>
                                    <Button onClick={handleCreate} disabled={submitting}>
                                        {submitting ? 'Creating...' : 'Create Card'}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Review Mode */}
                    {mode === 'review' && currentCard && (
                        <div className="max-w-2xl mx-auto space-y-4">
                            <div className="text-center text-sm text-muted-foreground">
                                Card {currentIndex + 1} of {dueCards.length} remaining
                            </div>

                            {/* Card */}
                            <div
                                className="min-h-[280px] cursor-pointer"
                                onClick={() => setFlipped(!flipped)}
                            >
                                <Card className="min-h-[280px] flex flex-col justify-center transition-all">
                                    <CardContent className="p-8 text-center">
                                        <Badge className={`mb-4 ${difficultyColors[currentCard.difficulty] || ''}`}>
                                            {currentCard.difficulty}
                                        </Badge>
                                        {currentCard.subject_name && (
                                            <Badge variant="outline" className="ml-2 mb-4">{currentCard.subject_name}</Badge>
                                        )}
                                        <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wider">
                                            {flipped ? 'Answer' : 'Question'} — tap to flip
                                        </p>
                                        <p className="text-lg leading-relaxed whitespace-pre-wrap">
                                            {flipped ? currentCard.back : currentCard.front}
                                        </p>
                                        {!flipped && (
                                            <p className="text-sm text-muted-foreground mt-6">
                                                <RotateCcw className="w-4 h-4 inline mr-1" /> Click to reveal answer
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Quality buttons (only when flipped) */}
                            {flipped && (
                                <div>
                                    <p className="text-center text-sm text-muted-foreground mb-3">How well did you recall this?</p>
                                    <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                                        {qualityLabels.map(q => (
                                            <button
                                                key={q.q}
                                                onClick={() => handleReview(q.q)}
                                                className={`${q.color} text-white rounded-lg px-2 py-3 text-center transition-colors`}
                                            >
                                                <p className="text-sm font-semibold">{q.label}</p>
                                                <p className="text-[10px] opacity-80">{q.desc}</p>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Navigation */}
                            <div className="flex justify-center gap-2">
                                <Button
                                    variant="outline" size="sm"
                                    disabled={currentIndex === 0}
                                    onClick={() => { setCurrentIndex(currentIndex - 1); setFlipped(false); }}
                                >
                                    <ChevronLeft className="w-4 h-4" /> Prev
                                </Button>
                                <Button
                                    variant="outline" size="sm"
                                    disabled={currentIndex >= dueCards.length - 1}
                                    onClick={() => { setCurrentIndex(currentIndex + 1); setFlipped(false); }}
                                >
                                    Next <ChevronRight className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* Review Complete */}
                    {mode === 'review' && dueCards.length === 0 && (
                        <Card className="max-w-md mx-auto">
                            <CardContent className="p-8 text-center">
                                <CheckCircle className="w-16 h-16 mx-auto text-emerald-500 mb-4" />
                                <h2 className="text-xl font-bold mb-2">All caught up!</h2>
                                <p className="text-muted-foreground mb-4">You&apos;ve reviewed all due flashcards.</p>
                                <Button onClick={() => setMode('browse')}>Back to Cards</Button>
                            </CardContent>
                        </Card>
                    )}

                    {/* Browse Mode — card list */}
                    {mode !== 'review' && !loading && (
                        <>
                            {cards.length === 0 ? (
                                <Card>
                                    <CardContent className="p-12 text-center">
                                        <Layers className="w-12 h-12 mx-auto text-muted-foreground/40 mb-3" />
                                        <p className="text-muted-foreground">No flashcards yet. Create your first card above!</p>
                                    </CardContent>
                                </Card>
                            ) : (
                                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {cards.map(card => {
                                        const isDue = new Date(card.next_review) <= new Date();
                                        return (
                                            <Card key={card.id} className={`group ${isDue ? 'border-amber-500/30' : ''}`}>
                                                <CardContent className="p-4">
                                                    <div className="flex items-start justify-between mb-2">
                                                        <div className="flex gap-1.5">
                                                            <Badge className={`text-[10px] ${difficultyColors[card.difficulty] || ''}`}>
                                                                {card.difficulty}
                                                            </Badge>
                                                            {isDue && <Badge className="text-[10px] bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300">Due</Badge>}
                                                        </div>
                                                        <Button
                                                            variant="ghost" size="icon"
                                                            className="h-7 w-7 opacity-0 group-hover:opacity-100 text-destructive"
                                                            onClick={() => handleDelete(card.id)}
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </Button>
                                                    </div>
                                                    <p className="text-sm font-medium line-clamp-2 mb-1">{card.front}</p>
                                                    <p className="text-xs text-muted-foreground line-clamp-2">{card.back}</p>
                                                    <div className="flex items-center gap-3 mt-3 text-xs text-muted-foreground">
                                                        <span><RotateCcw className="w-3 h-3 inline mr-0.5" />{card.review_count}x</span>
                                                        <span>{card.interval_days}d interval</span>
                                                        {card.subject_name && <span>{card.subject_name}</span>}
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        );
                                    })}
                                </div>
                            )}
                        </>
                    )}

                    {loading && mode !== 'review' && (
                        <div className="text-center py-12 text-muted-foreground animate-pulse">Loading flashcards...</div>
                    )}
                </main>
            </div>
        </div>
    );
}
