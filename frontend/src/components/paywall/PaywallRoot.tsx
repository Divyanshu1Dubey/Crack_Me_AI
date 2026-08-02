'use client';

/**
 * PaywallRoot — single client-side mount point for everything
 * freemium-related.
 *
 * Lives inside <body> in app/layout.tsx so:
 *  - <PaywallProvider> wires the React Context so any usePaywall() hook
 *    anywhere in the tree can call .show() / .dismiss().
 *  - <UpgradeModal> renders the global Radix Dialog whenever the api.ts
 *    interceptor fires (or any component calls usePaywall().show()).
 *  - <UsageBanner> shows the sticky "X/2 AI chats used today" prompt on
 *    /questions, /tests, /ai-tutor, /simulator for free users.
 *
 * Single client island keeps server components server-rendered.
 */
import { usePathname } from 'next/navigation';

import { PaywallProvider } from '@/lib/paywall/paywallContext';
import { UpgradeModal } from './UpgradeModal';
import { UsageBanner } from './UsageBanner';

const PAYWALL_BANNER_PATHS = [
  '/questions',
  '/tests',
  '/simulator',
  '/ai-tutor',
];

export function PaywallRoot() {
  const pathname = usePathname() || '';
  const showBanner = PAYWALL_BANNER_PATHS.some((p) => pathname.startsWith(p));

  return (
    <PaywallProvider>
      {showBanner ? <UsageBanner /> : null}
      <UpgradeModal />
    </PaywallProvider>
  );
}