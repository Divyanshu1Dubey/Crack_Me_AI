'use client';

/**
 * LeaderboardAnalytics.tsx — Tracks leaderboard tab switches + CTAs.
 *
 * Drop inside `/leaderboard`. Emits `leaderboard_view` on mount and
 * `leaderboard_tab_switch` whenever the period changes (all/weekly/
 * monthly).
 */

import { useEffect, useRef } from 'react';
import { analytics } from '@/lib/analytics';

export default function LeaderboardAnalytics({ period }: { period: string }) {
    const lastPeriod = useRef<string | null>(null);

    useEffect(() => {
        if (lastPeriod.current === null) {
            analytics.leaderboardView(period);
        } else if (lastPeriod.current !== period) {
            analytics.leaderboardTabSwitch(lastPeriod.current, period);
        }
        lastPeriod.current = period;
    }, [period]);

    return null;
}