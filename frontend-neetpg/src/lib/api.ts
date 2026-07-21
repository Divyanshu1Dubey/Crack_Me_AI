/**
 * api.ts — NEET PG site. Wraps the shared Django backend at
 * `NEXT_PUBLIC_API_URL` (default: production backend) and attaches the
 * Supabase access token on every request.
 *
 * Behaviour:
 *  - Auto-attaches `Authorization: Bearer <supabase access token>` from the
 *    browser Supabase client.
 *  - On 401 (`session_invalid`) the local session is cleared and the page
 *    redirected to /login.
 *  - On 502/503/504 the request retries once against `NEXT_PUBLIC_API_FALLBACK_URL`.
 *
 * NOTE: This file mirrors `frontend/src/lib/api.ts` with the production
 * base URL pointed at the shared backend (was hard-coded to the CMS domain
 * in the original — see `DEFAULT_PRODUCTION_API_URL`).
 */
import axios, { AxiosError, AxiosInstance } from "axios";
import { getSupabaseBrowserClient } from "./supabase";

const DEFAULT_PRODUCTION_API_URL = "https://crackcms-vsthc.ondigitalocean.app/api";

const resolveBaseURL = (): string => {
    const fromEnv = process.env.NEXT_PUBLIC_API_URL;
    if (fromEnv && fromEnv.length > 0) return fromEnv;
    if (typeof window !== "undefined") {
        const host = window.location.hostname;
        if (host === "localhost" || host === "127.0.0.1") {
            return "http://localhost:8000/api";
        }
    }
    return DEFAULT_PRODUCTION_API_URL;
};

const resolveFallbackURL = (): string | undefined => {
    const fb = process.env.NEXT_PUBLIC_API_FALLBACK_URL;
    return fb && fb.length > 0 ? fb : undefined;
};

const baseURL = resolveBaseURL();
const fallbackURL = resolveFallbackURL();

const apiClient: AxiosInstance = axios.create({
    baseURL,
    timeout: 30_000,
    headers: { "Content-Type": "application/json" },
});

let accessToken: string | null = null;

export function setApiAccessToken(token: string | null) {
    accessToken = token;
}

apiClient.interceptors.request.use((config) => {
    if (accessToken) {
        config.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    return config;
});

const UNHEALTHY_STATUS = new Set([502, 503, 504]);

apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const status = error.response?.status;

        if (status === 401 && typeof window !== "undefined") {
            // Token rejected — clear local session.
            try {
                const supabase = getSupabaseBrowserClient();
                await supabase.auth.signOut();
            } catch {
                /* no-op */
            }
            window.location.href = "/login";
            return Promise.reject(error);
        }

        if (status && UNHEALTHY_STATUS.has(status) && fallbackURL) {
            // Single retry against the fallback URL.
            try {
                const retry = await axios.request({
                    ...error.config,
                    baseURL: fallbackURL,
                    headers: { ...(error.config?.headers ?? {}), Authorization: `Bearer ${accessToken ?? ""}` },
                });
                return retry;
            } catch (retryErr) {
                return Promise.reject(retryErr);
            }
        }

        return Promise.reject(error);
    }
);

// ─── API surface (per-feature modules) ────────────────────────────────────

export const authAPI = {
    profile: () => apiClient.get("/auth/profile/"),
};

export const questionsAPI = {
    list: (params: Record<string, unknown> = {}) =>
        apiClient.get("/questions/", { params }),
    get: (id: number) => apiClient.get(`/questions/${id}/`),
    getSubjects: () => apiClient.get("/questions/subjects/", {
        params: { exam_type: "neet_pg" },
    }),
    getYears: () => apiClient.get("/questions/years/", {
        params: { exam_type: "neet_pg" },
    }),
    getStats: (params: Record<string, unknown> = {}) =>
        apiClient.get("/questions/stats/", { params: { ...params, exam_type: "neet_pg" } }),
    attempt: (id: number, body: { selected_answer: string }) =>
        apiClient.post(`/questions/${id}/attempt/`, body),
    bookmark: (id: number) => apiClient.post(`/questions/${id}/bookmark/`),
    myBookmarks: () => apiClient.get("/questions/my-bookmarks/"),
    getSimilar: (id: number) => apiClient.get(`/questions/${id}/similar_questions/`),
    submitFeedback: (body: { question: number; category: string; comment: string }) =>
        apiClient.post("/questions/feedback/", body),
};

export const aiAPI = {
    explainAfterAnswer: (payload: Record<string, unknown>) =>
        apiClient.post("/questions/explain-after-answer/", payload),
    textbookReference: (payload: { question_text: string }) =>
        apiClient.post("/ai/textbook-reference/", payload),
    getScreenshot: (questionId: number) =>
        apiClient.get(`/ai/textbook-screenshot/${questionId}/`),
};

export const testsAPI = {
    list: () => apiClient.get("/tests/"),
    pyqSimulation: (body: { year: number }) =>
        apiClient.post("/tests/pyq-simulation/", body),
};

export const analyticsAPI = {
    dashboard: () => apiClient.get("/analytics/dashboard/"),
};

export const tokensAPI = {
    balance: () => apiClient.get("/tokens/balance/"),
    history: () => apiClient.get("/tokens/history/"),
    purchase: (body: { package: string }) => apiClient.post("/tokens/purchase/", body),
};

export const announcementsAPI = {
    list: () => apiClient.get("/questions/announcements/", { params: { exam_type: "neet_pg" } }),
};

/** Pull the most useful error message out of a DRF error response. */
export function extractApiErrorMessage(payload: unknown, fallback: string): string {
    if (typeof payload === "string") return payload;
    if (payload && typeof payload === "object") {
        const obj = payload as Record<string, unknown>;
        if (typeof obj.detail === "string") return obj.detail;
        if (typeof obj.error === "string") return obj.error;
        if (typeof obj.message === "string") return obj.message;
        for (const value of Object.values(obj)) {
            if (Array.isArray(value) && value.length > 0) return String(value[0]);
        }
    }
    return fallback;
}

export default apiClient;
