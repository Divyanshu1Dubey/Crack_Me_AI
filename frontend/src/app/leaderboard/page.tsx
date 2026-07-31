'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI } from '@/lib/api';

import EmptyRankCTA from './components/EmptyRankCTA';
import InviteGate from './components/InviteGate';
import LiveBoard from './components/LiveBoard';
import MyRankCard from './components/MyRankCard';
import RivalCard from './components/RivalCard';
import WeeklyStatsRow from './components/WeeklyStatsRow';
import type { LeaderboardEnvelope } from './types';

const PERIODS: Array<{ key: 'weekly' | 'monthly' | 'all'; label: string }> = [
    { key: 'weekly', label: 'This Week' },
    { key: 'monthly', label: 'This Month' },
    { key: 'all', label: 'All Time' },
];

export default function LeaderboardPage() {
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    const initialPeriod = normalizePeriod(searchParams.get('period'));
    const [period, setPeriod] = useState<'weekly' | 'monthly' | 'all'>(initialPeriod);
    const [envelope, setEnvelope] = useState<LeaderboardEnvelope | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const userId: number | undefined = typeof user?.id === 'number' ? user.id : undefined;

    const fetchEnvelope = useCallback(
        async (selectedPeriod: 'weekly' | 'monthly' | 'all') => {
            setLoading(true);
            setError(null);
            try {
                const res = await analyticsAPI.getLeaderboard(selectedPeriod);
                setEnvelope(res.data as LeaderboardEnvelope);
            } catch {
                setEnvelope(null);
                setError('Could not load your leaderboard. Please try again.');
            } finally {
                setLoading(false);
            }
        },
        [],
    );

    // Auth + initial load
    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
            return;
        }
        if (isAuthenticated) {
            fetchEnvelope(period);
        }
    }, [authLoading, isAuthenticated, period, router, fetchEnvelope]);

    // URL sync — keep ?period= shareable.
    const handlePeriod = (next: 'weekly' | 'monthly' | 'all') => {
        if (next === period) return;
        setPeriod(next);
        if (typeof window !== 'undefined') {
            const url = new URL(window.location.href);
            url.searchParams.set('period', next);
            window.history.replaceState(null, '', url.toString());
        }
    };

    if (authLoading) return null;

    const me = envelope?.me ?? null;
    const rival = envelope?.rival ?? null;
    const liveBoard = envelope?.live_board ?? null;
    const liveEnabled = envelope?.live_board_enabled ?? false;
    const invite = envelope?.invite ?? null;

    const showEmptyState = !loading && me && me.xp_points === 0;

    return (
        <>
            <Sidebar />
            <div className="main-content">
                <Header />
                <main className="flex-1 p-4 md:p-6 page-container space-y-6">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 md:gap-4">
                        <div className="min-w-0">
                            <h1 className="text-xl md:text-2xl font-bold text-foreground truncate">Your Leaderboard</h1>
                            <p className="text-xs md:text-sm text-muted-foreground truncate">
                                Personal rank, weekly goal, and one real learner to chase.
                            </p>
                        </div>
                        <div className="flex gap-1 bg-muted rounded-lg p-1 self-start md:self-auto">
                            {PERIODS.map((p) => (
                                <button
                                    key={p.key}
                                    type="button"
                                    onClick={() => handlePeriod(p.key)}
                                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                                        period === p.key
                                            ? 'bg-background shadow text-foreground'
                                            : 'text-muted-foreground hover:text-foreground'
                                    }`}
                                    aria-pressed={period === p.key}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    {loading && (
                        <div className="text-center py-12 text-muted-foreground animate-pulse">
                            Loading your stats…
                        </div>
                    )}

                    {!loading && error && (
                        <div
                            role="alert"
                            className="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive"
                        >
                            {error}
                        </div>
                    )}

                    {!loading && !error && showEmptyState && <EmptyRankCTA />}

                    {!loading && !error && !showEmptyState && me && (
                        <>
                            <MyRankCard me={me} />

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <RivalCard rival={rival} meRank={me.rank} meXp={me.xp_points} />
                                {invite && !liveEnabled && <InviteGate invite={invite} />}
                            </div>

                            <WeeklyStatsRow me={me} />

                            {liveEnabled && liveBoard && (
                                <LiveBoard rows={liveBoard} myUserId={userId} />
                            )}
                        </>
                    )}

                    {!loading && !error && !me && (
                        <EmptyRankCTA />
                    )}
                </main>
            </div>
        </>
    );
}

function normalizePeriod(raw: string | null): 'weekly' | 'monthly' | 'all' {
    if (raw === 'monthly' || raw === 'all' || raw === 'weekly') return raw;
    return 'weekly';
}