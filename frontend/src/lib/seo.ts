import { CMS_PYQ_PHRASE } from "./bankStats";

export const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.cracklabs.app";

// Note: buildCanonical() lives in lib/metadata.ts (more comprehensive — strips
// multi-slash, normalises, returns `${siteUrl}/path`). Re-export here for
// legacy callers that import from seo.ts.
export { buildCanonical } from './metadata';

export const siteName = "CrackCMS";
export const brandName = "CrackLabs AI";
export const siteTitle =
  "CrackCMS - UPSC CMS Preparation App with AI Tutor, PYQs and Mock Tests";
export const siteDescription =
  `Prepare for UPSC CMS and medical PG exams with CrackCMS by CrackLabs AI. Practice ${CMS_PYQ_PHRASE}, AI-explained MCQs, mock tests, and full exam simulations.`;

/** 1200x630 social card generated from the logo (scripts/generate-brand-icons.mjs). */
export const defaultOgImage = "/brand/og-image.png";
export const defaultOgImageSize = { width: 1200, height: 630 } as const;

export const seoKeywords = [
  "UPSC CMS preparation",
  "UPSC CMS online coaching",
  "UPSC CMS app",
  "UPSC CMS question bank",
  "UPSC CMS previous year questions",
  "UPSC CMS PYQ",
  "UPSC CMS mock test",
  "UPSC CMS test series",
  "UPSC CMS syllabus",
  "UPSC CMS study material",
  "UPSC CMS medicine questions",
  "UPSC CMS surgery questions",
  "UPSC CMS pediatrics questions",
  "UPSC CMS OBG questions",
  "UPSC CMS PSM questions",
  "Combined Medical Services exam",
  "CMS exam preparation",
  "medical officer exam preparation",
  "medical MCQ practice",
  "clinical MCQ practice",
  "AI medical tutor",
  "AI medical exam preparation",
  "AI explanations for medical MCQs",
  "medical flashcards",
  "spaced repetition medical",
  "NEET PG question bank",
  "NEET PG mock test",
  "NEET PG PYQ",
  "medical PG entrance exam",
  "CrackCMS",
  "CrackLabs AI",
  "cracklabs app",
];

export const pageMetadata: Record<string, { title: string; description: string }> = {
  "/": {
    title: siteTitle,
    description: siteDescription,
  },
  "/login": {
    title: "Login to CrackCMS",
    description: "Sign in to continue UPSC CMS PYQs, mock tests, AI tutor sessions and medical revision on CrackCMS.",
  },
  "/register": {
    title: "Create Free CrackCMS Account",
    description: "Start UPSC CMS preparation with PYQs, AI explanations, mock tests, flashcards and performance analytics.",
  },
  "/subscription": {
    title: "CrackCMS Premium Plans for UPSC CMS Preparation",
    description: "Compare CrackCMS premium plans (1 month, 3 months, 1 year) for UPSC CMS preparation: AI tutor credits (unlimited on the yearly plan), exam-style mock tests, analytics and high-yield study tools.",
  },
  "/resources": {
    title: "UPSC CMS Resources, Syllabus, Booklist and Exam Guide",
    description: "Explore UPSC CMS syllabus guidance, book recommendations, FAQs, preparation strategy and high-yield resources for medical graduates.",
  },
  "/contact": {
    title: "Contact CrackCMS Support",
    description: "Contact CrackCMS for UPSC CMS preparation support, subscription help, feedback and platform assistance.",
  },
};

export const publicIndexableRoutes = [
  "/",
  "/register",
  "/resources",
  "/contact",
] as const;

/**
 * Login-only (or otherwise private) route prefixes. robots.ts disallows each
 * one, so keep them WITHOUT a trailing slash: "Disallow: /dashboard/" would
 * not match the real URL "/dashboard". "/auth/" keeps its slash so it does
 * not also block unrelated paths that merely start with "auth".
 */
export const privateNoIndexPrefixes = [
  "/admin",
  "/api",
  "/dashboard",
  "/questions",
  "/tests",
  "/analytics",
  "/settings",
  "/tokens",
  "/feedback",
  "/bookmarks",
  "/flashcards",
  "/generate",
  "/ai-tutor",
  "/roadmap",
  "/leaderboard",
  "/simulator",
  "/textbooks",
  "/upload",
  "/trends",
  "/practice",
  "/quests",
  "/mistake-notebook",
  "/study-time",
  "/topic-notes",
  "/recall",
  "/jobs",
  "/auth/",
  "/reset-password",
  "/forgot-password",
];

export type QuestionBankExam = "cms" | "neet-pg" | "ini-cet" | "fmge" | "usmle";

/**
 * Links from public pages into the (login-only) question bank, using the
 * parameters the bank routes actually read:
 *   /questions?exam=<slug>                       exam bank (lowercase slug)
 *   /questions/practice?exam=<slug>&year=<yyyy>  year-wise practice
 *   /questions/neet-pg/practice?year=<yyyy>      NEET PG bank by year
 *   /questions/inicet/practice?year=<yyyy>       INI-CET bank by year
 * `subject` is passed as ?subject=<slug> on the exam bank link.
 */
export function questionBankHref(
  exam: QuestionBankExam,
  opts: { year?: number | string; subject?: string } = {},
): string {
  const year = opts.year != null && String(opts.year).trim() !== "" ? encodeURIComponent(String(opts.year)) : "";
  if (year) {
    if (exam === "neet-pg") return `/questions/neet-pg/practice?year=${year}`;
    if (exam === "ini-cet") return `/questions/inicet/practice?year=${year}`;
    return `/questions/practice?exam=${exam}&year=${year}`;
  }
  const subject = opts.subject ? `&subject=${encodeURIComponent(opts.subject)}` : "";
  return `/questions?exam=${exam}${subject}`;
}
