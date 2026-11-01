/**
 * usageBannerRoutes — where the free-usage banner (UsageBanner) shows.
 *
 * <Header> renders the banner directly under the header bar on these
 * sections, so it appears on the pages of them that render the Header: the
 * question banks (/questions, /questions/neet-pg/practice,
 * /questions/inicet/practice), /tests, /simulator and /ai-tutor. Focus pages
 * without a Header (/questions/practice, the /tests/<id> player) show none.
 * The banner itself renders nothing for premium, admin and logged-out users.
 *
 * Kept free of React and Next imports so tests/unit can load it directly.
 */

/** Sections (a path and its sub-paths) that show the banner. */
export const USAGE_BANNER_PATHS: readonly string[] = ['/questions', '/tests', '/simulator', '/ai-tutor'];

/** True when the free-usage banner belongs under the Header on this route. */
export function isUsageBannerRoute(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return USAGE_BANNER_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
