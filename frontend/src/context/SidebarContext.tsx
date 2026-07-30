/**
 * SidebarContext — shared desktop-sidebar visibility state.
 *
 * The sidebar used to own its open/closed state inside Sidebar.tsx
 * (useState + localStorage). That made it impossible for any other
 * component to influence the sidebar — e.g. auto-collapse the user
 * into fullscreen on /questions/* routes.
 *
 * This context exposes a small store with:
 *   - `desktopOpen`      — current visibility (persisted in localStorage)
 *   - `userOverride`     — true after the user manually toggles, so the
 *                          auto-collapse logic stops fighting them until
 *                          they leave the auto-collapse scope (session-scoped)
 *   - `setDesktopOpen(v)` — sets the visibility + flips userOverride=true
 *   - `collapseForRoute()` — auto-collapse without marking override
 *
 * Persistence: only `desktopOpen` survives a hard refresh via the
 * localStorage key `crackcms_sidebar_desktop_open` (same key the old
 * code used, so existing users keep their preference).
 */
'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

const STORAGE_KEY = 'crackcms_sidebar_desktop_open';

interface SidebarContextValue {
  desktopOpen: boolean;
  userOverride: boolean;
  setDesktopOpen: (open: boolean) => void;
  /** Called by route-level auto-hide controllers (e.g. SidebarAutoHide). */
  collapseForRoute: () => void;
  /** Called when leaving an auto-hide scope so the override can be cleared. */
  resetOverride: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: ReactNode }) {
  // Start with the SSR-safe default. We hydrate from localStorage in an effect.
  const [desktopOpen, setDesktopOpenState] = useState<boolean>(true);
  const [userOverride, setUserOverride] = useState<boolean>(false);
  const [hydrated, setHydrated] = useState<boolean>(false);

  // Hydrate from localStorage once on mount.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved !== null) setDesktopOpenState(saved === 'true');
    setHydrated(true);
  }, []);

  // Persist `desktopOpen` whenever it changes (post-hydration only).
  useEffect(() => {
    if (typeof window === 'undefined' || !hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, String(desktopOpen));
    // Side effects on body — kept identical to the original Sidebar.tsx
    // logic so the existing CSS hook (body.sidebar-hidden) continues to work.
    if (desktopOpen) {
      document.body.classList.remove('sidebar-hidden');
    } else {
      document.body.classList.add('sidebar-hidden');
    }
    return () => {
      // Don't remove the class on unmount — a sibling Sidebar instance may
      // still be the source of truth. The next render cycle of the new
      // owner will reconcile.
    };
  }, [desktopOpen, hydrated]);

  const setDesktopOpen = useCallback((open: boolean) => {
    setDesktopOpenState(open);
    setUserOverride(true);
  }, []);

  const collapseForRoute = useCallback(() => {
    // Only collapse if the user hasn't manually overridden this session.
    setDesktopOpenState((current) => {
      if (!userOverride) return false;
      return current;
    });
  }, [userOverride]);

  const resetOverride = useCallback(() => {
    setUserOverride(false);
  }, []);

  const value = useMemo<SidebarContextValue>(
    () => ({
      desktopOpen,
      userOverride,
      setDesktopOpen,
      collapseForRoute,
      resetOverride,
    }),
    [desktopOpen, userOverride, setDesktopOpen, collapseForRoute, resetOverride],
  );

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
}

export function useSidebar(): SidebarContextValue {
  const ctx = useContext(SidebarContext);
  if (!ctx) {
    throw new Error('useSidebar must be used within a <SidebarProvider>');
  }
  return ctx;
}