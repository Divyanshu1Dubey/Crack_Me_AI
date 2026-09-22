'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { mistakeNotebookAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, BookOpen, CheckCircle2, Flag, Search } from 'lucide-react';
import Link from 'next/link';

interface MistakeEntry {
    id: number;
    question_text: string;
    selected_answer: string | null;
    correct_answer: string;
    user_note: string;
    is_flagged: boolean;
    review_status: string;
    created_at: string;
    next_review_at: string;
    question_id: number;
}

export default function MistakeNotebookPage() {
    const { user } = useAuth();
    const [entries, setEntries] = useState<MistakeEntry[]>([]);
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [reviewing, setReviewing] = useState<number | null>(null);
    const [reviewNote, setReviewNote] = useState('');

    useEffect(() => {
        Promise.all([
            mistakeNotebookAPI.list(),
            mistakeNotebookAPI.stats(),
        ]).then(([entriesRes, statsRes]) => {
            setEntries(entriesRes.data as MistakeEntry[]);
            setStats(statsRes.data);
            setLoading(false);
        }).catch(() => setLoading(false));
    }, []);

    const handleReview = async (entryId: number) => {
        setReviewing(entryId);
        try {
            await mistakeNotebookAPI.review(entryId);
            setEntries(prev => prev.map(e =>
                e.id === entryId ? { ...e, review_status: 'reviewed', next_review_at: '' } : e
            ));
        } catch (err) {
            console.error('Review failed:', err);
        } finally {
            setReviewing(null);
            setReviewNote('');
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'new': return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
            case 'learning': return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300';
            case 'review': return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';
            case 'mastered': return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
            default: return 'bg-gray-100 text-gray-700';
        }
    };

    if (loading) {
        return (
            <div className="max-w-4xl mx-auto p-6 space-y-4">
                <Skeleton className="h-8 w-64" />
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[1, 2, 3].map(i => <Skeleton key={i} className="h-24" />)}
                </div>
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-32" />)}
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
                    <BookOpen className="w-6 h-6 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold">Mistake Notebook</h1>
                    <p className="text-sm text-muted-foreground">Review and learn from your mistakes</p>
                </div>
            </div>

            {/* Stats */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card>
                        <CardContent className="p-4 text-center">
                            <div className="text-2xl font-bold">{stats.total}</div>
                            <div className="text-xs text-muted-foreground">Total Mistakes</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <div className="text-2xl font-bold text-amber-600">{stats.by_status?.new || 0}</div>
                            <div className="text-xs text-muted-foreground">New</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <div className="text-2xl font-bold text-blue-600">{stats.by_status?.review || 0}</div>
                            <div className="text-xs text-muted-foreground">In Review</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <div className="text-2xl font-bold text-green-600">{stats.by_status?.mastered || 0}</div>
                            <div className="text-xs text-muted-foreground">Mastered</div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Entries */}
            {entries.length === 0 ? (
                <Card>
                    <CardContent className="p-12 text-center">
                        <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold mb-2">No mistakes yet!</h3>
                        <p className="text-muted-foreground mb-4">
                            Start practicing questions and your mistakes will appear here for review.
                        </p>
                        <Link href="/questions">
                            <Button>Start Practicing</Button>
                        </Link>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    {entries.map((entry) => (
                        <Card key={entry.id} className={entry.is_flagged ? 'border-amber-300 dark:border-amber-700' : ''}>
                            <CardContent className="p-4 space-y-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium line-clamp-2">{entry.question_text}</p>
                                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                                            <Badge variant="outline" className="text-xs">
                                                Your answer: {entry.selected_answer || 'Skipped'}
                                            </Badge>
                                            <Badge className="text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
                                                Correct: {entry.correct_answer}
                                            </Badge>
                                            <Badge className={`text-xs ${getStatusColor(entry.review_status)}`}>
                                                {entry.review_status}
                                            </Badge>
                                            {entry.is_flagged && (
                                                <Badge variant="outline" className="text-xs border-amber-400 text-amber-600">
                                                    <Flag className="w-3 h-3 mr-1" /> Flagged
                                                </Badge>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {entry.user_note && (
                                    <div className="bg-muted/50 rounded-md p-2 text-xs text-muted-foreground">
                                        <strong>Your note:</strong> {entry.user_note}
                                    </div>
                                )}

                                <div className="flex items-center gap-2">
                                    <Link href={`/questions/${entry.question_id}`}>
                                        <Button variant="outline" size="sm">
                                            <Search className="w-3 h-3 mr-1" />
                                            Review Question
                                        </Button>
                                    </Link>
                                    {entry.review_status !== 'mastered' && (
                                        <Button
                                            size="sm"
                                            onClick={() => handleReview(entry.id)}
                                            disabled={reviewing === entry.id}
                                        >
                                            {reviewing === entry.id ? 'Saving...' : 'Mark as Reviewed'}
                                        </Button>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
