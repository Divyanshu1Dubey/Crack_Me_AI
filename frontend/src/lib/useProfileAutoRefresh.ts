'use client';
/**
 * useProfileAutoRefresh — keeps subscription / token info fresh on the
 * client without a hard page reload.
 *
 * Why this matters:
 *   - The TokenBalance daily/weekly counters reset at midnight (IST) on the
 *     backend. Without proactive refresh, the user sees a stale "0/10 used"
 *     pill until they manually F5 — which is the source of the "tokens didn't
 *     refresh at midnight" complaint.
 *   - The auto-refresh fires:
 *       1. Every 5 minutes (catches midnight reset within ±5 min).
 *       2. On `visibilitychange` → `visible` (tab regains focus).
 *       3. On `online` event (laptop wake from sleep).
 *
 * Usage:
 *   useProfileAutoRefresh();  // mount in any authenticated layout
 */
import { useEffect } from 'react';
import { useAuth } from './auth';

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export function useProfileAutoRefresh(): void {
    const { refreshProfile, isAuthenticated } = useAuth();

    useEffect(() => {
        if (!isAuthenticated || typeof window === 'undefined') return;

        // Periodic refresh
        const interval = window.setInterval(() => {
            void refreshProfile();
        }, REFRESH_INTERVAL_MS);

        // Refresh when user returns to the tab (most cases = post-sleep /
        // post-midnight / post-lunch)
        const onVisibility = () => {
            if (document.visibilityState === 'visible') {
                void refreshProfile();
            }
        };
        document.addEventListener('visibilitychange', onVisibility);

        // Refresh after reconnecting
        const onOnline = () => {
            void refreshProfile();
        };
        window.addEventListener('online', onOnline);

        return () => {
            window.clearInterval(interval);
            document.removeEventListener('visibilitychange', onVisibility);
            window.removeEventListener('online', onOnline);
        };
    }, [isAuthenticated, refreshProfile]);
}

export default useProfileAutoRefresh;
