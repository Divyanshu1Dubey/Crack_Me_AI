/**
 * sessionRefreshGate.ts -- bounded "refresh the session after a 401".
 *
 * Used by api.ts for Supabase access tokens. When the backend rejects a
 * session that is actually valid (Supabase /auth/v1/user unreachable from the
 * backend, a wrong anon key, ...), refreshing cannot help, and an unbounded
 * refresh-per-401 looped: refreshSession() emits TOKEN_REFRESHED, the auth
 * listener re-fetched the profile, that 401'd again, and so on until Supabase
 * rate-limited token refreshes for the whole IP.
 *
 * The gate allows:
 *   - one refresh at a time (concurrent 401s share it),
 *   - at most one refresh per `cooldownMs` (a request that failed with an
 *     older token during the cooldown is retried with the latest token),
 *   - no refresh for a token that a refresh produced within
 *     `refreshedTokenGraceMs` (the backend rejecting it is not an expiry).
 *
 * Kept free of imports so it can be unit-tested directly with Node
 * (tests/unit/session-refresh-gate.test.ts).
 */

export interface RefreshGateOptions {
  cooldownMs?: number;
  refreshedTokenGraceMs?: number;
  now?: () => number;
}

/** Returns `tokenAfter401(failedToken)`: a token to retry with, or null. */
export function createRefreshGate(
  refresh: () => Promise<string | null>,
  { cooldownMs = 30_000, refreshedTokenGraceMs = 10 * 60_000, now = Date.now }: RefreshGateOptions = {},
): (failedToken: string | null) => Promise<string | null> {
  let inFlight: Promise<string | null> | null = null;
  let lastRefreshAt = Number.NEGATIVE_INFINITY;
  let lastRefreshedToken: string | null = null;

  return (failedToken) => {
    if (inFlight) return inFlight;
    const sinceLastRefresh = now() - lastRefreshAt;
    if (failedToken && failedToken === lastRefreshedToken && sinceLastRefresh < refreshedTokenGraceMs) {
      return Promise.resolve(null);
    }
    if (sinceLastRefresh < cooldownMs) {
      return Promise.resolve(
        lastRefreshedToken && lastRefreshedToken !== failedToken ? lastRefreshedToken : null,
      );
    }
    lastRefreshAt = now();
    lastRefreshedToken = null; // set again only if this refresh succeeds
    const attempt = (async () => {
      try {
        const token = await refresh();
        lastRefreshedToken = token || null;
        return lastRefreshedToken;
      } catch {
        return null;
      }
    })();
    inFlight = attempt;
    // Cleared asynchronously, after the assignment above, even if `refresh`
    // settles synchronously.
    void attempt.finally(() => {
      if (inFlight === attempt) inFlight = null;
    });
    return attempt;
  };
}
