// Shared types for the /leaderboard page. These mirror the backend
// `LeaderboardView` envelope (see backend/analytics/views.py).

export type LeaderboardPeriod = 'weekly' | 'monthly' | 'all';

/** "this week" / "this month" / "all time" — for labels. */
export function periodPhrase(period: LeaderboardPeriod): string {
    if (period === 'monthly') return 'this month';
    if (period === 'all') return 'all time';
    return 'this week';
}

/** Accuracy is null until the learner has completed a test. */
export function formatAccuracy(accuracy: number | null | undefined, digits = 1): string {
    return typeof accuracy === 'number' ? `${accuracy.toFixed(digits)}%` : '—';
}

export interface MePayload {
    user_id: number;
    username: string;
    rank: number | null;
    out_of: number;
    /** All-time XP. */
    xp_points: number;
    /** XP earned in the selected period (equals xp_points for "all"). */
    period_xp?: number;
    current_streak: number;
    longest_streak: number;
    total_study_days: number;
    accuracy: number | null;
    tests_completed: number;
    weekly_xp: number;
    weekly_goal_xp: number;
    college?: string;
}

export interface RivalPayload {
    user_id: number;
    username: string;
    /** XP in the selected period. */
    xp_points: number;
    current_streak: number;
    accuracy: number | null;
    xp_to_surpass: number;
    questions_to_surpass: number;
}

export interface LiveBoardRow {
    rank: number;
    user_id: number;
    username: string;
    /** XP in the selected period. */
    xp_points: number;
    current_streak: number;
    accuracy: number | null;
}

export interface InvitePayload {
    url: string;
    cta: string;
}

export interface LeaderboardEnvelope {
    kind: 'personal';
    period: LeaderboardPeriod;
    me: MePayload;
    rival: RivalPayload | null;
    live_board: LiveBoardRow[] | null;
    live_board_enabled: boolean;
    invite: InvitePayload;
}