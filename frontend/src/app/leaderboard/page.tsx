'use client';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI } from '@/lib/api';
import { Trophy, Medal, Flame, Zap, Target, TrendingUp } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
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
    college?: string;
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

    const fetchLeaderboard = useCallback((selectedPeriod: string) => {
        setLoading(true);
        analyticsAPI.getLeaderboard(selectedPeriod)
            .then(res => {
                setEntries(Array.isArray(res.data) ? res.data : res.data?.results || []);
            })
            .catch(() => setEntries([]))
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            const timer = setTimeout(() => fetchLeaderboard(period), 0);
            return () => clearTimeout(timer);
        }
    }, [isAuthenticated, authLoading, router, fetchLeaderboard, period]);

    const handlePeriod = (p: string) => {
        if (p !== period) {
            setPeriod(p);
        }
    };

    if (authLoading) return null;

    const myRank = entries.find(e => e.user_id === user?.id);
    const topThree = entries.slice(0, 3);
    const rest = entries.slice(3);

    return (
        <>
            <Sidebar />
            <div className="main-content">
                {/* Sticky, always-visible header for leaderboard */}
                <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/60 px-4 md:px-8 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-2 md:gap-4 shadow-sm">
                    <div className="flex items-center gap-3 min-w-0">
                        <Trophy className="w-7 h-7 text-yellow-500 shrink-0" />
                        <div className="min-w-0">
                            <h1 className="text-xl md:text-2xl font-bold text-foreground truncate">Leaderboard</h1>
                            <p className="text-xs md:text-sm text-muted-foreground truncate">Top performers by XP</p>
                        </div>
                    </div>
                    <div className="flex gap-1 bg-muted rounded-lg p-1 self-start md:self-auto">
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
                <Header />
                <main className="flex-1 p-4 md:p-6 page-container space-y-6">

                    {/* Campus Momentum Section */}
                    <div className="glass-card p-6 border border-amber-500/20 relative overflow-hidden text-left" style={{
                        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)',
                    }}>
                        <div className="absolute top-0 right-0 w-72 h-72 bg-amber-500/5 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
                        <div className="absolute bottom-0 left-0 w-72 h-72 bg-cyan-500/5 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none" />
                        
                        <div className="relative z-10 space-y-4">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                <div>
                                    <h2 className="text-lg font-extrabold text-white flex items-center gap-2">
                                        <Flame className="w-5 h-5 text-amber-500 animate-pulse" />
                                        Campus Momentum
                                    </h2>
                                    <p className="text-slate-300 text-xs md:text-sm mt-1">
                                        Students and residents from leading medical institutions prep here.
                                    </p>
                                </div>
                                <div className="shrink-0 bg-amber-500/10 border border-amber-500/25 px-3 py-1.5 rounded-full text-[10px] md:text-xs font-bold text-amber-500 flex items-center gap-1.5 self-start sm:self-auto">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                                    2,900+ active this week
                                </div>
                            </div>

                            {/* Institutions ticker/list */}
                            <div className="flex flex-wrap gap-1.5 pt-1 border-t border-slate-700/40">
                                {['AIIMS Delhi', 'CMC Vellore', 'JIPMER Puducherry', 'KGMU Lucknow', 'Maulana Azad Medical College', 'Seth GS Medical College'].map((inst, i) => (
                                    <span key={i} className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-900/60 border border-border text-slate-300">
                                        🏫 {inst}
                                    </span>
                                ))}
                            </div>

                            {/* 4 Cards Grid of Achievements */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
                                {[
                                    { title: 'Active Streak', name: 'Dr. Riya Sharma', inst: 'AIIMS Delhi', detail: '412 Clinical Qs this month', badge: '🔥 Hot' },
                                    { title: 'Top Reviewer', name: 'Dr. Aarav Mehta', inst: 'CMC Vellore', detail: 'Daily streak active for 14 days', badge: '⚡ Streak' },
                                    { title: 'Mock Champion', name: 'Dr. Nisha Krishnan', inst: 'JIPMER Puducherry', detail: 'Top 9% in mock simulation', badge: '🏆 Champ' },
                                    { title: 'High Yield Master', name: 'Dr. Harsh Vardhan', inst: 'KGMU Lucknow', detail: '58 weak tags successfully resolved', badge: '🧠 Master' }
                                ].map((ach, idx) => (
                                    <div key={idx} className="p-3 rounded-lg bg-slate-950/40 border border-slate-800 hover:border-amber-500/20 transition-all flex flex-col justify-between space-y-1.5">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider">{ach.title}</span>
                                            <Badge variant="secondary" className="text-[8px] bg-slate-800 text-amber-500 hover:bg-slate-800 font-semibold px-1 py-0">{ach.badge}</Badge>
                                        </div>
                                        <div>
                                            <p className="text-xs font-bold text-white">{ach.name}</p>
                                            <p className="text-[9px] text-muted-foreground font-medium">{ach.inst}</p>
                                        </div>
                                        <p className="text-[9.5px] font-semibold text-emerald-400 border-t border-slate-850 pt-1 mt-1">{ach.detail}</p>
                                    </div>
                                ))}
                            </div>
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
                            <CardContent className="relative p-12 text-center flex flex-col items-center justify-center min-h-[320px]">
                                <Trophy className="w-14 h-14 mx-auto text-yellow-400/40 mb-3" />
                                <p className="text-lg font-bold text-foreground mb-2">No rankings yet</p>
                                <p className="text-muted-foreground mb-4">Start studying and practicing to appear on the leaderboard and earn XP!</p>
                                <button
                                    className="mt-2 px-5 py-2 rounded-lg bg-blue-600 text-white font-semibold shadow hover:bg-blue-700 transition-colors"
                                    onClick={() => router.push('/questions')}
                                >
                                    Practice Questions
                                </button>
                                {/* Subtle background illustration */}
                                <div className="absolute inset-0 pointer-events-none flex items-end justify-center z-0">
                                    <svg width="180" height="80" viewBox="0 0 180 80" fill="none" xmlns="http://www.w3.org/2000/svg" className="opacity-10 mb-2">
                                        <ellipse cx="90" cy="40" rx="80" ry="22" fill="#0ea5e9" />
                                    </svg>
                                </div>
                                <div className="mt-8 text-xs text-muted-foreground z-10">Compete with your peers and climb the leaderboard!</div>
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
                                                {entry.college && (
                                                    <p className="text-[10px] text-muted-foreground truncate mt-0.5">{entry.college}</p>
                                                )}
                                                <div className="flex items-center justify-center gap-1 mt-2">
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
                                                        {entry.college && (
                                                            <p className="text-[10px] text-muted-foreground truncate mt-0.5">{entry.college}</p>
                                                        )}
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
        </>
    );
}
