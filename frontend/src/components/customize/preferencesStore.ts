/**
 * The signed-in learner's layout preferences, shared by the sidebar, the dashboard and Settings.
 *
 * The server is the source of truth (GET / PATCH /api/auth/preferences/). This browser keeps a copy
 * of the server's answer per user in localStorage, so the custom layout shows at once on the next
 * page load; the server's answer then replaces it. Changes apply at once and are saved after a short
 * pause (one PATCH per burst of clicks, one request at a time). A save the server refuses or that
 * fails puts the layout back to the last saved one and sets `saveError`. Signed-out visitors get the
 * defaults; nothing is read, cached or sent for them.
 *
 * A module-level store (no provider): every component reads it through useUiPreferences
 * (usePreferences.ts); one GET per page load and user.
 */
import api from '@/lib/api';
import {
    RESET_PATCH,
    applyPreferencesPatch,
    sanitizePreferences,
    type UiPreferences,
    type UiPreferencesPatch,
} from '@/lib/preferences';

export const PREFERENCES_ENDPOINT = '/auth/preferences/';
const CACHE_PREFIX = 'crackcms_ui_prefs:';
const SAVE_DELAY_MS = 600;

export interface PreferencesSnapshot {
    /** Whose preferences these are (the user id); null when signed out. */
    userKey: string | null;
    prefs: UiPreferences;
    /** The server answered for this user, or could not be reached (then `prefs` is the best known). */
    loaded: boolean;
    /** `prefs` came from this browser's copy and the server has not answered yet. */
    fromCache: boolean;
    saving: boolean;
    /** Why the last save did not go through (the layout went back to the saved one), else null. */
    saveError: string | null;
}

const EMPTY: UiPreferences = Object.freeze({}) as UiPreferences;
const SIGNED_OUT: PreferencesSnapshot = Object.freeze({
    userKey: null,
    prefs: EMPTY,
    loaded: true,
    fromCache: false,
    saving: false,
    saveError: null,
});

let snapshot: PreferencesSnapshot = SIGNED_OUT;
/** What the server has (its last answer; before that, this browser's copy or the defaults). */
let confirmed: UiPreferences = EMPTY;
/** Changes not sent yet (top-level keys, the later change of a key wins). */
let pending: UiPreferencesPatch | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
/** Bumped on every change of user: answers that belong to an earlier user are ignored. */
let generation = 0;
/** The generation whose PATCH is in flight, or null. */
let savingGeneration: number | null = null;
const listeners = new Set<() => void>();

function setSnapshot(next: Partial<PreferencesSnapshot>): void {
    snapshot = { ...snapshot, ...next };
    listeners.forEach((listener) => listener());
}

function cacheKey(userKey: string): string {
    return `${CACHE_PREFIX}${userKey}`;
}

function readCache(userKey: string): UiPreferences | null {
    try {
        const raw = window.localStorage.getItem(cacheKey(userKey));
        if (!raw) return null;
        return sanitizePreferences((JSON.parse(raw) as { prefs?: unknown } | null)?.prefs);
    } catch {
        return null;
    }
}

function writeCache(userKey: string | null, prefs: UiPreferences): void {
    if (!userKey) return;
    try {
        window.localStorage.setItem(cacheKey(userKey), JSON.stringify({ v: 1, prefs }));
    } catch {
        // Private mode / quota: the server still has the preferences.
    }
}

function clearTimer(): void {
    if (timer !== null) {
        clearTimeout(timer);
        timer = null;
    }
}

function describeSaveError(error: unknown): string {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 429) return 'Too many changes in a row. Wait a minute, then try again.';
    if (status === 400 || status === 413) return 'This layout could not be saved. Reload the page and try again.';
    if (status === 401 || status === 403) return 'Sign in again to save your layout.';
    return "Couldn't save your layout. Check your connection and try again.";
}

async function load(userKey: string, gen: number): Promise<void> {
    try {
        const response = await api.get(PREFERENCES_ENDPOINT);
        if (gen !== generation) return;
        const server = sanitizePreferences((response.data as { preferences?: unknown } | undefined)?.preferences);
        confirmed = server;
        // Changes made while the request was out are being saved; their answer settles the layout.
        const busy = pending !== null || savingGeneration === gen;
        if (!busy) writeCache(userKey, server);
        setSnapshot({ prefs: busy ? snapshot.prefs : server, loaded: true, fromCache: false });
    } catch {
        if (gen !== generation) return;
        setSnapshot({ loaded: true });
    }
}

function schedule(delay: number): void {
    clearTimer();
    timer = setTimeout(() => {
        timer = null;
        void flush();
    }, delay);
}

async function flush(): Promise<void> {
    const gen = generation;
    const userKey = snapshot.userKey;
    if (!pending || !userKey || savingGeneration === gen) return; // the save in flight sends the rest after it
    const body = pending;
    pending = null;
    savingGeneration = gen;
    setSnapshot({ saving: true });
    try {
        const response = await api.patch(PREFERENCES_ENDPOINT, body);
        if (gen !== generation) return;
        confirmed = sanitizePreferences((response.data as { preferences?: unknown } | undefined)?.preferences);
        if (pending) {
            setSnapshot({ saving: false });
        } else {
            writeCache(userKey, confirmed);
            setSnapshot({ prefs: confirmed, saving: false, saveError: null, loaded: true, fromCache: false });
        }
    } catch (error) {
        if (gen !== generation) return;
        // Back to what the server has; changes made meanwhile built on the refused one.
        pending = null;
        clearTimer();
        writeCache(userKey, confirmed);
        setSnapshot({ prefs: confirmed, saving: false, saveError: describeSaveError(error) });
    } finally {
        if (savingGeneration === gen) savingGeneration = null;
        if (gen === generation && pending) schedule(0);
    }
}

/** Switch the store to `userKey` (null = signed out): this browser's copy now, the server's answer next. */
export function activatePreferences(userKey: string | null): void {
    if (userKey === snapshot.userKey) return;
    generation += 1;
    clearTimer();
    pending = null;
    if (!userKey) {
        confirmed = EMPTY;
        snapshot = SIGNED_OUT;
        listeners.forEach((listener) => listener());
        return;
    }
    const cached = readCache(userKey);
    confirmed = cached ?? EMPTY;
    setSnapshot({
        userKey,
        prefs: cached ?? EMPTY,
        loaded: false,
        fromCache: cached !== null,
        saving: false,
        saveError: null,
    });
    void load(userKey, generation);
}

/** Ask the server again (Settings does on open), unless changes are waiting to be saved. */
export function refreshPreferences(): void {
    const userKey = snapshot.userKey;
    if (!userKey || pending !== null || savingGeneration === generation) return;
    void load(userKey, generation);
}

/** Apply `patch` now and save it after a short pause (`immediate`: save now). No-op when signed out. */
export function updatePreferences(patch: UiPreferencesPatch, options: { immediate?: boolean } = {}): void {
    const userKey = snapshot.userKey;
    if (!userKey) return;
    const prefs = applyPreferencesPatch(snapshot.prefs, patch);
    pending = { ...(pending ?? {}), ...patch };
    // The copy in this browser is written once the server confirms (other tabs follow it).
    setSnapshot({ prefs, saveError: null });
    schedule(options.immediate ? 0 : SAVE_DELAY_MS);
}

/** Back to the default layout and opening page. */
export function resetPreferences(): void {
    updatePreferences(RESET_PATCH, { immediate: true });
}

// Another tab saved (its copy changed): follow it, unless this tab has changes of its own in flight.
function onStorage(event: StorageEvent): void {
    const userKey = snapshot.userKey;
    if (!userKey || event.key !== cacheKey(userKey) || pending !== null || savingGeneration !== null) return;
    const next = readCache(userKey);
    if (next) {
        confirmed = next;
        setSnapshot({ prefs: next });
    }
}

// Leaving the page: send what is waiting instead of dropping it.
function onVisibilityChange(): void {
    if (document.visibilityState === 'hidden' && pending !== null) {
        clearTimer();
        void flush();
    }
}

function watchPage(on: boolean): void {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;
    if (on) {
        window.addEventListener?.('storage', onStorage);
        document.addEventListener?.('visibilitychange', onVisibilityChange);
    } else {
        window.removeEventListener?.('storage', onStorage);
        document.removeEventListener?.('visibilitychange', onVisibilityChange);
    }
}

export function subscribePreferences(listener: () => void): () => void {
    listeners.add(listener);
    if (listeners.size === 1) watchPage(true);
    return () => {
        listeners.delete(listener);
        if (listeners.size === 0) watchPage(false);
    };
}

export function getPreferencesSnapshot(): PreferencesSnapshot {
    return snapshot;
}

/** Server render and hydration: the defaults (the server never knows the user's layout). */
export function getServerPreferencesSnapshot(): PreferencesSnapshot {
    return SIGNED_OUT;
}
