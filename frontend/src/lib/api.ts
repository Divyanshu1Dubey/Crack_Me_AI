/**
 * api.ts — Centralized Axios API client for CrackCMS.
 * Contains all API endpoint functions grouped by module:
 *   - questionsAPI: Question bank CRUD, bookmarks, subjects, topics
 *   - aiAPI: AI explanations, tutor chat, question generation
 *   - testsAPI: Test creation, submission, results
 *   - analyticsAPI: Dashboard stats, study streaks, daily activity
 *   - resourcesAPI: Study resources listing
 *   - textbooksAPI: Textbook index and chapters
 *   - authAPI: Token balance, purchase, transaction history
 * Base URL: NEXT_PUBLIC_API_URL or http://127.0.0.1:8000/api
 * Auth: Supabase access tokens are attached automatically when Supabase is configured.
 */
import axios from 'axios';
import {
  clearSupabaseLocalSession,
  getSupabaseBrowserClient,
  isInvalidRefreshTokenError,
  isSupabaseAuthEnabled,
} from './supabase';
import { clearLocalTokens, getLocalAccessToken, isLocalAuthMode, refreshLocalAccessToken } from './localAuth';
import { createRefreshGate } from './sessionRefreshGate';

import {
  USE_API_PROXY,
  API_BASE_URL,
  resolveFallbackApiBaseUrl,
} from './apiBase';
// Never a remote (production) API for a local run -- see resolveFallbackApiBaseUrl.
const FALLBACK_API_BASE_URL = resolveFallbackApiBaseUrl();

// Last Supabase session seen by the request interceptor.
let cachedSession: { access_token: string } | null = null;

// Device id sent as X-Session-ID; the backend counts devices by it.
const DEVICE_ID_KEY = 'crack_device_id';
const DEVICE_ID_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

const newDeviceId = () => 'dev_' + Math.random().toString(36).slice(2) + '_' + Date.now();

const readDeviceIdCookie = (): string | null => {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|; )${DEVICE_ID_KEY}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
};

const writeDeviceIdCookie = (id: string | null) => {
  try {
    document.cookie = id
      ? `${DEVICE_ID_KEY}=${encodeURIComponent(id)}; Path=/; SameSite=Lax; Max-Age=${DEVICE_ID_COOKIE_MAX_AGE}`
      : `${DEVICE_ID_KEY}=; Path=/; SameSite=Lax; Max-Age=0`;
  } catch {
    // Cookies blocked as well.
  }
};

// Storage access can throw (site data blocked, some privacy modes / webviews).
// Then keep the id in a first-party cookie. If that cannot be persisted
// either, send no X-Session-ID at all (the backend skips device tracking):
// a new id per page load used to enrol a new device on every visit and use
// up the 2-device allowance within two page loads.
const getOrCreateSessionId = (): string => {
  if (typeof window === 'undefined') return '';
  try {
    let id = window.localStorage.getItem(DEVICE_ID_KEY);
    if (!id) {
      id = newDeviceId();
      window.localStorage.setItem(DEVICE_ID_KEY, id);
    }
    return id;
  } catch {
    let id = readDeviceIdCookie();
    if (!id) {
      writeDeviceIdCookie(newDeviceId());
      id = readDeviceIdCookie();
    }
    return id || '';
  }
};

/** Forget this browser's device id, so the next sign-in enrols a new device. */
const resetDeviceId = () => {
  if (typeof window === 'undefined') return;
  writeDeviceIdCookie(null);
  try {
    window.localStorage.removeItem(DEVICE_ID_KEY);
  } catch {
    // Storage unavailable: the cookie was cleared above.
  }
};

/**
 * Backend error codes that end this browser's session
 * (accounts/supabase_rest_auth.py; local dev auth also answers a blocked
 * account with `account_blocked`, `user_inactive` is SimpleJWT's own code,
 * kept for older backends). `session_invalid` is the legacy single-session
 * code, kept for older backends.
 */
const SESSION_ENDING_MESSAGES: Record<string, string> = {
  account_blocked: 'Your account has been blocked. Contact support if you think this is a mistake.',
  user_inactive: 'Your account has been blocked. Contact support if you think this is a mistake.',
  device_inactive: 'This device was signed out. Please sign in again.',
  email_not_confirmed: 'Please confirm your email address, then sign in again.',
  email_required: 'Sign in with an email address to use CrackLabs.',
  account_link_required:
    'This account must be verified by an administrator before it can sign in. Please contact support.',
  session_invalid: "You're logged in on another device",
};

/** `code` field of a backend error response, if any. */
export const getApiErrorCode = (error: unknown): string | undefined => {
  const data = (error as { response?: { data?: unknown } } | null)?.response?.data;
  const code = data && typeof data === 'object' ? (data as { code?: unknown }).code : undefined;
  return typeof code === 'string' ? code : undefined;
};

/** User-facing message when `error` means the session is over (blocked account, logged-out device, ...). */
export const getSessionEndingMessage = (error: unknown): string | null => {
  const code = getApiErrorCode(error);
  return code && Object.prototype.hasOwnProperty.call(SESSION_ENDING_MESSAGES, code)
    ? SESSION_ENDING_MESSAGES[code]
    : null;
};

let sessionEndRedirecting = false;

/**
 * Sign this browser out locally after the backend ended the session, then
 * show the reason on /login. Returns true while the page is navigating away.
 * On /login itself it does not navigate, so the login form can show the error.
 */
export const endSessionAfterApiError = async (error: unknown): Promise<boolean> => {
  const message = getSessionEndingMessage(error);
  if (!message || typeof window === 'undefined') return false;
  if (sessionEndRedirecting) return true;
  if (getApiErrorCode(error) === 'device_inactive') resetDeviceId();
  cachedSession = null;
  if (isLocalAuthMode()) {
    clearLocalTokens();
  } else {
    await clearSupabaseLocalSession();
  }
  if (window.location.pathname.startsWith('/login')) return false;
  sessionEndRedirecting = true;
  window.location.href = '/login?authError=' + encodeURIComponent(message);
  return true;
};

// Only these are replayed against the fallback base URL: a 502/503/504 can
// arrive after the backend already processed a POST/PATCH (order creation,
// test submission, AI generation), and replaying it would run it twice.
const IDEMPOTENT_METHODS = new Set(['get', 'head', 'options']);

// ── Supabase session refresh after a 401 ─────────────────────────────────
// Bounded on purpose (see sessionRefreshGate.ts): when the backend rejects a
// session that is actually valid, an unbounded refresh-per-401 looped with
// the auth listener until Supabase rate-limited token refreshes for the IP.

/** Bearer token a request was sent with (AxiosHeaders or a plain object). */
const bearerTokenOf = (headers: unknown): string | null => {
  if (!headers || typeof headers !== 'object') return null;
  const h = headers as { get?: (name: string) => unknown } & Record<string, unknown>;
  const raw = typeof h.get === 'function' ? h.get('Authorization') : (h.Authorization ?? h.authorization);
  const value = typeof raw === 'string' ? raw : '';
  return value.toLowerCase().startsWith('bearer ') ? value.slice(7).trim() || null : null;
};

const refreshSupabaseAccessToken = async (): Promise<string | null> => {
  const supabase = getSupabaseBrowserClient();
  if (!supabase) return null;
  try {
    const { data, error } = await supabase.auth.refreshSession();
    if (error) {
      if (isInvalidRefreshTokenError(error)) {
        await clearSupabaseLocalSession();
        cachedSession = null;
      }
      return null;
    }
    if (data.session?.access_token) cachedSession = data.session;
    return data.session?.access_token || null;
  } catch (refreshError) {
    if (isInvalidRefreshTokenError(refreshError)) {
      await clearSupabaseLocalSession();
      cachedSession = null;
    }
    return null;
  }
};

/** A fresh access token to retry with after `failedToken` got a 401, or null. */
const supabaseTokenAfter401 = createRefreshGate(refreshSupabaseAccessToken);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token and session tracking to requests
api.interceptors.request.use(async (config) => {
  const sessionId = getOrCreateSessionId();
  if (sessionId) {
    config.headers['X-Session-ID'] = sessionId;
  }

  if (config.headers.Authorization) {
    // The caller passed a token explicitly (e.g. AuthProvider's profile
    // fetch right after sign-in): keep it.
  } else if (typeof window !== 'undefined' && isLocalAuthMode()) {
    const localToken = getLocalAccessToken();
    if (localToken) config.headers.Authorization = `Bearer ${localToken}`;
  } else if (typeof window !== 'undefined' && isSupabaseAuthEnabled()) {
    const supabase = getSupabaseBrowserClient();
    if (supabase) {
      try {
        // getSession() is cached by the Supabase JS client's internal
        // session cache (refreshed by autoRefreshToken). We read from it
        // here because it's the only call that exposes the access_token.
        // The underlying SDK only hits the network when the cache is cold
        // or the token has expired — not on every interceptor call.
        const { data } = await supabase.auth.getSession();
        if (data.session?.access_token) {
          cachedSession = data.session;
          config.headers.Authorization = `Bearer ${data.session.access_token}`;
        }
      } catch (error: unknown) {
        if (isInvalidRefreshTokenError(error)) {
          await clearSupabaseLocalSession();
          cachedSession = null;
        }
      }
    }
  }
  return config;
});

// Handle session-ending codes, token refresh on 401, and 5xx failover
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = (error.config || {}) as {
      _retry?: boolean;
      _apiBaseFailover?: boolean;
      _tokenRefresh?: boolean;
      baseURL?: string;
      method?: string;
      headers?: Record<string, string>;
    };
    const status = error.response?.status as number | undefined;
    const currentBaseUrl = originalRequest.baseURL || API_BASE_URL;
    const errorCode = getApiErrorCode(error);

    // Blocked account, device logged out (Settings / admin), unconfirmed
    // email: sign out locally and explain on /login. Must run before the
    // 401 refresh below -- a fresh token does not change these answers.
    if (getSessionEndingMessage(error)) {
      if (await endSessionAfterApiError(error)) {
        return new Promise(() => {}); // page is navigating to /login
      }
      return Promise.reject(error);
    }

    // Too many devices: keep the session but open Settings, where the
    // device list and "remove device" still work for this device.
    if (errorCode === 'device_limit_reached') {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/settings')) {
        window.location.href = '/settings?deviceLimit=1';
        return new Promise(() => {});
      }
      return Promise.reject(error);
    }

    // Freemium conversion layer (Task 9) — backend gates free users with
    // `code: 'upgrade_required'`. Open the global UpgradeModal so the user
    // sees the same CTA regardless of which surface they hit (Q-bank,
    // tests, AI tutor). Dynamic import keeps the paywall store out of
    // the SSR bundle for non-interactive pages.
    if (
      typeof window !== 'undefined' &&
      (errorCode === 'upgrade_required')
    ) {
      const data = (error.response?.data || {}) as {
        feature?: string;
        remaining?: number;
        cap?: number;
        message?: string;
      };
      const feature = data.feature || 'this feature';
      import('./paywall/paywallStore').then(({ showPaywall }) => {
        showPaywall(feature, {
          remaining: typeof data.remaining === 'number' ? data.remaining : null,
          cap: typeof data.cap === 'number' ? data.cap : null,
        });
      }).catch(() => {
        /* swallow — UI will fall back to whatever error the caller shows */
      });
    }

    // SECURITY / UX (Fix #7): on 401, refresh the Supabase session and retry
    // the original request once. Supabase access tokens are short-lived
    // (default 1h). Without this, a paying user who keeps a long-lived tab
    // open for >1h starts seeing 401s on every API call and has to reload --
    // and the profile refresh in auth.tsx falls back to mapSupabaseUser,
    // which has NO subscription_info. The refresh itself is bounded (see
    // supabaseTokenAfter401) so a backend that rejects valid sessions
    // cannot drive a refresh loop.
    if (
      status === 401 &&
      !originalRequest._tokenRefresh &&
      typeof window !== 'undefined' &&
      isLocalAuthMode()
    ) {
      originalRequest._tokenRefresh = true;
      const newToken = await refreshLocalAccessToken();
      if (newToken) {
        originalRequest.headers = originalRequest.headers || {};
        (originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`;
        return api(originalRequest);
      }
    }

    if (
      status === 401 &&
      !originalRequest._tokenRefresh &&
      typeof window !== 'undefined' &&
      !isLocalAuthMode() &&
      isSupabaseAuthEnabled()
    ) {
      originalRequest._tokenRefresh = true;
      const newToken = await supabaseTokenAfter401(bearerTokenOf(originalRequest.headers));
      if (newToken) {
        originalRequest.headers = originalRequest.headers || {};
        (originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`;
        return api(originalRequest);
      }
      // fall through to reject so the caller can render its own UI
    }

    const shouldFailover =
      !USE_API_PROXY &&
      !originalRequest._apiBaseFailover &&
      currentBaseUrl !== FALLBACK_API_BASE_URL &&
      IDEMPOTENT_METHODS.has((originalRequest.method || 'get').toLowerCase()) &&
      (status === 502 || status === 503 || status === 504);

    if (shouldFailover) {
      originalRequest._apiBaseFailover = true;
      originalRequest.baseURL = FALLBACK_API_BASE_URL;
      return api(originalRequest);
    }

    return Promise.reject(error);
  }
);

/**
 * Admin system actions. scope 'all' rewrites every user's data, so the backend
 * also requires confirm === 'RESET ALL' (the phrase the admin types in the
 * UI before the call is made). Callers should pass the typed phrase; until
 * the admin page does, scope 'all' calls default to the phrase here.
 */
type SystemActionPayload = { scope: 'all' | 'user'; user_id?: number; confirm?: string };
const PLATFORM_WIDE_CONFIRM_PHRASE = 'RESET ALL';
const withPlatformConfirm = (data: SystemActionPayload): SystemActionPayload =>
  data.scope === 'all' && data.confirm === undefined ? { ...data, confirm: PLATFORM_WIDE_CONFIRM_PHRASE } : data;

/** Scholarship challenge question as served by POST /auth/scholarship/start/ (no answer). */
export interface ScholarshipChallengeQuestion {
  id: number;
  question_text: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
}

// Auth API
export const authAPI = {
  register: (data: Record<string, string>) => api.post('/auth/register/', data),
  login: (data: { username: string; password: string }) => api.post('/auth/login/', data),
  getProfile: () => api.get('/auth/profile/'),
  updateProfile: (data: Record<string, string>) => api.patch('/auth/profile/', data),
  subscribe: () => api.post('/auth/subscribe/order/'),
  subscribeOrder: (plan?: string, requestId?: string) =>
    api.post('/auth/subscribe/order/', { plan, request_id: requestId }),
  subscribeVerify: (data: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) =>
    api.post('/auth/subscribe/verify/', data),
  // Local mock payments only (backend mounts this when PAYMENTS_MODE=mock + DEBUG).
  subscribeMockCheckout: (orderId: string) => api.post('/auth/subscribe/mock-checkout/', { order_id: orderId }),
  subscriptionStatus: () => api.get('/auth/subscribe/status/'),
  subscriptionHistory: () => api.get('/auth/subscribe/history/'),
  subscriptionInvoice: (subscriptionId: number) => api.get(`/auth/subscribe/invoice/${subscriptionId}/`),
  // Scholarship: the server picks the five questions and returns a signed
  // challenge_token that verifyScholarship must send back.
  startScholarship: () =>
    api.post<{ questions: ScholarshipChallengeQuestion[]; challenge_token: string | null; expires_in: number }>(
      '/auth/scholarship/start/',
    ),
  verifyScholarship: (answers: Record<string, string>, challengeToken?: string | null) =>
    api.post('/auth/verify-scholarship/', { answers, challenge_token: challengeToken || undefined }),
  // Password reset is Supabase-only (auth.tsx resetPassword); the old Django
  // /auth/password-reset/ endpoints now return 410.
  // Device management
  getDevices: () => api.get('/auth/devices/'),
  logoutDevice: (device_id: number) => api.post('/auth/devices/logout/', { device_id }),
  // Token system
  getTokenBalance: () => api.get('/auth/tokens/'),
  purchaseTokens: (data: { amount: number; payment_id?: string }) => api.post('/auth/tokens/purchase/', data),
  getTokenHistory: () => api.get('/auth/tokens/history/'),
  // Admin token management
  adminGetAllUsers: () => api.get('/auth/tokens/admin/users/'),
  adminGrantTokens: (data: { user_id: number; amount: number; note?: string }) => api.post('/auth/tokens/admin/grant/', data),
  adminTransferTokens: (data: { from_user_id?: number; to_user_id: number; amount: number; note?: string }) => api.post('/auth/tokens/admin/transfer/', data),
  adminAuditLogs: (params?: Record<string, string | number>) => api.get('/auth/tokens/admin/audit-logs/', { params }),
  adminListUsers: (params?: Record<string, string | number>) => api.get('/auth/admin/users/', { params }),
  adminToggleUserBlock: (userId: number, blocked: boolean) => api.patch(`/auth/admin/users/${userId}/block/`, { blocked }),
  adminUpdateUserRole: (userId: number, role: 'admin' | 'student') => api.patch(`/auth/admin/users/${userId}/role/`, { role }),
  adminResetUserProgress: (userId: number) => api.post(`/auth/admin/users/${userId}/reset-progress/`),
  adminResetAttempts: (data: SystemActionPayload) => api.post('/auth/admin/system/reset-attempts/', withPlatformConfirm(data)),
  adminClearAnalytics: (data: SystemActionPayload) => api.post('/auth/admin/system/clear-analytics/', withPlatformConfirm(data)),
  adminRerunEvaluation: (data: SystemActionPayload) => api.post('/auth/admin/system/rerun-evaluation/', withPlatformConfirm(data)),
  
  adminBackupData: () => api.post('/auth/admin/system/backup-data/'),
  adminRestoreData: () => api.post('/auth/admin/system/restore-data/'),
  
  // Phase 3 Admin Routes
  adminManageSubscription: (user_id: number, data: { action: 'grant' | 'revoke', plan?: string }) => 
    api.post(`/auth/admin/users/${user_id}/subscription/`, data),
  adminGetUserDevices: (user_id: number) => 
    api.get(`/auth/admin/users/${user_id}/devices/`),
  adminLogoutUserDevice: (user_id: number, device_id: number) => 
    api.post(`/auth/admin/users/${user_id}/devices/`, { device_id }),
  adminGetPayments: () => 
    api.get('/auth/admin/payments/'),
};

export const extractApiErrorMessage = (payload: unknown, fallback = 'Request failed') => {
  if (typeof payload === 'string') {
    const lowerPayload = payload.toLowerCase();
    if (
      lowerPayload.includes('<!doctype html') ||
      lowerPayload.includes('<html') ||
      lowerPayload.includes('body,html{height:100%') ||
      lowerPayload.includes('gateway timeout') ||
      lowerPayload.includes('status code 504')
    ) {
      return 'Service is temporarily unavailable (gateway timeout). Please try again in 30-60 seconds.';
    }

    const cleaned = payload.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    if (!cleaned) return fallback;
    const operationalError = cleaned.match(/OperationalError at/i);
    if (operationalError) {
      return 'Server database is not ready. Please try again in a minute.';
    }
    const notFound = cleaned.match(/Page not found/i);
    if (notFound) return 'Service endpoint not found. Please verify API URL configuration.';
    return cleaned.slice(0, 220);
  }

  if (payload && typeof payload === 'object') {
    const entries = Object.values(payload as Record<string, unknown>).flatMap((value) => {
      if (Array.isArray(value)) return value.map(String);
      if (typeof value === 'string') return [value];
      return [];
    });
    if (entries.length > 0) return entries.join(', ');
  }

  return fallback;
};

// Jobs API
export const jobsAPI = {
  list: (params?: Record<string, string | number>) => api.get('/jobs/', { params }),
  get: (id: number) => api.get(`/jobs/${id}/`),
  getCategories: () => api.get('/jobs/categories/'),
  bookmark: (id: number) => api.post(`/jobs/${id}/bookmark/`),
  // Admin only
  create: (data: Record<string, unknown>) => api.post('/jobs/', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/jobs/${id}/`, data),
  remove: (id: number) => api.delete(`/jobs/${id}/`),
};

// Announcements API
export const announcementsAPI = {
  list: (params?: Record<string, string | number>) => api.get('/questions/announcements/', { params }),
  get: (id: number) => api.get(`/questions/announcements/${id}/`),
  create: (data: Record<string, unknown>) => api.post('/questions/announcements/', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/questions/announcements/${id}/`, data),
  remove: (id: number) => api.delete(`/questions/announcements/${id}/`),
};

// Production Content Ingestion Platform (Phase 1) — isolated from
// the UPSC CMS. Mounted at /api/ingestion/. Admin-only.
export const ingestionAPI = {
  // Jobs
  listJobs: (params?: Record<string, string | number>) =>
    api.get('/ingestion/jobs/', { params }),
  getJob: (id: number) => api.get(`/ingestion/jobs/${id}/`),
  createJob: (data: {
    material_sha16: string;
    parent_exam: string;
    batch_id?: number;
    // 'auto-all' is no longer accepted by the API (400).
    strategy?: 'auto-pr-only' | 'manual';
  }) => api.post('/ingestion/jobs/', data),
  retryJob: (id: number) => api.post(`/ingestion/jobs/${id}/retry/`, {}),
  cancelJob: (id: number) => api.post(`/ingestion/jobs/${id}/cancel/`, {}),
  listStages: (id: number) => api.get(`/ingestion/jobs/${id}/stages/`),
  listCheckpoints: (id: number) => api.get(`/ingestion/jobs/${id}/checkpoints/`),
  listLogs: (id: number, params?: Record<string, string | number>) =>
    api.get(`/ingestion/jobs/${id}/logs/`, { params }),
  listStagedQuestions: (id: number, params?: Record<string, string | number>) =>
    api.get(`/ingestion/jobs/${id}/staged-questions/`, { params }),

  // Materials
  listMaterials: (params?: Record<string, string | number>) =>
    api.get('/ingestion/materials/', { params }),
  getMaterial: (sha16: string) => api.get(`/ingestion/materials/${sha16}/`),
  uploadMaterial: (file: File, meta: { exam_hint?: string } = {}) => {
    const fd = new FormData();
    fd.append('file', file);
    if (meta.exam_hint) fd.append('exam_hint', meta.exam_hint);
    return api.post('/ingestion/materials/upload/', fd, {
      headers: { 'Content-Type': undefined },
    });
  },

  // Batches
  listBatches: (params?: Record<string, string | number>) =>
    api.get('/ingestion/batches/', { params }),
  getBatch: (id: number) => api.get(`/ingestion/batches/${id}/`),
  createBatch: (data: {
    name: string;
    material_sha16s: string[];
    parent_exam: string;
    // 'auto-all' is no longer accepted by the API (400).
    strategy?: 'auto-pr-only' | 'manual';
  }) => api.post('/ingestion/batches/', data),
};
// Questions API
export const questionsAPI = {
  list: (params?: Record<string, string | number>) => api.get('/questions/', { params }),
  get: (id: number) => api.get(`/questions/${id}/`),
  getSimilar: (id: number) => api.get(`/questions/${id}/similar/`),
  getImages: (id: number) => api.get(`/questions/${id}/images/`),
  getSubjects: (params?: Record<string, string | number>) => api.get('/questions/subjects/', { params }),
  getTopics: (params?: Record<string, string | number>) => api.get('/questions/topics/', { params }),
  getExamTracks: (params?: Record<string, string | number>) => api.get('/questions/exam-tracks/', { params }),
  getYears: () => api.get('/questions/years/'),
  getStats: (params?: Record<string, string | number>) => api.get('/questions/stats/', { params }),
  bookmark: (id: number) => api.post(`/questions/${id}/bookmark/`),
  // time_spent_seconds feeds server-side study-time tracking (optional).
  attempt: (id: number, data: { selected_answer: string; time_spent_seconds?: number }) =>
    api.post(`/questions/${id}/attempt/`, data),
  getBookmarks: () => api.get('/questions/bookmarks/'),
  upload: (data: Record<string, unknown>[]) => api.post('/questions/upload/', data),
  create: (data: Record<string, unknown>) => api.post('/questions/', data),
  update: (id: number, data: Record<string, unknown>, opts?: { ifMatch?: string }) => {
    const headers = opts?.ifMatch ? { 'If-Match': opts.ifMatch } : undefined;
    return api.patch(`/questions/${id}/`, data, { headers });
  },
  remove: (id: number) => api.delete(`/questions/${id}/`),
  submitFeedback: (data: { question: number; category: string; comment: string }) =>
    api.post('/questions/feedback/', data),
  getFeedback: (params?: Record<string, string>) => api.get('/questions/feedback/', { params }),
  resolveFeedback: (id: number) => api.patch(`/questions/feedback/${id}/resolve/`),
  getAdminIssueQueue: (params?: Record<string, string | number>) => api.get('/questions/feedback/admin-queue/', { params }),
  updateFeedbackStatus: (id: number, data: Record<string, unknown>) => api.patch(`/questions/feedback/${id}/status/`, data),
  verify: (id: number, verified_note?: string) => api.patch(`/questions/${id}/verify/`, { verified_note }),
  unverify: (id: number) => api.patch(`/questions/${id}/unverify/`),
  duplicate: (id: number) => api.post(`/questions/${id}/duplicate/`),
  archive: (id: number) => api.patch(`/questions/${id}/archive/`),
  unarchive: (id: number) => api.patch(`/questions/${id}/unarchive/`),
  importPreview: (data: Record<string, unknown>) => api.post('/questions/import-preview/', data),
  bulkMetadataUpdate: (data: Record<string, unknown>) => api.patch('/questions/bulk-metadata/', data),
  bulkDelete: (data: Record<string, unknown>) => api.post('/questions/bulk-delete/', data),
  extractionUpload: (data: FormData) => api.post('/questions/extraction/upload/', data, { headers: { 'Content-Type': undefined } }),
  extractionJobs: (params?: Record<string, string | number>) => api.get('/questions/extraction/jobs/', { params }),
  extractionRetry: (jobId: number) => api.post(`/questions/extraction/jobs/${jobId}/retry/`),
  extractionItems: (jobId: number) => api.get(`/questions/extraction/jobs/${jobId}/items/`),
  extractionItemUpdate: (itemId: number, data: Record<string, unknown>) => api.patch(`/questions/extraction/items/${itemId}/`, data),
  extractionItemAutotag: (itemId: number) => api.post(`/questions/extraction/items/${itemId}/autotag/`),
  extractionItemApprove: (itemId: number) => api.post(`/questions/extraction/items/${itemId}/approve/`),
  extractionItemReject: (itemId: number, data?: Record<string, unknown>) => api.post(`/questions/extraction/items/${itemId}/reject/`, data || {}),
  extractionItemPublish: (itemId: number) => api.post(`/questions/extraction/items/${itemId}/publish/`),
  aiOverride: (id: number, data: Record<string, unknown>) => api.patch(`/questions/${id}/ai-override/`, data),
  aiLock: (id: number, data: Record<string, unknown>) => api.patch(`/questions/${id}/ai-lock/`, data),
  forceRegenerate: (id: number) => api.post(`/questions/${id}/force-regenerate/`),
  generateVideo: (id: number) => api.post(`/questions/${id}/generate-video/`),
  aiPromptVersions: () => api.get('/questions/ai-prompt-versions/'),
  createAiPromptVersion: (data: { name: string; prompt_text: string; activate?: boolean }) => api.post('/questions/ai-prompt-versions/', data),
  activateAiPromptVersion: (versionId: number) => api.post(`/questions/ai-prompt-versions/${versionId}/activate/`),
  aiTimeline: (id: number) => api.get(`/questions/${id}/ai-timeline/`),
  getRevisions: (id: number) => api.get(`/questions/${id}/revisions/`),
  getRevisionDiff: (id: number, revisionId?: number) => api.get(`/questions/${id}/revisions-diff/`, { params: revisionId ? { revision_id: revisionId } : {} }),
  undoRevision: (id: number, revisionId?: number) => api.post(`/questions/${id}/undo-last-revision/`, revisionId ? { revision_id: revisionId } : {}),
  linkRelatedPyqs: (id: number, relatedIds: number[]) => api.patch(`/questions/${id}/related-pyqs/`, { related_ids: relatedIds }),
  setConceptId: (id: number, conceptId: string) => api.patch(`/questions/${id}/concept-id/`, { concept_id: conceptId }),
  updateReference: (id: number, data: Record<string, unknown>) => api.patch(`/questions/${id}/reference/`, data),
  formatFix: (id: number) => api.patch(`/questions/${id}/format-fix/`),
  // Admin AI explanation generation
  generateExplanation: (id: number, data: { correct_answer: string; regenerate_if_exists?: boolean; update_correct_answer?: boolean }) =>
    api.post(`/questions/${id}/generate-explanation/`, data),
  uploadImage: (data: { questionId: number; file: File; role?: 'primary' | 'option' | 'illustration' | 'explanation' }) => {
    const form = new FormData();
    form.append('question_id', String(data.questionId));
    form.append('file', data.file);
    // Optional role hint. The admin editor sends 'explanation' when the
    // upload is triggered from the explanation / concept_explanation /
    // mnemonic field so the backend records the row with role='explanation'
    // and the question stem pane stops showing the figure before the
    // student attempts the question. Omitting role keeps the prior
    // 'illustration' default for legacy callers.
    if (data.role) form.append('role', data.role);
    return api.post('/questions/images/', form, {
      headers: { 'Content-Type': undefined },
    });
  },
  updateImage: (id: number, data: Record<string, unknown>) =>
    api.patch(`/questions/images/${id}/`, data),
  deleteImage: (id: number) => api.delete(`/questions/images/${id}/`),
  reorderImage: (id: number, newIndex: number) =>
    api.post(`/questions/images/${id}/reorder/`, { new_index_in_page: newIndex }),

  // Duplicate-question detection / merging (Bug 4).
  // GET /questions/<id>/duplicates/                — { cluster_id, canonical_id, members: [...] }
  // POST /questions/<id>/merge-duplicates/         — { duplicate_ids: [...] } soft-drops siblings.
  listDuplicates: (id: number) => api.get(`/questions/${id}/duplicates/`),
  mergeDuplicates: (id: number, data: { duplicate_ids: number[] }) =>
    api.post(`/questions/${id}/merge-duplicates/`, data),

  // Durable soft-delete (the "Remove from bank" admin action).
  // POST /questions/<id>/remove-from-bank/         — { reason?: string }
  //   Soft-deletes the row (is_active=False, is_dropped=True) AND
  //   records its stem hash in `RemovedQuestion` so the next
  //   import_neet_pg / load_exam_fixture deploy won't re-create it.
  // POST /questions/<id>/unremove-from-bank/       — restores the row.
  removeFromBank: (id: number, data?: { reason?: string }) =>
    api.post(`/questions/${id}/remove-from-bank/`, data || {}),
  unremoveFromBank: (id: number) =>
    api.post(`/questions/${id}/unremove-from-bank/`, {}),
};

// Tests API
export const testsAPI = {
  list: (params?: Record<string, string>) => api.get('/tests/', { params }),
  get: (id: number) => api.get(`/tests/${id}/`),
  generate: (data: Record<string, string | number>) => api.post('/tests/generate/', data),
  createManual: (data: Record<string, unknown>) => api.post('/tests/create-manual/', data),
  setQuestions: (id: number, questionIds: number[]) => api.patch(`/tests/${id}/set-questions/`, { question_ids: questionIds }),
  publish: (id: number) => api.patch(`/tests/${id}/publish/`),
  unpublish: (id: number) => api.patch(`/tests/${id}/unpublish/`),
  duplicate: (id: number) => api.post(`/tests/${id}/duplicate/`),
  safeUpdate: (id: number, data: Record<string, unknown>) => api.patch(`/tests/${id}/safe-update/`, data),
  start: (id: number) => api.post(`/tests/${id}/start/`),
  submit: (id: number, data: Record<string, unknown>) => api.post(`/tests/${id}/submit/`, data),
  review: (id: number, attemptId: number) => api.get(`/tests/${id}/review/`, { params: { attempt_id: attemptId } }),
  // exam_type scopes the paper / adaptive pool (e.g. 'cms', 'neet_pg').
  generateAdaptive: (data: { num_questions?: number; exam_type?: string }) => api.post('/tests/generate-adaptive/', data),
  pyqSimulation: (data: { year: number; paper?: number; exam_type?: string }) => api.post('/tests/pyq-simulation/', data),
  getAttempts: () => api.get('/tests/attempts/'),
  getAttempt: (id: number) => api.get(`/tests/attempts/${id}/`),
};

// Analytics API
export const analyticsAPI = {
  getDashboard: () => api.get('/analytics/dashboard/'),
  getBundle: () => api.get('/analytics/dashboard/bundle/'),
  getWeakTopics: () => api.get('/analytics/weak-topics/'),
  getTopicPerformance: () => api.get('/analytics/topic-performance/'),
  getHeatmap: () => api.get('/analytics/heatmap/'),
  getRecentAttempts: () => api.get('/analytics/recent-attempts/'),
  getScorePrediction: () => api.get('/analytics/score-prediction/'),
  getPerformanceTrend: () => api.get('/analytics/performance-trend/'),
  // Feedback
  getFeedback: () => api.get('/analytics/feedback/'),
  submitFeedback: (data: { category: string; rating: number; title: string; message: string }) =>
    api.post('/analytics/feedback/', data),
  replyFeedback: (id: number, data: { admin_reply: string }) =>
    api.patch(`/analytics/feedback/${id}/`, data),
  deleteFeedback: (id: number) => api.delete(`/analytics/feedback/${id}/`),
  contactUs: (data: { name: string; email: string; subject: string; message: string }) =>
    api.post('/analytics/contact/', data),
  exportData: (type?: string) => api.get('/analytics/export/', { params: { type: type || 'all' } }),
  exportCSV: (type: string) => api.get('/analytics/export/csv/', { params: { type }, responseType: 'blob' }),
  // Announcements ({scope: 'all'} lets admins include expired / inactive ones)
  getAnnouncements: (params?: Record<string, string | number>) => api.get('/analytics/announcements/', { params }),
  createAnnouncement: (data: { title: string; message: string; priority: string; expires_at?: string }) =>
    api.post('/analytics/announcements/', data),
  updateAnnouncement: (id: number, data: Record<string, unknown>) =>
    api.patch(`/analytics/announcements/${id}/`, data),
  deleteAnnouncement: (id: number) => api.delete(`/analytics/announcements/${id}/`),
  // Gamification
  getStreak: () => api.get('/analytics/streak/'),
  getBadges: () => api.get('/analytics/badges/'),
  getLeaderboard: (period?: string) => api.get('/analytics/leaderboard/', { params: { period } }),
  // Admin
  getAdminDashboard: () => api.get('/analytics/admin-dashboard/'),
  getWeakAreaControl: (params?: Record<string, string | number>) => api.get('/analytics/admin/weak-area-control/', { params }),
  listCampaigns: (params?: Record<string, string | number>) => api.get('/analytics/admin/campaigns/', { params }),
  createCampaign: (data: Record<string, unknown>) => api.post('/analytics/admin/campaigns/', data),
  sendCampaignNow: (id: number) => api.post(`/analytics/admin/campaigns/${id}/send-now/`),
  // Internal analytics ingestion + admin dashboard
  ingestEvent: (data: Record<string, unknown>) =>
    api.post('/analytics/events/', data, { timeout: 5000 }),
  getAdminDashboardData: () =>
    api.get('/analytics/admin/dashboard-data/', { timeout: 15000 }),
};


// AI API — 120s timeout for AI calls (backend cold starts + LLM latency)
const AI_TIMEOUT = 120000;

export const aiAPI = {
  askTutor: (data: { question: string; context?: string }) => api.post('/ai/tutor/', data, { timeout: AI_TIMEOUT }),
  generateMnemonic: (data: { topic: string; concept?: string }) => api.post('/ai/mnemonic/', data, { timeout: AI_TIMEOUT }),
  explain: (data: { concept: string; level?: string }) => api.post('/ai/explain/', data, { timeout: AI_TIMEOUT }),
  analyzeQuestion: (data: Record<string, string>) => api.post('/ai/analyze/', data, { timeout: AI_TIMEOUT }),
  explainAfterAnswer: (data: {
    // Bank question id: lets the backend use (and store) the question's own
    // explanation and apply its answer-access rules.
    question_id?: number;
    question_text: string;
    options?: Record<string, string>;
    correct_answer?: string;
    selected_answer?: string;
    subject?: string;
    topic?: string;
  }) => api.post('/ai/explain-answer/', data, { timeout: AI_TIMEOUT }),
  explainQuestion: (questionId: number, data: Record<string, unknown> = {}, config?: Record<string, unknown>) =>
    api.post(`/ai/explain-question/${questionId}/`, data, { timeout: AI_TIMEOUT, ...config }),
  // RAG endpoints
  ragSearch: (data: { query: string; book?: string; n_results?: number }) => api.post('/ai/rag-search/', data, { timeout: AI_TIMEOUT }),
  ragAnswer: (data: { question: string }) => api.post('/ai/rag-answer/', data, { timeout: AI_TIMEOUT }),
  textbookReference: (data: { question_text: string }) => api.post('/ai/textbook-reference/', data, { timeout: AI_TIMEOUT }),
  getScreenshot: (questionId: number) => api.get(`/ai/screenshot/${questionId}/`),
  // Study planning
  getStudyPlan: (data: { weak_topics?: string[]; days_remaining?: number }) => api.post('/ai/study-plan/', data, { timeout: AI_TIMEOUT }),
  getHighYieldTopics: () => api.get('/ai/high-yield/'),
  // Knowledge base management (auto-ingest)
  uploadKnowledge: (file: File, bookName?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (bookName) formData.append('book_name', bookName);
    return api.post('/ai/knowledge/upload/', formData, { headers: { 'Content-Type': undefined } });
  },
  scanKnowledge: () => api.post('/ai/knowledge/scan/'),
  getKnowledgeStats: () => api.get('/ai/knowledge/stats/'),
  generateQuestions: (data: { subject: string; topic?: string; difficulty?: string; count?: number }) =>
    api.post('/ai/generate-questions/', data, { timeout: AI_TIMEOUT }),
  // Chat history
  getChatSessions: () => api.get('/ai/chat/sessions/'),
  createChatSession: (data: { mode?: string; title?: string }) => api.post('/ai/chat/sessions/', data),
  getChatSession: (id: number) => api.get(`/ai/chat/sessions/${id}/`),
  deleteChatSession: (id: number) => api.delete(`/ai/chat/sessions/${id}/`),
  getChatMessages: (sessionId: number) => api.get(`/ai/chat/sessions/${sessionId}/messages/`),
  addChatMessage: (sessionId: number, data: { role: string; content: string; mode?: string; citations?: Array<{ book: string; page: number; excerpt: string; relevance: number }> }) =>
    api.post(`/ai/chat/sessions/${sessionId}/messages/add/`, data),
};

// Blog API is in @/lib/blogAPI.ts (blog_api import)

// Textbooks API
export const textbooksAPI = {
  list: (params?: Record<string, string | number>) => api.get('/textbooks/books/', { params }),
  get: (id: number) => api.get(`/textbooks/books/${id}/`),
  getChapters: (bookId: number) => api.get(`/textbooks/books/${bookId}/`, { params: { expand: 'chapters' } }),
  create: (data: Record<string, unknown>) => api.post('/textbooks/books/', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/textbooks/books/${id}/`, data),
  remove: (id: number) => api.delete(`/textbooks/books/${id}/`),
  upload: (data: FormData) => api.post('/textbooks/uploads/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  getUploads: () => api.get('/textbooks/uploads/'),
  getChunks: (params?: Record<string, string | number>) => api.get('/textbooks/books/chunks/', { params }),
  getChunkDiagnostics: () => api.get('/textbooks/books/chunks/diagnostics/'),
  deleteChunk: (chunkId: number) => api.post('/textbooks/books/chunks/delete/', { chunk_id: chunkId }),
  markChunk: (chunkId: number, status: 'approved' | 'rejected' | 'pending') => api.post('/textbooks/books/chunks/mark/', { chunk_id: chunkId, status }),
  mergeChunks: (chunkIds: number[]) => api.post('/textbooks/books/chunks/merge/', { chunk_ids: chunkIds }),
  rechunk: (chunkIds: number[], chunkSize = 500, overlap = 50) => api.post('/textbooks/books/chunks/rechunk/', { chunk_ids: chunkIds, chunk_size: chunkSize, overlap }),
  mapQuestionReference: (data: FormData) => api.post('/textbooks/books/question-reference-map/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  getReferenceOverrides: (params?: Record<string, string | number>) => api.get('/textbooks/books/question-reference-overrides/', { params }),
};

// Resources API
export const resourcesAPI = {
  getCatalog: () => api.get('/resources/catalog/'),
  getExamGuide: () => api.get('/resources/exam-guide/'),
  downloadUrl: (id: string) => `${api.defaults.baseURL}/resources/download/${id}/`,
};

// Discussions API
export const discussionsAPI = {
  list: (questionId: number) => api.get('/questions/discussions/', { params: { question: questionId } }),
  create: (data: { question: number; text: string; parent?: number }) => api.post('/questions/discussions/', data),
  replies: (id: number) => api.get(`/questions/discussions/${id}/replies/`),
  vote: (id: number, voteType: 'up' | 'down') => api.post(`/questions/discussions/${id}/vote/`, { vote_type: voteType }),
};

// Topic Notes API — PYQ explanation → revision notes pipeline
export const topicNotesAPI = {
  // `/questions/notes/` is the *personal* notes endpoint; admin topic notes
  // live under `/questions/topic-notes/library/`.
  list: (params?: Record<string, string | number>) => api.get('/questions/topic-notes/library/', { params }),
  get: (id: number) => api.get(`/questions/topic-notes/library/${id}/`),
  create: (data: { subject: number; topic: number; exam_type?: string; title: string; content?: string; source_question_ids?: number[] }) =>
    api.post('/questions/topic-notes/library/', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/questions/topic-notes/library/${id}/`, data),
  delete: (id: number) => api.delete(`/questions/topic-notes/library/${id}/`),
  generateFromTopic: (id: number) => api.post(`/questions/topic-notes/library/${id}/generate/`),
  // Admin topic notes (exam_type-specific)
  adminList: (params?: Record<string, string | number>) => api.get('/questions/topic-notes/library/', { params }),
  adminCreate: (data: Record<string, unknown>) => api.post('/questions/topic-notes/', data),
  adminGenerate: (id: number) => api.post(`/questions/topic-notes/${id}/generate/`),
};

// Mistake Notebook API — student review tracking
export const mistakeNotebookAPI = {
  list: (params?: Record<string, string | number>) => api.get('/analytics/mistake-notebook/', { params }),
  add: (data: { question: number; selected_answer?: string; user_note?: string; is_flagged?: boolean }) =>
    api.post('/analytics/mistake-notebook/', data),
  get: (id: number) => api.get(`/analytics/mistake-notebook/${id}/`),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/analytics/mistake-notebook/${id}/`, data),
  remove: (id: number) => api.delete(`/analytics/mistake-notebook/${id}/`),
  review: (id: number) => api.post(`/analytics/mistake-notebook/${id}/review/`),
  due: () => api.get('/analytics/mistake-notebook/due/'),
  stats: () => api.get('/analytics/mistake-notebook/stats/'),
};

// Study Time API — time-per-subject tracking
export const studyTimeAPI = {
  record: (data: { subject: number; seconds: number; question_count: number; date?: string }) =>
    api.post('/analytics/study-time/', data),
  list: (params?: { start?: string; end?: string }) =>
    api.get('/analytics/study-time/', { params }),
};

// Quests API — daily quests and streaks
export const questsAPI = {
  list: (params?: { status?: string }) =>
    api.get('/analytics/quests/', { params }),
  get: (id: number) => api.get(`/analytics/quests/${id}/`),
  // Claim a finished quest; the server validates progress and awards XP.
  complete: (id: number) => api.patch(`/analytics/quests/${id}/`, { is_completed: true }),
  remove: (id: number) => api.delete(`/analytics/quests/${id}/`),
  getStreak: () => api.get('/analytics/quests/streak/'),
  toggleFreeze: () => api.post('/analytics/quests/streak/freeze/'),
  // Explicit state: a double click cannot flip it back.
  setFreeze: (frozen: boolean) => api.post('/analytics/quests/streak/freeze/', { streak_frozen: frozen }),
};

// Notes API — user personal notes
export const notesAPI = {
  list: (params?: { question?: number; topic?: number }) => api.get('/questions/notes/', { params }),
  create: (data: { question?: number; topic?: number; title?: string; content: string }) => api.post('/questions/notes/', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/questions/notes/${id}/`, data),
  delete: (id: number) => api.delete(`/questions/notes/${id}/`),
};

// Flashcards API
export const flashcardsAPI = {
  list: (params?: { subject?: number; due?: string }) => api.get('/questions/flashcards/', { params }),
  create: (data: { question?: number; subject?: number; front: string; back: string; difficulty?: string; personal_note?: string }) =>
    api.post('/questions/flashcards/', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/questions/flashcards/${id}/`, data),
  delete: (id: number) => api.delete(`/questions/flashcards/${id}/`),
  review: (id: number, quality: number) => api.post(`/questions/flashcards/${id}/review/`, { quality }),
  analytics: () => api.get('/questions/flashcards/analytics/'),
};

// Admin Import Center API (Phase 1)
export const importCenterAPI = {
  // Dashboard / health
  dashboard: () => api.get('/admin/import/dashboard/'),
  health: () => api.get('/admin/import/health/'),
  lookups: () => api.get('/admin/import/lookups/'),
  search: (q: string) => api.get('/admin/import/search/', { params: { q } }),

  // Batches
  listBatches: (params?: Record<string, string | number>) => api.get('/admin/import/batches/', { params }),
  getBatch: (id: number) => api.get(`/admin/import/batches/${id}/`),
  getBatchMaterials: (id: number) => api.get(`/admin/import/batches/${id}/materials/`),
  getBatchAudit: (id: number, page = 1, pageSize = 50) =>
    api.get(`/admin/import/batches/${id}/audit/`, { params: { page, page_size: pageSize } }),
  getBatchReport: (id: number) => api.get(`/admin/import/batches/${id}/report/`),

  upload: (formData: FormData, onProgress?: (p: number) => void) =>
    api.post('/admin/import/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress
        ? (e: { loaded: number; total?: number }) =>
            onProgress(e.total ? Math.round((e.loaded / e.total) * 100) : 0)
        : undefined,
    }),
  cancelBatch: (id: number) => api.post(`/admin/import/batches/${id}/cancel/`),
  publishBatch: (id: number, data: { max_per_test?: number; only_publish?: boolean; build_tests?: boolean }) =>
    api.post(`/admin/import/batches/${id}/publish/`, data),
  rollbackBatch: (id: number, delete_published = false) =>
    api.post(`/admin/import/batches/${id}/rollback/`, { delete_published, confirm: true }),
  republishBatch: (id: number) => api.post(`/admin/import/batches/${id}/republish/`),
  generateMock: (id: number, data: {
    strategy: string; question_count?: number; difficulty?: string;
    subject_id?: number | null; topic_id?: number | null;
  }) => api.post(`/admin/import/batches/${id}/generate-mock/`, data),

  // Questions / review queue
  listQuestions: (params?: Record<string, string | number>) => api.get('/admin/import/questions/', { params }),
  getQuestion: (id: number) => api.get(`/admin/import/questions/${id}/`),
  decideQuestion: (id: number, decision: 'approve' | 'reject' | 'reset', note = '') =>
    api.post(`/admin/import/questions/${id}/decision/`, { decision, note }),
  classifyQuestion: (id: number, use_ai = true) =>
    api.post(`/admin/import/questions/${id}/classify-ai/`, { use_ai }),
  bulkDecide: (ids: number[], decision: 'approve' | 'reject' | 'reset', note = '') =>
    api.post('/admin/import/questions/bulk-decision/', { ids, decision, note }),
};

export default api;
