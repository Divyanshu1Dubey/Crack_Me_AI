'use client';

/**
 * PaywallRoot — single client-side mount point for the upgrade modal
 * (UpgradeModal).
 *
 * The <PaywallProvider> itself is wired at the layout root
 * (app/layout.tsx) so that any client component anywhere in the tree —
 * notably <Sidebar> on /admin routes — can call usePaywall() safely.
 * Without lifting the provider, the SSR prerender of /admin/analytics-dashboard
 * crashes with "usePaywall must be used within <PaywallProvider>" because
 * Sidebar renders before PaywallRoot gets a chance to mount.
 *
 * This file just renders the modal. The free-usage banner (UsageBanner) is
 * rendered by <Header>, directly under the header bar, on the routes in
 * lib/paywall/usageBannerRoutes.ts; mounted here it sat after the footer.
 */
import { UpgradeModal } from './UpgradeModal';

export function PaywallRoot() {
  return <UpgradeModal />;
}
