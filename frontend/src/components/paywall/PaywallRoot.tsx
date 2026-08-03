'use client';

/**
 * PaywallRoot — single client-side mount point for the freemium UI
 * (UpgradeModal + UsageBanner).
 *
 * The <PaywallProvider> itself is wired at the layout root
 * (app/layout.tsx) so that any client component anywhere in the tree —
 * notably <Sidebar> on /admin routes — can call usePaywall() safely.
 * Without lifting the provider, the SSR prerender of /admin/analytics-dashboard
 * crashes with "usePaywall must be used within <PaywallProvider>" because
 * Sidebar renders before PaywallRoot gets a chance to mount.
 *
 * This file just renders the modal and (optionally) the per-route banner.
 */
import { usePathname } from 'next/navigation';

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
    <>
      {showBanner ? <UsageBanner /> : null}
      <UpgradeModal />
    </>
  );
}