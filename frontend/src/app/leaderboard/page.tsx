/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI } from '@/lib/api';
import { Trophy, Medal, Flame, Zap, Target, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface LeaderboardEntry {
    rank: number;
    username: string;
    user_id: number;
    xp_points: number;
    current_streak: number;
    total_study_days: number;
    accuracy: number;
    tests_completed: number;
}

const rankStyle = (rank: number) => {
    if (rank === 1) return 'bg-gradient-to-r from-yellow-500/20 to-amber-500/10 border-yellow-500/30';
    if (rank === 2) return 'bg-gradient-to-r from-slate-300/20 to-slate-400/10 border-slate-400/30';
    if (rank === 3) return 'bg-gradient-to-r from-orange-500/20 to-amber-600/10 border-orange-600/30';
    return '';
};

const rankIcon = (rank: number) => {
    if (rank === 1) return <Trophy className="w-6 h-6 text-yellow-500" />;
    if (rank === 2) return <Medal className="w-6 h-6 text-slate-400" />;
    if (rank === 3) return <Medal className="w-6 h-6 text-orange-500" />;
    return <span className="w-6 h-6 flex items-center justify-center text-sm font-bold text-muted-foreground">#{rank}</span>;
};

export default function LeaderboardPage() {
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [period, setPeriod] = useState<string>('all');

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) fetchLeaderboard();
    }, [isAuthenticated, authLoading, router]);

    const fetchLeaderboard = (p?: string) => {
        setLoading(true);
        analyticsAPI.getLeaderboard(p || period)
            .then(res => {
                setEntries(Array.isArray(res.data) ? res.data : res.data?.results || []);
            })
            .catch(() => setEntries([]))
            .finally(() => setLoading(false));
    };

    const handlePeriod = (p: string) => {
        setPeriod(p);
        fetchLeaderboard(p);
    };

    if (authLoading) return null;

    const myRank = entries.find(e => e.user_id === user?.id);
    const topThree = entries.slice(0, 3);
    const rest = entries.slice(3);

    return (
        <div className="min-h-screen bg-background flex">
            <Sidebar />
            <div className="flex-1 flex flex-col">
                <Header />
                <main className="flex-1 p-6 page-container space-y-6">
                    {/* Title */}
                    <div className="flex items-center justify-between flex-wrap gap-3">
                        <div className="flex items-center gap-3">
                            <Trophy className="w-7 h-7 text-yellow-500" />
                            <div>
                                <h1 className="text-2xl font-bold">Leaderboard</h1>
                                <p className="text-sm text-muted-foreground">Top performers by XP</p>
                            </div>
                        </div>
                        <div className="flex gap-1 bg-muted rounded-lg p-1">
                            {['all', 'weekly', 'monthly'].map(p => (
                                <button
                                    key={p}
                                    onClick={() => handlePeriod(p)}
                                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${period === p ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                                >
                                    {p === 'all' ? 'All Time' : p.charAt(0).toUpperCase() + p.slice(1)}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* My Rank Card */}
                    {myRank && (
                        <Card className="border-primary/30 bg-primary/5">
                            <CardContent className="p-4 flex items-center justify-between flex-wrap gap-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center font-bold text-primary">
                                        #{myRank.rank}
                                    </div>
                                    <div>
                                        <p className="font-semibold">Your Ranking</p>
                                        <p className="text-sm text-muted-foreground">{myRank.xp_points} XP</p>
                                    </div>
                                </div>
                                <div className="flex gap-4 text-sm">
                                    <span className="flex items-center gap-1"><Flame className="w-4 h-4 text-orange-500" />{myRank.current_streak}d streak</span>
                                    <span className="flex items-center gap-1"><Target className="w-4 h-4 text-emerald-500" />{myRank.accuracy?.toFixed(1)}%</span>
                                    <span className="flex items-center gap-1"><TrendingUp className="w-4 h-4 text-blue-500" />{myRank.tests_completed} tests</span>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {loading ? (
                        <div className="text-center py-12 text-muted-foreground animate-pulse">Loading rankings...</div>
                    ) : entries.length === 0 ? (
                        <Card>
                            <CardContent className="p-12 text-center">
                                <Trophy className="w-12 h-12 mx-auto text-muted-foreground/40 mb-3" />
                                <p className="text-muted-foreground">No rankings yet. Start studying to appear on the leaderboard!</p>
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            {/* Top 3 Podium */}
                            {topThree.length > 0 && (
                                <div className="grid sm:grid-cols-3 gap-4">
                                    {topThree.map(entry => (
                                        <Card key={entry.rank} className={`${rankStyle(entry.rank)} border`}>
                                            <CardContent className="p-5 text-center">
                                                {rankIcon(entry.rank)}
                                                <div className="w-14 h-14 mx-auto mt-3 rounded-full bg-primary/10 flex items-center justify-center text-xl font-bold text-primary">
                                                    {entry.username.charAt(0).toUpperCase()}
                                                </div>
                                                <p className="font-semibold mt-2">{entry.username}</p>
                                                <div className="flex items-center justify-center gap-1 mt-1">
                                                    <Zap className="w-4 h-4 text-yellow-500" />
                                                    <span className="text-lg font-bold">{entry.xp_points}</span>
                                                    <span className="text-xs text-muted-foreground">XP</span>
                                                </div>
                                                <div className="flex justify-center gap-3 mt-2 text-xs text-muted-foreground">
                                                    <span><Flame className="w-3 h-3 inline text-orange-500" /> {entry.current_streak}d</span>
                                                    <span><Target className="w-3 h-3 inline text-emerald-500" /> {entry.accuracy?.toFixed(0)}%</span>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            )}

                            {/* Rest of Leaderboard */}
                            {rest.length > 0 && (
                                <Card>
                                    <CardContent className="p-0">
                                        <div className="divide-y">
                                            {rest.map(entry => (
                                                <div
                                                    key={entry.rank}
                                                    className={`flex items-center gap-4 px-4 py-3 hover:bg-muted/50 transition-colors ${entry.user_id === user?.id ? 'bg-primary/5' : ''}`}
                                                >
                                                    <span className="w-8 text-center font-bold text-muted-foreground">#{entry.rank}</span>
                                                    <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                                                        {entry.username.charAt(0).toUpperCase()}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <p className="font-medium text-sm truncate">
                                                            {entry.username}
                                                            {entry.user_id === user?.id && <Badge variant="outline" className="ml-2 text-[10px]">You</Badge>}
                                                        </p>
                                                    </div>
                                                    <div className="flex items-center gap-4 text-sm shrink-0">
                                                        <span className="flex items-center gap-1 text-muted-foreground">
                                                            <Flame className="w-3.5 h-3.5 text-orange-500" />{entry.current_streak}d
                                                        </span>
                                                        <span className="flex items-center gap-1 text-muted-foreground">
                                                            <Target className="w-3.5 h-3.5 text-emerald-500" />{entry.accuracy?.toFixed(0)}%
                                                        </span>
                                                        <span className="flex items-center gap-1 font-semibold">
                                                            <Zap className="w-3.5 h-3.5 text-yellow-500" />{entry.xp_points}
                                                        </span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}
                </main>
            </div>
        </div>
    );
}
