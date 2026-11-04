'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useExamTrack } from '@/components/ExamTrackProvider';
import { landingHref, landingPageOf } from '@/lib/preferences';
import { useUiPreferences } from './usePreferences';

/**
 * The opening page (Settings > Customise > "Open the app on").
 *
 * Every sign-in lands on /dashboard with a full page load (lib/authNavigation.ts), and so does
 * opening the app from a bookmark or the address bar. On such a load the dashboard sends the learner
 * to the page they chose, once per page load. A reload of the dashboard, the back button and every
 * in-app link to the dashboard (sidebar, logo, bottom bar) open the dashboard itself.
 */

/** The opening page was settled for this page load (module state: it resets on the next full load). */
let settled = false;
/** Longest wait for the server when this browser has no copy of the preferences yet. */
const WAIT_FOR_SERVER_MS = 2500;

/** True when this document was a fresh load of /dashboard (not a reload or a back / forward visit). */
export function openedOnDashboard(): boolean {
    try {
        const [entry] = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[];
        if (!entry || entry.type !== 'navigate') return false;
        return new URL(entry.name).pathname.replace(/\/+$/, '') === '/dashboard';
    } catch {
        return false;
    }
}

export type LandingState = 'checking' | 'redirecting' | 'stay';

/**
 * `checking` while the dashboard decides (render a placeholder), `redirecting` once it left for the
 * opening page, `stay` to show the dashboard. `ready`: the user is signed in (useRequireAuth).
 */
export function useLandingRedirect(ready: boolean): LandingState {
    const router = useRouter();
    const { prefs, loaded, fromCache } = useUiPreferences();
    const { activeTrack, hydrated } = useExamTrack();
    const [state, setState] = useState<LandingState>(() => (settled ? 'stay' : 'checking'));
    const [waitedEnough, setWaitedEnough] = useState(false);

    useEffect(() => {
        if (state !== 'checking' || !ready) return;
        const timeout = window.setTimeout(() => setWaitedEnough(true), WAIT_FOR_SERVER_MS);
        return () => window.clearTimeout(timeout);
    }, [state, ready]);

    useEffect(() => {
        if (state !== 'checking' || !ready) return;
        if (settled || !openedOnDashboard()) {
            settled = true;
            setState('stay');
            return;
        }
        // This browser's copy decides at once; without one, wait (briefly) for the server.
        // The exam track picks the question bank's player. Never longer than WAIT_FOR_SERVER_MS.
        if ((!loaded && !fromCache) || !hydrated) {
            if (!waitedEnough) return;
        }
        settled = true;
        const page = landingPageOf(prefs);
        if (page === 'dashboard') {
            setState('stay');
            return;
        }
        setState('redirecting');
        router.replace(landingHref(page, hydrated ? activeTrack : 'cms'));
    }, [state, ready, loaded, fromCache, waitedEnough, hydrated, prefs, activeTrack, router]);

    return state;
}
