export const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.cracklabs.app";

export const siteName = "CrackCMS";
export const brandName = "CrackLabs AI";
export const siteTitle =
  "CrackCMS - UPSC CMS Preparation App with AI Tutor, PYQs and Mock Tests";
export const siteDescription =
  "Prepare for UPSC CMS and medical PG exams with CrackCMS by CrackLabs AI. Practice PYQs, topic-wise MCQs, mock tests, AI explanations, flashcards, textbooks, analytics and exam strategy in one medical preparation platform.";

export const defaultOgImage = "/cms-circle-logo.png";

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
    description: "Unlock premium UPSC CMS preparation with unlimited AI tutor support, exam-style mock tests, analytics and high-yield study tools.",
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
  "/subscription",
  "/resources",
  "/contact",
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
  "/auth",
  "/reset-password",
  "/forgot-password",
];
