/**
 * appShellRoutes — pure route helpers for the global app shell
 * (Header title, FloatingDock visibility, ExamSwitcher labels).
 *
 * Kept free of React and Next imports so tests/unit can load it directly
 * with `node --test` (see tests/unit/app-shell-routes.test.ts).
 */

/** Header title per route. A key also covers its sub-paths unless a longer key matches. */
export const PAGE_TITLES: Readonly<Record<string, string>> = {
  '/dashboard': 'Dashboard',
  '/questions': 'Question Bank',
  '/questions/neet-pg': 'NEET PG Question Bank',
  '/questions/inicet': 'INI-CET Question Bank',
  '/tests': 'Tests',
  '/ai-tutor': 'AI Tutor',
  '/simulator': 'CMS Simulator',
  '/generate': 'Question Generator',
  '/roadmap': 'Study Roadmap',
  '/resources': 'CMS Study Hub',
  '/textbooks': 'Textbooks',
  '/trends': 'Exam Trends',
  '/upload': 'Upload & Train',
  '/analytics': 'Analytics',
  '/analytics/dashboard_v3': 'Analytics Dashboard',
  '/analytics/heatmap': 'Study Heatmap',
  '/bookmarks': 'Bookmarks',
  '/feedback': 'Feedback',
  '/tokens': 'AI Tokens',
  '/settings': 'Settings',
  '/leaderboard': 'Leaderboard',
  '/flashcards': 'Flashcards',
  '/mistake-notebook': 'Mistake Notebook',
  '/study-time': 'Study Time',
  '/quests': 'Daily Quests',
  '/practice': 'Practice',
  '/topic-notes': 'Topic Notes',
  '/recall/search': 'Recall Search',
  // The page heading is "Premium Membership Hub" (the nav item says Subscription).
  '/subscription': 'Premium Membership',
  '/contact': 'Contact Us',
  '/jobs': 'Jobs Portal',
  '/admin': 'Admin Panel',
  '/admin/analytics-dashboard': 'Analytics Dashboard',
  '/admin/questions-editor': 'Questions Editor',
  '/admin/review-queue': 'Answer-Key Review',
  '/admin/announcements': 'Announcements',
  '/admin/jobs': 'Manage Jobs',
  '/admin/notes': 'Topic Notes',
  '/admin/recall': 'Recall Admin',
  '/admin/import-center': 'Import Center',
  '/admin/ingestion': 'Ingestion',
};

export const DEFAULT_PAGE_TITLE = 'CrackCMS';

// Longest key first, so '/questions/neet-pg' wins over '/questions'.
const TITLE_KEYS = Object.keys(PAGE_TITLES).sort((a, b) => b.length - a.length);

function matchesSection(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** Title shown in the Header's "Workspace" block for a route. */
export function getPageTitle(pathname: string | null | undefined): string {
  if (!pathname) return DEFAULT_PAGE_TITLE;
  // A single test attempt (/tests/<id>) reads better as "Test" than "Tests".
  if (pathname.startsWith('/tests/')) return 'Test';
  const key = TITLE_KEYS.find((k) => matchesSection(pathname, k));
  return key ? PAGE_TITLES[key] : DEFAULT_PAGE_TITLE;
}

/**
 * Routes where the global FloatingDock (Ask AI + Create flashcard buttons)
 * must not render:
 *   - /admin/**   admin tools: the student dock has no use there and its
 *                 fixed buttons covered table columns and primary CTAs;
 *   - /ai-tutor   the page is itself the AI chat, and the dock sat on top of
 *                 the composer's Send button;
 *   - /tests/<id> the timed test player: the dock covered "Submit Test" and
 *                 answer options, and an AI chat has no place in a mock exam.
 *                 (The /tests list keeps the dock.)
 */
export function isFloatingDockHiddenRoute(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  if (matchesSection(pathname, '/admin')) return true;
  if (matchesSection(pathname, '/ai-tutor')) return true;
  return /^\/tests\/[^/]+/.test(pathname);
}

export type ExamTrack = 'cms' | 'neet_pg' | 'ini_cet' | 'usmle' | 'fmge';

/** Full option labels (the dropdown list). */
export const EXAM_LABELS: Readonly<Record<ExamTrack, string>> = {
  cms: 'UPSC CMS',
  neet_pg: 'NEET PG',
  ini_cet: 'INI-CET',
  usmle: 'USMLE',
  fmge: 'FMGE',
};

/** Codes for the narrow (phone) header trigger, where the full label does not fit. */
export const EXAM_CODES: Readonly<Record<ExamTrack, string>> = {
  cms: 'CMS',
  neet_pg: 'NEET',
  ini_cet: 'INI',
  usmle: 'USMLE',
  fmge: 'FMGE',
};

export function isExamTrack(value: unknown): value is ExamTrack {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(EXAM_LABELS, value);
}

/**
 * Exam implied by the current route. The NEET PG and INI-CET banks are
 * dedicated players, so the header switcher must show that exam there even
 * when the saved preference says UPSC CMS. Other routes return null.
 */
export function examFromPathname(pathname: string | null | undefined): ExamTrack | null {
  if (!pathname) return null;
  if (matchesSection(pathname, '/questions/neet-pg')) return 'neet_pg';
  if (matchesSection(pathname, '/questions/inicet')) return 'ini_cet';
  return null;
}
