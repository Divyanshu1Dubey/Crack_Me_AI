/**
 * api.ts — FMGE site. Mirrors the NEET PG / USMLE api.ts but with
 * `exam_type="fmge"` baked into question requests.
 */
import axios, { AxiosError, AxiosInstance } from "axios";
import { getSupabaseBrowserClient } from "./supabase";

const DEFAULT_PRODUCTION_API_URL = "https://crackcms-vsthc.ondigitalocean.app/api";

const resolveBaseURL = (): string => {
    const fromEnv = process.env.NEXT_PUBLIC_API_URL;
    if (fromEnv) return fromEnv;
    if (typeof window !== "undefined") {
        const host = window.location.hostname;
        if (host === "localhost" || host === "127.0.0.1") return "http://localhost:8000/api";
    }
    return DEFAULT_PRODUCTION_API_URL;
};

const baseURL = resolveBaseURL();
const fallbackURL = process.env.NEXT_PUBLIC_API_FALLBACK_URL || undefined;

const apiClient: AxiosInstance = axios.create({
    baseURL, timeout: 30_000,
    headers: { "Content-Type": "application/json" },
});

let accessToken: string | null = null;
export function setApiAccessToken(token: string | null) { accessToken = token; }

apiClient.interceptors.request.use((c) => {
    if (accessToken) c.headers.set("Authorization", `Bearer ${accessToken}`);
    return c;
});

const UNHEALTHY_STATUS = new Set([502, 503, 504]);
apiClient.interceptors.response.use(
    (r) => r,
    async (error: AxiosError) => {
        const status = error.response?.status;
        if (status === 401 && typeof window !== "undefined") {
            try { await getSupabaseBrowserClient().auth.signOut(); } catch { /* noop */ }
            window.location.href = "/login";
            return Promise.reject(error);
        }
        if (status && UNHEALTHY_STATUS.has(status) && fallbackURL) {
            try {
                return await axios.request({
                    ...error.config, baseURL: fallbackURL,
                    headers: { ...(error.config?.headers ?? {}), Authorization: `Bearer ${accessToken ?? ""}` },
                });
            } catch (e) { return Promise.reject(e); }
        }
        return Promise.reject(error);
    }
);

export const authAPI = { profile: () => apiClient.get("/auth/profile/") };
export const questionsAPI = {
    list: (params: Record<string, unknown> = {}) =>
        apiClient.get("/questions/", { params: { ...params, exam_type: "fmge" } }),
    get: (id: number) => apiClient.get(`/questions/${id}/`),
    getSubjects: () => apiClient.get("/questions/subjects/", { params: { exam_type: "fmge" } }),
    getYears: () => apiClient.get("/questions/years/", { params: { exam_type: "fmge" } }),
    getStats: (params: Record<string, unknown> = {}) =>
        apiClient.get("/questions/stats/", { params: { ...params, exam_type: "fmge" } }),
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
    getScreenshot: (id: number) => apiClient.get(`/ai/textbook-screenshot/${id}/`),
};
export const testsAPI = {
    list: () => apiClient.get("/tests/"),
    pyqSimulation: (body: { year: number }) => apiClient.post("/tests/pyq-simulation/", body),
    fmgeSimulation: (body: { blueprint?: boolean } = { blueprint: true }) =>
        apiClient.post("/tests/fmge-simulation/", body),
};
export const analyticsAPI = { dashboard: () => apiClient.get("/analytics/dashboard/") };
export const tokensAPI = {
    balance: () => apiClient.get("/tokens/balance/"),
    history: () => apiClient.get("/tokens/history/"),
    purchase: (body: { package: string }) => apiClient.post("/tokens/purchase/", body),
};

export function extractApiErrorMessage(payload: unknown, fallback: string): string {
    if (typeof payload === "string") return payload;
    if (payload && typeof payload === "object") {
        const o = payload as Record<string, unknown>;
        if (typeof o.detail === "string") return o.detail;
        if (typeof o.error === "string") return o.error;
        if (typeof o.message === "string") return o.message;
        for (const v of Object.values(o)) if (Array.isArray(v) && v.length > 0) return String(v[0]);
    }
    return fallback;
}

export default apiClient;
