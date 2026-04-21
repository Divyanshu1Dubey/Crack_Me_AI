export const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.cracklabs.app";

export const siteName = "CrackCMS";
export const siteTitle = "CrackCMS | UPSC CMS & NEET PG Preparation Platform";
export const siteDescription =
  "CrackCMS is a doctor-first exam prep platform for UPSC CMS (Combined Medical Services) and NEET PG with PYQs, AI tutoring, mock tests, analytics, and high-yield revision workflows.";

export const seoKeywords = [
  "UPSC CMS",
  "Combined Medical Services exam",
  "UPSC CMS preparation",
  "UPSC CMS PYQ",
  "UPSC CMS mock test",
  "NEET PG preparation",
  "NEET PG question bank",
  "medical entrance exam preparation",
  "doctor exam preparation platform",
  "CrackCMS",
];

export const publicIndexableRoutes = [
  "/",
  "/resources",
] as const;

export const privateNoIndexPrefixes = [
  "/admin",
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
];
