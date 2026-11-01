'use client';

/**
 * UsageBanner (Task 8) — sticky amber banner at top of /questions, /tests,
 * /ai-tutor for free users. Shows remaining AI chats today + a CTA to
 * /subscription. Dismissable per session via localStorage.
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

function readDismissed(): boolean {
  if (typeof window === 'undefined') return false;
  return Boolean(
    sessionStorage.getItem(SESSION_KEY) || localStorage.getItem(STORAGE_KEY),
  );
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
    sessionStorage.setItem(SESSION_KEY, '1');
    localStorage.setItem(STORAGE_KEY, '1');
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

  return (
    <div
      className={`w-full ${isDepleted ? 'bg-rose-500/15 border-rose-500/40 text-rose-100'
        : 'bg-amber-500/10 border-amber-500/30 text-amber-100'}
        border-b backdrop-blur-sm`}
      role="region"
      aria-label="Free usage status"
    >
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2 text-sm">
        <Sparkles size={16} aria-hidden="true" className="shrink-0" />
        <p className="flex-1">
          {isDepleted ? (
            <>
              You&rsquo;ve used all <strong>{cap}/{cap}</strong> AI chats today. Subscribe for unlimited AI Tutor →
            </>
          ) : (
            <>
              <strong>{usedToday}/{cap}</strong> AI chats used today · Unlock all features from just ₹129/month →
            </>
          )}
        </p>
        <Link
          href="/subscription"
          className="rounded-md bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold px-3 py-1 text-xs"
        >
          Subscribe
        </Link>
        <button
          type="button"
          aria-label="Dismiss banner"
          onClick={dismiss}
          className="ml-1 rounded-md p-1 text-current/70 hover:bg-white/10"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}