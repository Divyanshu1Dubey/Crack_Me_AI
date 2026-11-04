'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { useAuth } from '@/lib/auth';
import type { UiPreferences } from '@/lib/preferences';
import {
    activatePreferences,
    getPreferencesSnapshot,
    getServerPreferencesSnapshot,
    subscribePreferences,
} from './preferencesStore';

const DEFAULTS: UiPreferences = Object.freeze({}) as UiPreferences;

export interface UiPreferencesState {
    /** The learner's preferences; `{}` (the defaults) while signed out or not known yet. */
    prefs: UiPreferences;
    /** True once the server answered (or failed) for this user; always true when signed out. */
    loaded: boolean;
    /** `prefs` is this browser's copy and the server has not answered yet. */
    fromCache: boolean;
    saving: boolean;
    saveError: string | null;
    signedIn: boolean;
}

/**
 * The signed-in user's layout preferences (see preferencesStore.ts). The server render and
 * hydration use the defaults, so the custom layout appears right after the user is known.
 */
export function useUiPreferences(): UiPreferencesState {
    const { user, loading } = useAuth();
    const userKey = user ? String(user.id) : null;

    useEffect(() => {
        // While the session is still being checked, keep whatever is shown.
        if (!userKey && loading) return;
        activatePreferences(userKey);
    }, [userKey, loading]);

    const snap = useSyncExternalStore(subscribePreferences, getPreferencesSnapshot, getServerPreferencesSnapshot);
    const mine = userKey !== null && snap.userKey === userKey;
    return {
        prefs: mine ? snap.prefs : DEFAULTS,
        loaded: mine ? snap.loaded : userKey === null && !loading,
        fromCache: mine && snap.fromCache,
        saving: mine && snap.saving,
        saveError: mine ? snap.saveError : null,
        signedIn: userKey !== null,
    };
}
