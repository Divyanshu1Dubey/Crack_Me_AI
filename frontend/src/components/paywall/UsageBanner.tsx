'use client';

/**
 * UsageBanner (Task 8) — amber card for free users, directly under the
 * header bar: <Header> renders it on /questions, /tests, /simulator and
 * /ai-tutor (lib/paywall/usageBannerRoutes.ts). Shows the AI chats used
 * today + a CTA to /subscription. Dismissable via localStorage (and
 * sessionStorage).
 */
import Link from 'next/link';
import { useCallback, useState } from 'react';
import { Sparkles, X } from 'lucide-react';

import { useAuth } from '@/lib/auth';

interface UsageBannerProps {
  /** Override for the daily AI tutor cap. Defaults to the profile's
   *  `ai_tutor_daily_cap` (backend TokenConfig.ai_tutor_daily_cap). */
  cap?: number;
  /** Override for today's usage. Defaults to the profile's `ai_tutor_used_today`. */
  usedToday?: number;
}

const STORAGE_KEY = 'crackcms:paywall:banner:dismissed';
const SESSION_KEY = 'crackcms:paywall:banner:dismissed:session';

// Storage can be missing or throw (private mode, blocked site data): the
// banner then simply shows, and dismissing it still hides it for this view.
function readDismissed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return Boolean(
      window.sessionStorage.getItem(SESSION_KEY) || window.localStorage.getItem(STORAGE_KEY),
    );
  } catch {
    return false;
  }
}

function writeDismissed(): void {
  try {
    window.sessionStorage.setItem(SESSION_KEY, '1');
    window.localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    /* storage unavailable: dismissed for this render tree only */
  }
}

export function UsageBanner({ cap: capOverride, usedToday: usedOverride }: UsageBannerProps) {
  const { user } = useAuth();
  // Storage is read on each render — the dismiss() callback bumps
  // `nonce` so React re-renders and we re-read storage. Avoids the
  // `react-hooks/set-state-in-effect` lint rule (which fires on
  // useEffect+setState in React 19).
  const [nonce, setNonce] = useState(0);
  const dismissed = nonce > 0 || readDismissed();

  const dismiss = useCallback(() => {
    if (typeof window === 'undefined') return;
    writeDismissed();
    setNonce(1);
  }, []);

  // Only render for free (non-premium, non-admin) users. The profile sends
  // `ai_tutor_daily_cap: null` for anyone without a cap.
  const isFree =
    user &&
    !user.is_admin &&
    !user.is_premium &&
    !user.subscription_info?.is_active &&
    user.ai_tutor_daily_cap !== null;

  if (!isFree || dismissed) return null;

  const cap = capOverride ?? (typeof user.ai_tutor_daily_cap === 'number' ? user.ai_tutor_daily_cap : 2);
  const usedToday = Math.min(
    cap,
    usedOverride ?? (typeof user.ai_tutor_used_today === 'number' ? user.ai_tutor_used_today : 0),
  );
  const remaining = Math.max(0, cap - usedToday);
  const isDepleted = remaining === 0;

  // Dark text on the light tint, light text on the dark tint: the banner
  // used rose-100 / amber-100 text in both themes (unreadable in light mode).
  // A rounded card the width of the header card above it (both sit in
  // .main-content). Phones (<640px) drop the icon and the second clause,
  // which wrapped the card over several lines; the Subscribe button stays.
  return (
    <div
      className={`mb-4 w-full rounded-xl border ${isDepleted
        ? 'bg-rose-500/15 border-rose-500/40 text-rose-900 dark:text-rose-100'
        : 'bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-100'}
        backdrop-blur-sm`}
      role="region"
      aria-label="Free usage status"
    >
      <div className="flex items-center gap-2 px-3 py-2 text-sm sm:gap-3 sm:px-4">
        <Sparkles size={16} aria-hidden="true" className="hidden shrink-0 sm:block" />
        <p className="min-w-0 flex-1">
          {isDepleted ? (
            <>
              You&rsquo;ve used all <strong>{cap}/{cap}</strong> AI chats today.
              <span className="hidden sm:inline"> Subscribe to remove the daily limit →</span>
            </>
          ) : (
            <>
              <strong>{usedToday}/{cap}</strong> AI chats used today
              <span className="hidden sm:inline"> · Unlock all features from just ₹129/month →</span>
            </>
          )}
        </p>
        <Link
          href="/subscription"
          className="shrink-0 rounded-md bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold px-3 py-1 text-xs"
        >
          Subscribe
        </Link>
        <button
          type="button"
          aria-label="Dismiss banner"
          onClick={dismiss}
          className="ml-1 shrink-0 rounded-md p-1.5 opacity-70 transition hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/10 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
