/**
 * tokenRefresh.ts -- one refresh at a time for the token modes
 * (NEXT_PUBLIC_AUTH_MODE=local / django; lib/localAuth.ts wires it up).
 *
 * The Django-native backend rotates refresh tokens and treats a rotated token
 * presented again as theft: it revokes the whole session ("session_revoked"),
 * except for the token rotated in the last NATIVE_AUTH_REFRESH_REUSE_SECONDS
 * (20 s), which gets tokens equivalent to the current ones
 * (accounts/native_sessions.py rotate()). Every tab shares the tokens in
 * localStorage, so the client must never POST the same refresh token twice
 * when it can avoid it:
 *
 *   - concurrent requests in one tab share one refresh (one promise);
 *   - tabs take turns with an exclusive Web Lock and re-read the stored tokens
 *     once they hold it: when another tab has stored a newer access token in
 *     the meantime, that one is used and nothing is POSTed;
 *   - tokens replaced or cleared while the refresh ran (a sign-in or sign-out
 *     in another tab) are never overwritten with the older session's answer;
 *   - only a definitive answer (400 / 401 / 403: expired, revoked, blocked,
 *     unconfirmed, logged-out device) clears the stored session. A network
 *     error, 429 or 5xx keeps it, so a backend blip does not sign anyone out
 *     (local mode keeps its old rule: any failure clears the tokens).
 *
 * No imports: unit-tested directly (tests/unit/token-refresh.test.ts).
 */

export interface StoredTokens {
  access: string | null;
  refresh: string | null;
}

export interface RefreshResponse {
  status: number;
  data: Record<string, unknown> | null;
}

export type RefreshOutcome =
  | { ok: true; access: string; refreshed: boolean }
  | { ok: false; definitive: boolean; status: number; code?: string };

export interface TokenRefresherOptions {
  readTokens: () => StoredTokens;
  /** Store a new access token, and the rotated refresh token when the server sent one. */
  writeTokens: (access: string, refresh: string | null) => void;
  clearTokens: () => void;
  /** POST the refresh token. Resolves with the HTTP answer; rejects on a network error. */
  postRefresh: (refresh: string) => Promise<RefreshResponse>;
  /** Run `task` while holding a lock shared by every tab (browserRefreshLock()). */
  withLock?: <T>(task: () => Promise<T>) => Promise<T>;
  /** Clear the stored session on ANY failed refresh (the dev-only local mode's old behaviour). */
  clearOnTransientFailure?: boolean;
}

/** Answers after which the refresh token can never work again. */
const DEFINITIVE_STATUSES = new Set([400, 401, 403]);

const runWithoutLock = <T,>(task: () => Promise<T>): Promise<T> => task();

/**
 * Returns `refresh(failedAccess)`: a usable access token for a request that
 * got a 401 with `failedAccess`, or why there is none.
 */
export function createTokenRefresher(options: TokenRefresherOptions) {
  const withLock = options.withLock ?? runWithoutLock;
  let inFlight: Promise<RefreshOutcome> | null = null;

  const run = async (failedAccess: string | null): Promise<RefreshOutcome> => {
    const { access, refresh } = options.readTokens();
    // Another tab (or an earlier refresh here) stored a newer access token
    // while this request was in flight: retry with it, POST nothing.
    if (access && failedAccess && access !== failedAccess) {
      return { ok: true, access, refreshed: false };
    }
    if (!refresh) {
      return { ok: false, definitive: true, status: 0, code: 'no_refresh_token' };
    }

    let response: RefreshResponse | null = null;
    try {
      response = await options.postRefresh(refresh);
    } catch {
      response = null; // network error / timeout
    }

    const now = options.readTokens();
    if (now.refresh !== refresh) {
      // Signed in again or signed out (another tab) while this ran: what is
      // stored now wins; never write the older session's tokens over it.
      return now.access
        ? { ok: true, access: now.access, refreshed: false }
        : { ok: false, definitive: true, status: response?.status ?? 0, code: 'signed_out' };
    }

    const status = response?.status ?? 0;
    const data = response?.data ?? null;
    const newAccess = status >= 200 && status < 300 && data && typeof data.access === 'string' ? data.access : '';
    if (newAccess) {
      // No `refresh` in the answer (older backends inside the reuse window):
      // another tab rotated a moment ago and stored the new one.
      const newRefresh = data && typeof data.refresh === 'string' && data.refresh ? data.refresh : null;
      options.writeTokens(newAccess, newRefresh);
      return { ok: true, access: newAccess, refreshed: true };
    }

    const code = data && typeof data.code === 'string' ? data.code : undefined;
    const definitive = DEFINITIVE_STATUSES.has(status);
    if (definitive || options.clearOnTransientFailure) options.clearTokens();
    return { ok: false, definitive, status, code };
  };

  return (failedAccess: string | null = null): Promise<RefreshOutcome> => {
    if (inFlight) return inFlight;
    const attempt = withLock(() => run(failedAccess)).catch(
      (): RefreshOutcome => ({ ok: false, definitive: false, status: 0 }),
    );
    inFlight = attempt;
    // Cleared asynchronously, after the assignment above, even when the
    // refresh settles synchronously.
    void attempt.finally(() => {
      if (inFlight === attempt) inFlight = null;
    });
    return attempt;
  };
}

type LockRequest = (
  name: string,
  options: { signal?: AbortSignal },
  callback: () => Promise<unknown>,
) => Promise<unknown>;

/**
 * A cross-tab exclusive lock (Web Locks API) for createTokenRefresher. Where
 * the API is missing (old browsers) or the lock is not granted within
 * `waitMs` (a stuck tab), the task runs anyway: the server's 20-second reuse
 * window covers that rare overlap.
 */
export function browserRefreshLock(
  name = 'crack_auth_refresh',
  waitMs = 10_000,
  locks: { request?: LockRequest } | undefined = typeof navigator === 'undefined'
    ? undefined
    : (navigator as unknown as { locks?: { request?: LockRequest } }).locks,
) {
  return async <T,>(task: () => Promise<T>): Promise<T> => {
    if (!locks || typeof locks.request !== 'function') return task();
    const controller = typeof AbortController === 'undefined' ? null : new AbortController();
    const timer = controller ? setTimeout(() => controller.abort(), waitMs) : null;
    let started = false;
    try {
      return (await locks.request(name, controller ? { signal: controller.signal } : {}, async () => {
        started = true;
        if (timer) clearTimeout(timer);
        return task();
      })) as T;
    } catch (error) {
      if (!started) return task(); // not granted in time / refused: refresh without it
      throw error;
    } finally {
      if (timer) clearTimeout(timer);
    }
  };
}
