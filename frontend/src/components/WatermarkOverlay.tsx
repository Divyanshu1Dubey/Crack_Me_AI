'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';

/**
 * WatermarkOverlay
 * ----------------
 * Screen-recording deterrent for PYQ content. Renders the user's email
 * and current timestamp tiled across the viewport, rotated -12°, scaled
 * 150%, at near-invisible opacity.
 *
 * Why `mix-blend-mode: difference`:
 *   A flat opacity (e.g. 0.015) reads as "barely there" on a light
 *   background but becomes clearly legible on dark backgrounds because
 *   the foreground/text colors are constant. Switching to
 *   `mix-blend-mode: difference` makes the watermark invert against
 *   whatever sits beneath it — so on white it's faint dark, on dark
 *   it's faint light, on a colored card it's faint complementary. The
 *   perceived contrast stays low across every theme without per-theme
 *   tuning.
 *
 * Opacity is also dropped to 0.05 (from 0.015) for additional
 * deterrence on light backgrounds; difference-blend keeps it subtle.
 *
 * Tested in `frontend/tests/e2e/neet-pg-qa.spec.ts` (Bug #R1) — the
 * overlay's computed opacity must remain <= 0.10 to satisfy that test.
 */
export function WatermarkOverlay() {
  const { user } = useAuth();
  const [timestamp, setTimestamp] = useState('');
  // mounted gate — SSR returns null for the overlay because useAuth has no
  // session on the server. Without this gate, the client's first paint
  // renders 50 timestamped spans while the server rendered nothing,
  // triggering React #418 (text content mismatch).
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Update timestamp every minute
    const updateTime = () => setTimestamp(new Date().toLocaleString());
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!mounted || !user) return null;

  const watermarkText = `${user.email || user.username} • ${timestamp}`;

  return (
    <div
      aria-hidden="true"
      style={{ mixBlendMode: 'difference' }}
      className="pointer-events-none fixed inset-0 z-9999 flex flex-wrap items-center justify-center gap-24 overflow-hidden select-none opacity-[0.05] scale-150 -rotate-12"
    >
      {[...Array(30)].map((_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className="text-xl font-medium whitespace-nowrap text-white"
        >
          {watermarkText}
        </span>
      ))}
    </div>
  );
}
