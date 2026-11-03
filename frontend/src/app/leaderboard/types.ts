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

/**
 * How another learner is named: "@handle", or `fallback` when the API lists
 * them without a name (`username: null`: they never chose a handle, e.g. a
 * Google sign-up whose username was taken from their email address).
 */
export function learnerName(username: string | null | undefined, fallback: string): string {
    const handle = (username ?? '').trim();
    return handle ? `@${handle}` : fallback;
}

/**
 * The viewer's own board name for their card ("Others see you as
 * @learner_1a2b3c4d") and the label of the link to Settings, where the
 * username is changed. `null` when the payload has no `public_username`
 * (an envelope cached before the field existed).
 */
export function boardIdentity(publicUsername: string | null | undefined): { label: string; action: string } | null {
    if (publicUsername === undefined) return null;
    const name = learnerName(publicUsername, '');
    return name
        ? { label: `Others see you as ${name}`, action: 'Change' }
        : { label: 'Others see you without a name', action: 'Choose a username' };
}

export interface MePayload {
    user_id: number;
    /** The viewer's own display name (their name, else their username). */
    username: string;
    /** What other learners see: a username they chose, or null (listed without a name). */
    public_username?: string | null;
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
    /** A handle the learner chose, or null (shown without a name, see learnerName). */
    username: string | null;
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
    /** A handle the learner chose, or null (shown without a name, see learnerName). */
    username: string | null;
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