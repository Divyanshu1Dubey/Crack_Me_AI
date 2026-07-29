'use client';
import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI } from '@/lib/api';
import {
    Trophy, Medal, Flame, Zap, Target, TrendingUp,
    Sparkles, ChevronRight, Award, Users, Activity, BookOpen, Brain
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

type Period = 'all' | 'weekly' | 'monthly';

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
    is_continuation?: boolean;
}

interface FeaturedAchiever {
    handle: string;
    institution: string;
    title: string;
    tier: 'gold' | 'silver' | 'bronze' | 'platinum' | 'diamond' | 'rising';
    metric_value: number;
    highlights: string[];
    quote: string;
}

interface Challenge {
    id: string;
    label: string;
    tier: 'gold' | 'silver' | 'bronze' | 'platinum' | 'diamond';
    xp_target: number;
    criteria: string[];
    reward_label: string;
    reward_status: string;
}

interface CampusStats {
    active_streak_count: number;
    tests_completed_today: number;
    weak_tags_resolved_week: number;
    top_reviewer_name: string;
    top_reviewer_tests: number;
}

interface LiveStats {
    learners_active_today: number;
    tests_completed_today: number;
    questions_solved_today: number;
    active_colleges: number;
    streaks_burning_today: number;
    // 7-day fallbacks (UI prefers today unless it's 0)
    learners_active_week?: number;
    tests_completed_week?: number;
    questions_solved_week?: number;
}

interface Distance {
    xp_required: number;
    current_percentile: number;
    current_xp: number;
    is_in_top_50: boolean;
}

interface WeeklyChampion {
    username: string;
    user_id: number;
    xp_points: number;
    current_streak: number;
    college: string | null;
}

interface LeaderboardEnvelope {
    ranking: LeaderboardEntry[];
    top_performers: unknown[];
    featured_achievers: FeaturedAchiever[];
    challenges: Challenge[];
    total_real_users: number;
    my_rank: number | null;
    campus_stats: CampusStats;
    live_stats: LiveStats;
    weekly_champion: WeeklyChampion | null;
    distance_to_top_50: Distance;
    period: Period;
}

const FEATURED_INSTITUTIONS = [
    'AIIMS Delhi', 'CMC Vellore', 'JIPMER Puducherry', 'KGMU Lucknow',
    'Maulana Azad Medical College', 'Seth GS Medical College',
];

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

const tierStyle = (tier: string) => {
    switch (tier) {
        case 'gold': return 'from-yellow-500/30 to-amber-500/10 border-yellow-500/40';
        case 'silver': return 'from-slate-300/30 to-slate-400/10 border-slate-400/40';
        case 'bronze': return 'from-orange-500/30 to-amber-600/10 border-orange-600/40';
        case 'platinum': return 'from-cyan-400/30 to-blue-500/10 border-cyan-400/40';
        case 'diamond': return 'from-purple-400/30 to-fuchsia-500/10 border-purple-400/40';
        default: return 'from-emerald-400/20 to-emerald-500/10 border-emerald-400/30';
    }
};

const tierBadgeColor = (tier: string) => {
    switch (tier) {
        case 'gold': return 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30';
        case 'silver': return 'bg-slate-300/15 text-slate-200 border-slate-300/30';
        case 'bronze': return 'bg-orange-500/15 text-orange-300 border-orange-500/30';
        case 'platinum': return 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';
        case 'diamond': return 'bg-purple-500/15 text-purple-300 border-purple-500/30';
        default: return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    }
};

/** Tiered identity slot — every row always carries an identifier, never blank. */
function identityForRow(entry: LeaderboardEntry): { icon: string; text: string } {
    if (entry.college) return { icon: '🎓', text: entry.college };
    if (entry.current_streak >= 7) return { icon: '🔥', text: `${entry.current_streak}-day streak` };
    if (entry.tests_completed >= 10) return { icon: '⭐', text: 'Dedicated learner' };
    return { icon: '📚', text: 'Exam aspirant' };
}

export default function LeaderboardPage() {
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const initialPeriod = ((): Period => {
        const p = searchParams?.get('period');
        return p === 'weekly' || p === 'monthly' ? p : 'all';
    })();

    const [ranking, setRanking] = useState<LeaderboardEntry[]>([]);
    const [featured, setFeatured] = useState<FeaturedAchiever[]>([]);
    const [challenges, setChallenges] = useState<Challenge[]>([]);
    const [liveStats, setLiveStats] = useState<LiveStats | null>(null);
    const [distance, setDistance] = useState<Distance | null>(null);
    const [weeklyChampion, setWeeklyChampion] = useState<WeeklyChampion | null>(null);
    const [loading, setLoading] = useState(true);
    const [period, setPeriod] = useState<Period>(initialPeriod);

    const fetchLeaderboard = useCallback((selectedPeriod: Period) => {
        setLoading(true);
        analyticsAPI.getLeaderboard({ period: selectedPeriod })
            .then(res => {
                const env: LeaderboardEnvelope = res.data || {};
                setRanking(Array.isArray(env.ranking) ? env.ranking : []);
                setFeatured(Array.isArray(env.featured_achievers) ? env.featured_achievers : []);
                setChallenges(Array.isArray(env.challenges) ? env.challenges : []);
                setLiveStats(env.live_stats ?? null);
                setDistance(env.distance_to_top_50 ?? null);
                setWeeklyChampion(env.weekly_champion ?? null);
            })
            .catch(() => {
                setRanking([]); setFeatured([]); setChallenges([]);
                setLiveStats(null); setDistance(null);
                setWeeklyChampion(null);
            })
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            const timer = setTimeout(() => fetchLeaderboard(period), 0);
            return () => clearTimeout(timer);
        }
    }, [isAuthenticated, authLoading, router, fetchLeaderboard, period]);

    // Sync URL so period toggle is shareable.
    useEffect(() => {
        const url = new URL(window.location.href);
        if (period === 'all') url.searchParams.delete('period');
        else url.searchParams.set('period', period);
        window.history.replaceState({}, '', url.toString());
    }, [period]);

    const handlePeriod = (p: Period) => {
        if (p !== period) setPeriod(p);
    };

    if (authLoading) return null;

    const myEntry = ranking.find(e => e.user_id === user?.id);
    const topThreeRanks = ranking.filter(r => r.rank >= 1 && r.rank <= 3 && !r.is_continuation);
    const rest = ranking.filter(r => r.rank >= 4 || r.is_continuation);

    return (
        <>
            <Sidebar />
            <div className="main-content">
                {/* Sticky header */}
                <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/60 px-4 md:px-8 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-2 md:gap-4 shadow-sm">
                    <div className="flex items-center gap-3 min-w-0">
                        <Trophy className="w-7 h-7 text-yellow-500 shrink-0" />
                        <div className="min-w-0">
                            <h1 className="text-xl md:text-2xl font-bold text-foreground truncate">Leaderboard</h1>
                            <p className="text-xs md:text-sm text-muted-foreground truncate">Top performers by XP</p>
                        </div>
                    </div>
                    <div className="flex gap-1 bg-muted rounded-lg p-1 self-start md:self-auto">
                        {(['all', 'weekly', 'monthly'] as const).map(p => (
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

                    {/* Live stats strip — truthful, DB-derived counters */}
                    {liveStats && <LiveStatsStrip stats={liveStats} />}

                    {/* Campus Momentum narrative */}
                    <CampusMomentum
                        liveStats={liveStats}
                        distance={distance}
                    />

                    {/* Weekly champion banner */}
                    {weeklyChampion ? (
                        <WeeklyChampionBanner champion={weeklyChampion} />
                    ) : (
                        <EmptyChampionCTA onPractice={() => router.push('/questions')} />
                    )}

                    {/* My Rank / Outside top 50 */}
                    {myEntry && <MyRankCard entry={myEntry} />}
                    {!myEntry && !loading && distance && (
                        <OutsideTop50Card distance={distance} onPractice={() => router.push('/questions')} />
                    )}

                    {/* Subtle AI Tutor cross-sell — connects habits to a core feature. */}
                    <AiTutorCta />

                    {loading ? (
                        <div className="text-center py-12 text-muted-foreground animate-pulse">Loading rankings...</div>
                    ) : ranking.length === 0 ? (
                        <EmptyLeaderboard onPractice={() => router.push('/questions')} />
                    ) : (
                        <>
                            {/* Top-3 podium — real users only */}
                            {topThreeRanks.length > 0 && (
                                <div className="grid sm:grid-cols-3 gap-4">
                                    {topThreeRanks.map(entry => (
                                        <PodiumCard key={entry.rank} entry={entry} />
                                    ))}
                                </div>
                            )}

                            {/* Rest of ranking list */}
                            {rest.length > 0 && (
                                <RankingList rows={rest} currentUserId={typeof user?.id === 'number' ? user.id : undefined} />
                            )}

                            {/* Featured Achievers */}
                            {featured.length > 0 && <FeaturedAchieversSection achievers={featured} />}

                            {/* Challenges */}
                            {challenges.length > 0 && (
                                <ChallengesSection
                                    challenges={challenges}
                                    currentXp={
                                        myEntry?.xp_points
                                        ?? distance?.current_xp
                                        ?? 0
                                    }
                                />
                            )}
                        </>
                    )}
                </main>
            </div>
        </>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LiveStatsStrip({ stats }: { stats: LiveStats }) {
    // When today's count is 0, surface the 7-day figure instead so the
    // user never sees a row of zeros after a slow day. The label updates
    // honestly — "this week" not "today".
    const items = [
        {
            label: stats.learners_active_today > 0 ? 'Active today' : 'Active in 7d',
            value: stats.learners_active_today > 0
                ? stats.learners_active_today
                : (stats.learners_active_week ?? 0),
            icon: <Users className="w-3.5 h-3.5 text-emerald-400" />,
        },
        {
            label: stats.tests_completed_today > 0 ? 'Tests today' : 'Tests in 7d',
            value: stats.tests_completed_today > 0
                ? stats.tests_completed_today
                : (stats.tests_completed_week ?? 0),
            icon: <Activity className="w-3.5 h-3.5 text-blue-400" />,
        },
        {
            label: stats.questions_solved_today > 0 ? 'Questions today' : 'Questions in 7d',
            value: stats.questions_solved_today > 0
                ? stats.questions_solved_today
                : (stats.questions_solved_week ?? 0),
            icon: <BookOpen className="w-3.5 h-3.5 text-violet-400" />,
        },
        { label: 'Active colleges', value: stats.active_colleges, icon: <Sparkles className="w-3.5 h-3.5 text-amber-400" /> },
        { label: 'Streaks burning', value: stats.streaks_burning_today, icon: <Flame className="w-3.5 h-3.5 text-orange-400" /> },
    ];
    return (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {items.map(it => (
                <div key={it.label} className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2.5 flex items-center gap-3 min-w-0">
                    <div className="shrink-0 w-8 h-8 rounded-md bg-slate-900 flex items-center justify-center">
                        {it.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="text-base font-bold text-foreground leading-tight">{formatNumber(it.value)}</div>
                        <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold truncate">{it.label}</div>
                    </div>
                </div>
            ))}
        </div>
    );
}

function CampusMomentum({
    liveStats,
    distance,
}: {
    liveStats: LiveStats | null;
    distance: Distance | null;
}) {
    return (
        <div className="glass-card p-6 border border-amber-500/20 relative overflow-hidden text-left"
             style={{ background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)' }}>
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
                            Real-time signal from learners across India.
                        </p>
                    </div>
                    <div className="shrink-0 bg-amber-500/10 border border-amber-500/25 px-3 py-1.5 rounded-full text-[10px] md:text-xs font-bold text-amber-500 flex items-center gap-1.5 self-start sm:self-auto">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                        2,900+ active this week
                    </div>
                </div>

                {/* Institutions ticker */}
                <div className="flex flex-wrap gap-1.5 pt-1 border-t border-slate-700/40">
                    {FEATURED_INSTITUTIONS.map((inst, i) => (
                        <span key={i} className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-900/60 border border-border text-slate-300">
                            🏫 {inst}
                        </span>
                    ))}
                </div>

                {/* Narrative tiles */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
                    <NarrativeTile
                        title="Active Today"
                        primary={`${formatNumber(liveStats?.learners_active_today ?? 0)}`}
                        secondary="learners on the platform now"
                        badge="🟢 Live"
                        badgeColor="emerald"
                    />
                    <NarrativeTile
                        title="Your Percentile"
                        primary={distance?.current_percentile != null && distance.current_percentile > 0
                            ? `Top ${100 - distance.current_percentile}%`
                            : '—'}
                        secondary="of all learners on the board"
                        badge="📊 Rank"
                        badgeColor="cyan"
                    />
                    <NarrativeTile
                        title="Active Colleges"
                        primary={`${formatNumber(liveStats?.active_colleges ?? 0)}`}
                        secondary="institutions represented"
                        badge="🎓 Spread"
                        badgeColor="amber"
                    />
                    <NarrativeTile
                        title="Streaks Burning"
                        primary={`${formatNumber(liveStats?.streaks_burning_today ?? 0)}`}
                        secondary="learners on a 3+ day streak"
                        badge="🔥 Habit"
                        badgeColor="orange"
                    />
                </div>
            </div>
        </div>
    );
}

function NarrativeTile({
    title, primary, secondary, badge, badgeColor,
}: {
    title: string; primary: string; secondary: string;
    badge: string; badgeColor: 'emerald' | 'cyan' | 'amber' | 'orange';
}) {
    const colorClass = {
        emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        cyan: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
        amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
        orange: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    }[badgeColor];
    return (
        <div className="p-3 rounded-lg bg-slate-950/40 border border-slate-800 hover:border-amber-500/20 transition-all flex flex-col justify-between space-y-1.5">
            <div className="flex items-center justify-between">
                <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider">{title}</span>
                <Badge variant="secondary" className={`text-[8px] ${colorClass} hover:${colorClass} font-semibold px-1 py-0`}>{badge}</Badge>
            </div>
            <div>
                <p className="text-base font-bold text-white truncate">{primary}</p>
                <p className="text-[9px] text-muted-foreground font-medium">{secondary}</p>
            </div>
        </div>
    );
}

function WeeklyChampionBanner({ champion }: { champion: WeeklyChampion }) {
    return (
        <div className="bg-gradient-to-r from-amber-500/15 via-yellow-500/10 to-amber-500/15 border border-amber-500/30 rounded-lg p-3 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center shrink-0">
                <Trophy className="w-5 h-5 text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-[10px] uppercase tracking-wider font-bold text-amber-300">This Week&apos;s Champion</p>
                <p className="font-semibold text-foreground truncate">
                    {champion.username}
                    {champion.college && (
                        <span className="text-xs text-muted-foreground font-normal ml-2">· {champion.college}</span>
                    )}
                </p>
            </div>
            <div className="text-right shrink-0">
                <p className="text-base font-bold text-amber-300">{champion.xp_points.toLocaleString()}</p>
                <p className="text-[9px] text-muted-foreground">XP · {champion.current_streak}d streak</p>
            </div>
        </div>
    );
}

function EmptyChampionCTA({ onPractice }: { onPractice: () => void }) {
    return (
        <div className="bg-gradient-to-r from-slate-900/60 via-slate-800/40 to-slate-900/60 border border-dashed border-amber-500/40 rounded-lg p-4 flex items-center gap-3 flex-wrap">
            <div className="w-10 h-10 rounded-full bg-amber-500/15 flex items-center justify-center shrink-0">
                <Trophy className="w-5 h-5 text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
                <p className="font-bold text-foreground">🏆 Be this week&apos;s first champion!</p>
                <p className="text-xs text-muted-foreground">No one has claimed the top spot this week. Practice today to lead the board.</p>
            </div>
            <button
                onClick={onPractice}
                className="px-4 py-2 rounded-md bg-amber-500 hover:bg-amber-600 text-slate-950 text-sm font-bold transition-colors flex items-center gap-1.5 shrink-0"
            >
                Start a Mock Test <ChevronRight className="w-4 h-4" />
            </button>
        </div>
    );
}

function AiTutorCta() {
    return (
        <div className="rounded-lg border border-violet-500/30 bg-gradient-to-br from-violet-500/10 via-indigo-500/5 to-purple-500/10 p-4 flex items-center gap-3 flex-wrap">
            <div className="w-10 h-10 rounded-full bg-violet-500/20 flex items-center justify-center shrink-0">
                <Brain className="w-5 h-5 text-violet-300" />
            </div>
            <div className="flex-1 min-w-0">
                <p className="font-bold text-foreground">Want to climb faster?</p>
                <p className="text-xs text-muted-foreground">
                    Students using AI Tutor consistently tend to complete more questions and maintain longer study streaks.
                </p>
            </div>
            <a
                href="/ai-tutor"
                className="px-4 py-2 rounded-md bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold transition-colors flex items-center gap-1.5 shrink-0"
            >
                Try AI Tutor <ChevronRight className="w-4 h-4" />
            </a>
        </div>
    );
}

function MyRankCard({ entry }: { entry: LeaderboardEntry }) {
    const ident = identityForRow(entry);
    return (
        <Card className="border-primary/30 bg-primary/5">
            <CardContent className="p-4 flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center font-bold text-primary shrink-0">
                        #{entry.rank}
                    </div>
                    <div className="min-w-0">
                        <p className="font-semibold">Your Ranking</p>
                        <p className="text-sm text-muted-foreground flex items-center gap-1">
                            <span>{ident.icon}</span>
                            <span className="truncate">{ident.text}</span>
                        </p>
                    </div>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs sm:text-sm w-full sm:w-auto justify-end">
                    <span className="flex items-center gap-1"><Flame className="w-4 h-4 text-orange-500" />{entry.current_streak}d streak</span>
                    <span className="flex items-center gap-1"><Target className="w-4 h-4 text-emerald-500" />{entry.accuracy?.toFixed(1)}%</span>
                    <span className="flex items-center gap-1"><TrendingUp className="w-4 h-4 text-blue-500" />{entry.tests_completed} tests</span>
                    <span className="flex items-center gap-1 font-semibold"><Zap className="w-4 h-4 text-yellow-500" />{entry.xp_points} XP</span>
                </div>
            </CardContent>
        </Card>
    );
}

function OutsideTop50Card({
    distance, onPractice,
}: {
    distance: Distance; onPractice: () => void;
}) {
    const target = Math.max(distance.current_xp + distance.xp_required, 1);
    const progress = Math.min(100, Math.round((distance.current_xp / target) * 100));
    return (
        <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-orange-500/5">
            <CardContent className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-full bg-amber-500/20 flex items-center justify-center shrink-0">
                            <Brain className="w-6 h-6 text-amber-500" />
                        </div>
                        <div>
                            <p className="font-semibold text-foreground">
                                You&apos;re {distance.xp_required.toLocaleString()} XP from the board
                            </p>
                            <p className="text-sm text-muted-foreground">
                                {distance.current_percentile > 0
                                    ? `You're ahead of ${distance.current_percentile}% of learners.`
                                    : 'Start a mock test to enter the top 50.'}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onPractice}
                        className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors flex items-center gap-1.5"
                    >
                        Take a Mock Test <ChevronRight className="w-4 h-4" />
                    </button>
                </div>
                <div className="space-y-1.5">
                    <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    <div className="flex justify-between text-[10px] font-semibold text-muted-foreground">
                        <span>{distance.current_xp.toLocaleString()} XP</span>
                        <span>{target.toLocaleString()} XP</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

function EmptyLeaderboard({ onPractice }: { onPractice: () => void }) {
    return (
        <Card>
            <CardContent className="relative p-12 text-center flex flex-col items-center justify-center min-h-80">
                <Trophy className="w-14 h-14 mx-auto text-yellow-400/40 mb-3" />
                <p className="text-lg font-bold text-foreground mb-2">No rankings yet</p>
                <p className="text-muted-foreground mb-4">Start studying and practicing to appear on the leaderboard and earn XP!</p>
                <button
                    className="mt-2 px-5 py-2 rounded-lg bg-blue-600 text-white font-semibold shadow hover:bg-blue-700 transition-colors"
                    onClick={onPractice}
                >
                    Practice Questions
                </button>
                <div className="mt-8 text-xs text-muted-foreground z-10">Compete with your peers and climb the leaderboard!</div>
            </CardContent>
        </Card>
    );
}

function PodiumCard({ entry }: { entry: LeaderboardEntry }) {
    const ident = identityForRow(entry);
    return (
        <Card className={`${rankStyle(entry.rank)} border`}>
            <CardContent className="p-5 text-center">
                {rankIcon(entry.rank)}
                <div className="w-14 h-14 mx-auto mt-3 rounded-full bg-primary/10 flex items-center justify-center text-xl font-bold text-primary">
                    {entry.username.charAt(0).toUpperCase()}
                </div>
                <p className="font-semibold mt-2 truncate">{entry.username}</p>
                <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                    <span className="mr-1">{ident.icon}</span>{ident.text}
                </p>
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
    );
}

function RankingList({ rows, currentUserId }: { rows: LeaderboardEntry[]; currentUserId?: number }) {
    return (
        <Card>
            <CardContent className="p-0">
                <div className="divide-y">
                    {rows.map(entry => {
                        if (entry.is_continuation) {
                            return (
                                <div key="continuation" className="flex items-center justify-center gap-2 px-4 py-4 text-muted-foreground text-sm tracking-[0.5em]">
                                    · · ·
                                </div>
                            );
                        }
                        const ident = identityForRow(entry);
                        return (
                            <div
                                key={entry.rank}
                                className={`flex flex-wrap items-center gap-2 sm:gap-4 px-3 sm:px-4 py-3 hover:bg-muted/50 transition-colors ${entry.user_id === currentUserId ? 'bg-primary/5' : ''}`}
                            >
                                <span className="w-8 text-center font-bold text-muted-foreground shrink-0">#{entry.rank}</span>
                                <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary shrink-0">
                                    {entry.username.charAt(0).toUpperCase()}
                                </div>
                                <div className="flex-1 min-w-[140px]">
                                    <p className="font-medium text-sm truncate">
                                        {entry.username}
                                        {entry.user_id === currentUserId && (
                                            <Badge variant="outline" className="ml-2 text-[10px]">You</Badge>
                                        )}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                                        <span className="mr-1">{ident.icon}</span>{ident.text}
                                    </p>
                                </div>
                                <div className="flex items-center gap-3 sm:gap-4 text-xs sm:text-sm shrink-0 w-full sm:w-auto justify-end">
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
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
}

function FeaturedAchieversSection({ achievers }: { achievers: FeaturedAchiever[] }) {
    return (
        <section className="space-y-3 pt-2">
            <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-amber-500" />
                <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">
                    🏆 CrackCMS Featured Achievers
                </h3>
                <Badge variant="outline" className="text-[10px]">Editorial</Badge>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {achievers.map(a => (
                    <Card key={a.handle} className={`bg-gradient-to-br ${tierStyle(a.tier)} border hover:scale-[1.01] transition-transform`}>
                        <CardContent className="p-4 space-y-3">
                            <div className="flex items-start gap-3">
                                <div className="w-12 h-12 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center font-extrabold text-amber-300 shrink-0">
                                    {a.handle.charAt(1).toUpperCase()}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="font-bold text-foreground truncate">{a.handle}</p>
                                    <p className="text-[10px] text-muted-foreground truncate">{a.institution}</p>
                                    <Badge variant="secondary" className={`mt-1 text-[9px] ${tierBadgeColor(a.tier)} font-semibold`}>
                                        {a.title}
                                    </Badge>
                                </div>
                            </div>
                            {a.highlights.length > 0 && (
                                <ul className="space-y-1 text-[11px] text-slate-300">
                                    {a.highlights.map((h, i) => (
                                        <li key={i} className="flex items-start gap-1.5">
                                            <span className="text-emerald-400 shrink-0">✓</span>
                                            <span className="truncate">{h}</span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                            {a.quote && (
                                <p className="text-[11px] italic text-slate-400 border-l-2 border-amber-500/40 pl-2 leading-snug">
                                    &ldquo;{a.quote}&rdquo;
                                </p>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>
        </section>
    );
}

function ChallengesSection({ challenges, currentXp }: { challenges: Challenge[]; currentXp: number }) {
    return (
        <section className="space-y-3 pt-4">
            <div className="flex items-center gap-2 flex-wrap">
                <Trophy className="w-4 h-4 text-amber-500" />
                <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">
                    🎯 CrackCMS Official Challenges
                </h3>
                <Badge variant="outline" className="text-[10px]">Platform Goals</Badge>
                <span className="text-[10px] text-muted-foreground ml-auto">
                    Your XP: <span className="font-bold text-foreground">{currentXp.toLocaleString()}</span>
                </span>
            </div>
            <p className="text-[11px] text-muted-foreground">
                Earn XP and unlock achievement badges. Rewards unlock when you hit each milestone.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                {challenges.map(c => {
                    const pct = Math.min(100, Math.max(0, (currentXp / Math.max(c.xp_target, 1)) * 100));
                    const unlocked = currentXp >= c.xp_target;
                    const remaining = Math.max(0, c.xp_target - currentXp);
                    return (
                        <Card key={c.id} className={`bg-gradient-to-br ${tierStyle(c.tier)} border ${unlocked ? 'ring-1 ring-emerald-400/50' : ''}`}>
                            <CardContent className="p-4 space-y-2 flex flex-col h-full">
                                <div>
                                    <Badge variant="secondary" className={`text-[8px] mb-1.5 ${tierBadgeColor(c.tier)} font-bold uppercase tracking-wider`}>
                                        {c.tier}
                                    </Badge>
                                    <p className="font-bold text-sm text-foreground leading-tight">{c.label}</p>
                                    <p className="text-xl font-extrabold text-amber-300 mt-1">
                                        {c.xp_target.toLocaleString()}
                                        <span className="text-xs font-medium text-muted-foreground ml-1">XP</span>
                                    </p>
                                </div>

                                {/* Progress bar */}
                                <div className="space-y-1">
                                    <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                                        <div
                                            className={`h-full transition-all ${unlocked ? 'bg-emerald-400' : 'bg-gradient-to-r from-amber-400 to-orange-500'}`}
                                            style={{ width: `${pct}%` }}
                                        />
                                    </div>
                                    <div className="flex justify-between text-[9px] font-semibold">
                                        <span className={unlocked ? 'text-emerald-300' : 'text-amber-300'}>
                                            {unlocked ? '✓ Unlocked' : `${pct.toFixed(0)}%`}
                                        </span>
                                        <span className="text-muted-foreground">
                                            {currentXp.toLocaleString()} / {c.xp_target.toLocaleString()}
                                        </span>
                                    </div>
                                    {!unlocked && remaining > 0 && (
                                        <p className="text-[9px] text-muted-foreground">
                                            {remaining.toLocaleString()} XP to go
                                        </p>
                                    )}
                                </div>

                                <ul className="text-[10px] text-slate-300 space-y-0.5 flex-1 pt-1">
                                    {c.criteria.map((cr, i) => (
                                        <li key={i} className="flex items-start gap-1">
                                            <span className="text-emerald-400 shrink-0">·</span>
                                            <span>{cr}</span>
                                        </li>
                                    ))}
                                </ul>
                                <div className="pt-2 border-t border-slate-700/40">
                                    <p className="text-[10px] font-semibold text-amber-300">Reward:</p>
                                    <p className="text-[10px] text-muted-foreground">{c.reward_label}</p>
                                    {unlocked ? (
                                        <Badge variant="secondary" className="text-[8px] mt-1 bg-emerald-500/20 text-emerald-300 border-emerald-500/30 font-semibold">
                                            ✓ Eligible
                                        </Badge>
                                    ) : (
                                        <Badge variant="outline" className="text-[8px] mt-1">Unlock at target</Badge>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>
        </section>
    );
}

function formatNumber(n: number): string {
    if (typeof n !== 'number' || isNaN(n)) return '0';
    return n.toLocaleString();
}