/**
 * useGenerationHistory — localStorage-backed "recent runs" + "favorites"
 * for the AI Question Generator. Lives in a hook so any future page
 * (the admin dashboard, a /history route, etc.) can share the same data.
 *
 * Storage keys are namespaced under `crackcms:generate:` so a future
 * "clear site data" tool can drop them in one pass.
 *
 * Hydration uses `useSyncExternalStore` (the React 18+ canonical way
 * to subscribe to a non-React store) — avoids both the "empty state
 * flash on first render" and the `react-hooks/set-state-in-effect`
 * lint warning.
 */
'use client';

import { useCallback, useMemo, useSyncExternalStore } from 'react';
import type { Difficulty, GenerationHistoryEntry } from '@/components/QuestionComposer/types';

const KEY_RECENT = 'crackcms:generate:recent';
const KEY_FAVORITES = 'crackcms:generate:favorites';
const MAX_RECENT = 12;

/** In-process notifier so the same tab also re-renders on writes. */
const listeners = new Set<() => void>();
function notify(): void {
  for (const l of listeners) l();
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function readArray<T>(key: string): T[] {
  if (!isBrowser()) return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function writeArray<T>(key: string, value: T[]): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    notify();
  } catch {
    /* Quota exceeded or storage disabled — non-fatal. */
  }
}

let recentCache: GenerationHistoryEntry[] | null = null;
let favoritesCache: GenerationHistoryEntry[] | null = null;

function getRecent(): GenerationHistoryEntry[] {
  if (recentCache === null) recentCache = readArray<GenerationHistoryEntry>(KEY_RECENT);
  return recentCache;
}
function getFavorites(): GenerationHistoryEntry[] {
  if (favoritesCache === null) favoritesCache = readArray<GenerationHistoryEntry>(KEY_FAVORITES);
  return favoritesCache;
}

/**
 * Subscribe to both:
 *  - our own in-tab notifier (so `record` re-renders the page that
 *    triggered the write)
 *  - the browser's `storage` event (so a write in another tab re-renders
 *    this one)
 */
function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY_RECENT || e.key === KEY_FAVORITES) {
      // Invalidate caches so the next snapshot reflects the new value.
      if (e.key === KEY_RECENT) recentCache = null;
      if (e.key === KEY_FAVORITES) favoritesCache = null;
      cb();
    }
  };
  if (isBrowser()) window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(cb);
    if (isBrowser()) window.removeEventListener('storage', onStorage);
  };
}

function getServerRecent(): GenerationHistoryEntry[] { return []; }
function getServerFavorites(): GenerationHistoryEntry[] { return []; }

export interface UseGenerationHistory {
  recent: GenerationHistoryEntry[];
  favorites: GenerationHistoryEntry[];
  record: (entry: Omit<GenerationHistoryEntry, 'id' | 'createdAt'>) => GenerationHistoryEntry;
  toggleFavorite: (id: string) => void;
  removeFavorite: (id: string) => void;
  clearRecent: () => void;
}

function makeId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `g-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useGenerationHistory(): UseGenerationHistory {
  const recent = useSyncExternalStore(subscribe, getRecent, getServerRecent);
  const favorites = useSyncExternalStore(subscribe, getFavorites, getServerFavorites);

  const record = useCallback<UseGenerationHistory['record']>((entry) => {
    const next: GenerationHistoryEntry = {
      ...entry,
      id: makeId(),
      createdAt: Date.now(),
    };
    const merged = [next, ...getRecent().filter((p) => p.id !== next.id)].slice(0, MAX_RECENT);
    recentCache = merged;
    writeArray(KEY_RECENT, merged);
    return next;
  }, []);

  const toggleFavorite = useCallback<UseGenerationHistory['toggleFavorite']>((id) => {
    const list = getFavorites();
    const exists = list.find((p) => p.id === id);
    const base = getRecent();
    const next = exists
      ? list.filter((p) => p.id !== id)
      : [...list, base.find((r) => r.id === id)].filter(
          (x): x is GenerationHistoryEntry => Boolean(x),
        );
    favoritesCache = next;
    writeArray(KEY_FAVORITES, next);
  }, []);

  const removeFavorite = useCallback<UseGenerationHistory['removeFavorite']>((id) => {
    const next = getFavorites().filter((p) => p.id !== id);
    favoritesCache = next;
    writeArray(KEY_FAVORITES, next);
  }, []);

  const clearRecent = useCallback(() => {
    recentCache = [];
    writeArray(KEY_RECENT, []);
  }, []);

  return useMemo(
    () => ({ recent, favorites, record, toggleFavorite, removeFavorite, clearRecent }),
    [recent, favorites, record, toggleFavorite, removeFavorite, clearRecent],
  );
}

// Re-export the type so consumers don't have to dig into QuestionComposer/types.
export type { Difficulty, GenerationHistoryEntry };