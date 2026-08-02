'use client';

/**
 * LockedBadge (Task 8) — small "Premium" pill with a lock icon. Used
 * inline next to feature names that the current user can't access yet.
 * Visibility rule: ALL premium features stay visible in nav/lists — only
 * the affordance to start them is gated.
 */
import { Lock } from 'lucide-react';

interface LockedBadgeProps {
  label?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export function LockedBadge({
  label = 'Premium',
  size = 'sm',
  className = '',
}: LockedBadgeProps) {
  const dims = size === 'md' ? 'text-xs px-2 py-0.5' : 'text-[10px] px-1.5 py-0.5';
  const iconSize = size === 'md' ? 12 : 10;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full
        bg-amber-500/15 border border-amber-500/40 text-amber-300
        font-medium uppercase tracking-wide whitespace-nowrap ${dims} ${className}`}
      title={`${label} feature — subscribe to unlock`}
      aria-label={`${label} feature — subscribe to unlock`}
    >
      <Lock size={iconSize} aria-hidden="true" />
      {label}
    </span>
  );
}