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
 * Auth: JWT tokens auto-attached via interceptor from localStorage.
 */
import axios from 'axios';

const isAppRunningLocally = () => {
  if (typeof window === 'undefined') {
    return process.env.NODE_ENV !== 'production';
  }

  const host = window.location.hostname.toLowerCase();
  return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
};

const USE_API_PROXY = isAppRunningLocally() && (process.env.NEXT_PUBLIC_USE_API_PROXY ?? 'false') === 'true';
const DEFAULT_LOCAL_API_URL = 'http://localhost:8000/api';
const DEFAULT_PRODUCTION_API_URL = 'https://crackcms-vsthc.ondigitalocean.app/api';
const LEGACY_UNHEALTHY_API_HOSTS = ['crackcms-vsthc.ondigitalocean.app'];

const normalizeApiBaseUrl = (url: string) => {
  const normalized = url.replace(/\/+$/, '');
  return normalized.endsWith('/api') ? normalized : `${normalized}/api`;
};

const isLocalhostApiUrl = (url: string) => {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
  } catch {
    return false;
  }
};

const shouldIgnoreConfiguredApiUrl = (url: string) =>
  isLocalhostApiUrl(url) && !isAppRunningLocally();

const isKnownUnhealthyApiHost = (url: string) =>
  LEGACY_UNHEALTHY_API_HOSTS.some((host) => url.includes(host));

const resolveApiBaseUrl = () => {
  if (USE_API_PROXY) {
    return '/api/proxy';
  }

  const configured = (process.env.NEXT_PUBLIC_API_URL || '').trim();
  if (configured) {
    const normalized = normalizeApiBaseUrl(configured);
    if (shouldIgnoreConfiguredApiUrl(normalized)) {
      return DEFAULT_PRODUCTION_API_URL;
    }
    if (isKnownUnhealthyApiHost(normalized)) {
      return DEFAULT_PRODUCTION_API_URL;
    }
    return normalized;
  }

  if (process.env.NODE_ENV === 'production') {
    return DEFAULT_PRODUCTION_API_URL;
  }

  return DEFAULT_LOCAL_API_URL;
};

const API_BASE_URL = resolveApiBaseUrl();
const configuredFallback = normalizeApiBaseUrl((process.env.NEXT_PUBLIC_API_FALLBACK_URL || DEFAULT_PRODUCTION_API_URL).trim());
const FALLBACK_API_BASE_URL = USE_API_PROXY
  ? API_BASE_URL
  : (shouldIgnoreConfiguredApiUrl(configuredFallback) ? DEFAULT_PRODUCTION_API_URL : configuredFallback);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = (error.config || {}) as {
      _retry?: boolean;
      _apiBaseFailover?: boolean;
      baseURL?: string;
      headers?: Record<string, string>;
    };
    const status = error.response?.status as number | undefined;
    const currentBaseUrl = originalRequest.baseURL || API_BASE_URL;

    const shouldFailover =
      !USE_API_PROXY &&
      !originalRequest._apiBaseFailover &&
      currentBaseUrl !== FALLBACK_API_BASE_URL &&
      (status === 502 || status === 503 || status === 504);

    if (shouldFailover) {
      originalRequest._apiBaseFailover = true;
      originalRequest.baseURL = FALLBACK_API_BASE_URL;
      return api(originalRequest);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const refreshBaseUrl = originalRequest.baseURL || API_BASE_URL;
          const { data } = await axios.post(`${refreshBaseUrl}/auth/token/refresh/`, {
            refresh: refreshToken,
          });
          localStorage.setItem('access_token', data.access);
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${data.access}`;
          }
          return api(originalRequest);
        }
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (data: Record<string, string>) => api.post('/auth/register/', data),
  login: (data: { username: string; password: string }) => api.post('/auth/login/', data),
  getProfile: () => api.get('/auth/profile/'),
  updateProfile: (data: Record<string, string>) => api.put('/auth/profile/', data),
  // Password reset
  requestPasswordReset: (data: { email: string }) => api.post('/auth/password-reset/', data),
  confirmPasswordReset: (data: { uid: string; token: string; new_password: string }) =>
    api.post('/auth/password-reset/confirm/', data),
  // Token system
  getTokenBalance: () => api.get('/auth/tokens/'),
  purchaseTokens: (data: { amount: number; payment_id?: string }) => api.post('/auth/tokens/purchase/', data),
  getTokenHistory: () => api.get('/auth/tokens/history/'),
  // Admin token management
  adminGetAllUsers: () => api.get('/auth/tokens/admin/users/'),
  adminGrantTokens: (data: { user_id: number; amount: number; note?: string }) => api.post('/auth/tokens/admin/grant/', data),
  adminTransferTokens: (data: { from_user_id?: number; to_user_id: number; amount: number; note?: string }) => api.post('/auth/tokens/admin/transfer/', data),
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

// Questions API
export const questionsAPI = {
  list: (params?: Record<string, string | number>) => api.get('/questions/', { params }),
  get: (id: number) => api.get(`/questions/${id}/`),
  getSimilar: (id: number) => api.get(`/questions/${id}/similar/`),
  getSubjects: () => api.get('/questions/subjects/'),
  getTopics: (params?: Record<string, string | number>) => api.get('/questions/topics/', { params }),
  getYears: () => api.get('/questions/years/'),
  getStats: () => api.get('/questions/stats/'),
  bookmark: (id: number) => api.post(`/questions/${id}/bookmark/`),
  getBookmarks: () => api.get('/questions/bookmarks/'),
  upload: (data: Record<string, unknown>[]) => api.post('/questions/upload/', data),
  submitFeedback: (data: { question: number; category: string; comment: string }) =>
    api.post('/questions/feedback/', data),
  getFeedback: (params?: Record<string, string>) => api.get('/questions/feedback/', { params }),
  resolveFeedback: (id: number) => api.patch(`/questions/feedback/${id}/resolve/`),
};

// Tests API
export const testsAPI = {
  list: (params?: Record<string, string>) => api.get('/tests/', { params }),
  get: (id: number) => api.get(`/tests/${id}/`),
  generate: (data: Record<string, string | number>) => api.post('/tests/generate/', data),
  start: (id: number) => api.post(`/tests/${id}/start/`),
  submit: (id: number, data: Record<string, unknown>) => api.post(`/tests/${id}/submit/`, data),
  review: (id: number, attemptId: number) => api.get(`/tests/${id}/review/`, { params: { attempt_id: attemptId } }),
  generateAdaptive: (data: { num_questions?: number }) => api.post('/tests/generate-adaptive/', data),
  pyqSimulation: (data: { year: number; paper?: number }) => api.post('/tests/pyq-simulation/', data),
  getAttempts: () => api.get('/tests/attempts/'),
  getAttempt: (id: number) => api.get(`/tests/attempts/${id}/`),
};

// Analytics API
export const analyticsAPI = {
  getDashboard: () => api.get('/analytics/dashboard/'),
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
  exportData: (type?: string) => api.get('/analytics/export/', { params: { type: type || 'all' } }),
  exportCSV: (type: string) => api.get('/analytics/export/csv/', { params: { type }, responseType: 'blob' }),
  // Announcements
  getAnnouncements: () => api.get('/analytics/announcements/'),
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
};


// AI API — 120s timeout for AI calls (backend cold starts + LLM latency)
const AI_TIMEOUT = 120000;

export const aiAPI = {
  askTutor: (data: { question: string; context?: string }) => api.post('/ai/tutor/', data, { timeout: AI_TIMEOUT }),
  generateMnemonic: (data: { topic: string; concept?: string }) => api.post('/ai/mnemonic/', data, { timeout: AI_TIMEOUT }),
  explain: (data: { concept: string; level?: string }) => api.post('/ai/explain/', data, { timeout: AI_TIMEOUT }),
  analyzeQuestion: (data: Record<string, string>) => api.post('/ai/analyze/', data, { timeout: AI_TIMEOUT }),
  explainAfterAnswer: (data: {
    question_text: string;
    options?: Record<string, string>;
    correct_answer?: string;
    selected_answer?: string;
    subject?: string;
    topic?: string;
  }) => api.post('/ai/explain-answer/', data, { timeout: AI_TIMEOUT }),
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
    return api.post('/ai/knowledge/upload/', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
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

// Textbooks API
export const textbooksAPI = {
  list: (params?: Record<string, string | number>) => api.get('/textbooks/books/', { params }),
  get: (id: number) => api.get(`/textbooks/books/${id}/`),
  getChapters: (bookId: number) => api.get(`/textbooks/books/${bookId}/`, { params: { expand: 'chapters' } }),
  upload: (data: FormData) => api.post('/textbooks/uploads/', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  getUploads: () => api.get('/textbooks/uploads/'),
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

// Notes API
export const notesAPI = {
  list: (params?: { question?: number; topic?: number }) => api.get('/questions/notes/', { params }),
  create: (data: { question?: number; topic?: number; title?: string; content: string }) => api.post('/questions/notes/', data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/questions/notes/${id}/`, data),
  delete: (id: number) => api.delete(`/questions/notes/${id}/`),
};

// Flashcards API
export const flashcardsAPI = {
  list: (params?: { subject?: number; due?: string }) => api.get('/questions/flashcards/', { params }),
  create: (data: { question?: number; subject?: number; front: string; back: string; difficulty?: string }) =>
    api.post('/questions/flashcards/', data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/questions/flashcards/${id}/`, data),
  delete: (id: number) => api.delete(`/questions/flashcards/${id}/`),
  review: (id: number, quality: number) => api.post(`/questions/flashcards/${id}/review/`, { quality }),
  analytics: () => api.get('/questions/flashcards/analytics/'),
};

export default api;
