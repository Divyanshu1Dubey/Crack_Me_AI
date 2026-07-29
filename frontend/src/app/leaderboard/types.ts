// Shared types for the /leaderboard page. These mirror the backend
// `LeaderboardView` envelope (see backend/analytics/views.py).

export interface MePayload {
    user_id: number;
    username: string;
    rank: number | null;
    out_of: number;
    xp_points: number;
    current_streak: number;
    longest_streak: number;
    total_study_days: number;
    accuracy: number;
    tests_completed: number;
    weekly_xp: number;
    weekly_goal_xp: number;
    college?: string;
}

export interface RivalPayload {
    user_id: number;
    username: string;
    xp_points: number;
    current_streak: number;
    accuracy: number;
    xp_to_surpass: number;
    questions_to_surpass: number;
    college?: string;
}

export interface LiveBoardRow {
    rank: number;
    user_id: number;
    username: string;
    xp_points: number;
    current_streak: number;
    accuracy: number;
    college?: string;
}

export interface InvitePayload {
    url: string;
    cta: string;
    current_referrals: number;
}

export interface LeaderboardEnvelope {
    kind: 'personal';
    period: 'weekly' | 'monthly' | 'all';
    me: MePayload;
    rival: RivalPayload | null;
    live_board: LiveBoardRow[] | null;
    live_board_enabled: boolean;
    invite: InvitePayload;
}