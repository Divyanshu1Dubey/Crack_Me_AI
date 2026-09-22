'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { questsAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Flame, CheckCircle2, Gift, Target, Zap, Star } from 'lucide-react';

interface Quest {
    id: number;
    quest_type: string;
    title: string;
    description: string;
    target_value: number;
    current_value: number;
    reward_tokens: number;
    reward_xp: number;
    expires_at: string;
    is_completed: boolean;
    icon: string;
}

interface StreakInfo {
    current_streak: number;
    longest_streak: number;
    streak_freeze_available: boolean;
    last_active_date: string;
}

const QUEST_ICONS: Record<string, any> = {
    'daily_practice': Target,
    'daily_quiz': Zap,
    'weekly_master': Star,
    'streak_keep': Flame,
    'special': Gift,
};

export default function QuestsPage() {
    const { user } = useAuth();
    const [quests, setQuests] = useState<Quest[]>([]);
    const [streak, setStreak] = useState<StreakInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [completing, setCompleting] = useState<number | null>(null);

    useEffect(() => {
        Promise.all([
            questsAPI.list(),
            questsAPI.getStreak(),
        ]).then(([questsRes, streakRes]) => {
            setQuests(questsRes.data as Quest[]);
            setStreak(streakRes.data as StreakInfo);
            setLoading(false);
        }).catch(() => setLoading(false));
    }, []);

    const handleComplete = async (questId: number) => {
        setCompleting(questId);
        try {
            await questsAPI.complete(questId);
            setQuests(prev => prev.map(q =>
                q.id === questId ? { ...q, is_completed: true } : q
            ));
        } catch (err) {
            console.error('Complete quest failed:', err);
        } finally {
            setCompleting(null);
        }
    };

    if (loading) {
        return (
            <div className="max-w-4xl mx-auto p-6 space-y-4">
                <Skeleton className="h-8 w-48" />
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-40" />)}
            </div>
        );
    }

    const activeQuests = quests.filter(q => !q.is_completed);
    const completedQuests = quests.filter(q => q.is_completed);

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
                    <Flame className="w-6 h-6 text-orange-600 dark:text-orange-400" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold">Daily Quests</h1>
                    <p className="text-sm text-muted-foreground">Complete quests to earn tokens and XP</p>
                </div>
            </div>

            {/* Streak Card */}
            {streak && (
                <Card className="bg-linear-to-r from-orange-50 to-amber-50 dark:from-orange-950/30 dark:to-amber-950/30 border-orange-200 dark:border-orange-800">
                    <CardContent className="p-6 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="text-4xl">🔥</div>
                            <div>
                                <div className="text-3xl font-bold text-orange-600 dark:text-orange-400">
                                    {streak.current_streak} days
                                </div>
                                <div className="text-sm text-muted-foreground">
                                    Best: {streak.longest_streak} days
                                </div>
                            </div>
                        </div>
                        {streak.streak_freeze_available && (
                            <Badge variant="outline" className="border-blue-400 text-blue-600">
                                Freeze Available
                            </Badge>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Active Quests */}
            {activeQuests.length > 0 && (
                <div className="space-y-3">
                    <h2 className="text-lg font-semibold">Active Quests</h2>
                    {activeQuests.map(quest => {
                        const Icon = QUEST_ICONS[quest.quest_type] || Target;
                        const progress = Math.min((quest.current_value / quest.target_value) * 100, 100);
                        return (
                            <Card key={quest.id}>
                                <CardContent className="p-4">
                                    <div className="flex items-start gap-3">
                                        <div className="p-2 bg-primary/10 rounded-lg">
                                            <Icon className="w-5 h-5 text-primary" />
                                        </div>
                                        <div className="flex-1">
                                            <div className="font-medium">{quest.title}</div>
                                            <p className="text-sm text-muted-foreground">{quest.description}</p>
                                            <div className="mt-2 h-2 bg-muted rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-primary rounded-full transition-all"
                                                    style={{ width: `${progress}%` }}
                                                />
                                            </div>
                                            <div className="text-xs text-muted-foreground mt-1">
                                                {quest.current_value} / {quest.target_value}
                                            </div>
                                            <div className="flex items-center gap-2 mt-2">
                                                <Badge variant="outline" className="text-xs">
                                                    +{quest.reward_tokens} tokens
                                                </Badge>
                                                <Badge variant="outline" className="text-xs">
                                                    +{quest.reward_xp} XP
                                                </Badge>
                                            </div>
                                        </div>
                                        <Button
                                            size="sm"
                                            onClick={() => handleComplete(quest.id)}
                                            disabled={completing === quest.id || progress < 100}
                                        >
                                            {completing === quest.id ? '...' : 'Claim'}
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Completed Quests */}
            {completedQuests.length > 0 && (
                <div className="space-y-3">
                    <h2 className="text-lg font-semibold text-muted-foreground">Completed</h2>
                    {completedQuests.map(quest => (
                        <Card key={quest.id} className="opacity-60">
                            <CardContent className="p-4 flex items-center gap-3">
                                <CheckCircle2 className="w-5 h-5 text-green-500" />
                                <div className="flex-1">
                                    <div className="font-medium line-through">{quest.title}</div>
                                </div>
                                <Badge variant="secondary" className="text-xs">
                                    +{quest.reward_tokens} tokens
                                </Badge>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {quests.length === 0 && (
                <Card>
                    <CardContent className="p-8 text-center text-muted-foreground">
                        <Gift className="w-12 h-12 mx-auto mb-3 opacity-30" />
                        <p>No active quests right now. Check back later!</p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
