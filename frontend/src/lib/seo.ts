export const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.cracklabs.app";

export const siteName = "CrackCMS";
export const siteTitle = "CrackCMS — #1 UPSC CMS & NEET PG Preparation Platform | PYQs, AI Tutor, Mock Tests";
export const siteDescription =
  "India's top-rated UPSC CMS & NEET PG preparation platform. 10,000+ Previous Year Questions (PYQs), AI-powered explanations, expert-curated mock tests, topic-wise practice, spaced repetition flashcards, and real-time analytics. Trusted by 5,000+ medical graduates. Start free today.";

export const seoKeywords = [
  // Core exam keywords — high search volume
  "UPSC CMS",
  "UPSC CMS preparation",
  "UPSC CMS 2025",
  "UPSC CMS 2026",
  "Combined Medical Services exam",
  "CMS exam preparation",
  "UPSC CMS syllabus",
  "UPSC CMS previous year papers",
  "UPSC CMS PYQ",
  "UPSC CMS mock test",
  "UPSC CMS online test series",
  "UPSC CMS question bank",
  "UPSC CMS study material",
  "UPSC CMS free mock test",
  "UPSC CMS preparation online",
  // NEET PG keywords
  "NEET PG",
  "NEET PG preparation",
  "NEET PG 2025",
  "NEET PG 2026",
  "NEET PG question bank",
  "NEET PG previous year questions",
  "NEET PG PYQ",
  "NEET PG mock test",
  "NEET PG online test series",
  "NEET PG study material",
  // Feature keywords
  "AI medical exam tutor",
  "AI-powered medical question solving",
  "medical entrance exam preparation",
  "doctor exam preparation platform",
  "medical PG entrance exam",
  "FMGE preparation",
  "medical MCQ practice",
  "clinical MCQ practice",
  "spaced repetition medical",
  "medical flashcards",
  "topic wise medical practice",
  "subject wise question bank medical",
  // Brand
  "CrackCMS",
  "CrackLabs",
  "cracklabs.app",
];

// SEO-optimized page metadata for each route
export const pageMetadata: Record<string, { title: string; description: string }> = {
  "/": {
    title: "CrackCMS — #1 UPSC CMS & NEET PG Preparation Platform",
    description: "India's most trusted UPSC CMS & NEET PG preparation platform. 10,000+ PYQs with AI explanations, mock tests, topic-wise practice, flashcards & analytics. Start free.",
  },
  "/login": {
    title: "Login to CrackCMS",
    description: "Sign in to your CrackCMS account and continue your UPSC CMS & NEET PG preparation journey.",
  },
  "/register": {
    title: "Create Free Account — CrackCMS",
    description: "Join 5,000+ medical graduates on CrackCMS. Free access to UPSC CMS & NEET PG PYQs, AI tutor, and mock tests. Sign up in 30 seconds.",
  },
  "/subscription": {
    title: "Premium Plans — CrackCMS",
    description: "Unlock unlimited UPSC CMS & NEET PG preparation with CrackCMS Premium. AI explanations, full mock tests, analytics dashboard. Plans from ₹79/month.",
  },
  "/resources": {
    title: "Free UPSC CMS & NEET PG Study Resources",
    description: "Free study resources for UPSC CMS & NEET PG — syllabus guides, subject-wise strategies, high-yield topics, recommended textbooks, and preparation roadmaps.",
  },
};

// Routes that Google should index — these generate sitemap entries
export const publicIndexableRoutes = [
  "/",
  "/login",
  "/register",
  "/subscription",
  "/resources",
  "/forgot-password",
] as const;

// Routes that are behind auth — excluded from sitemap, marked noindex in robots
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
