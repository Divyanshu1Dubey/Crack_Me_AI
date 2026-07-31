import type { Metadata } from "next";
import { ReactNode } from "react";

export const metadata: Metadata = {
    title: "NEET PG Question Bank — Practice Previous Year Papers | CrackLabs",
    description:
        "Practice 5,000+ NEET PG previous-year questions (2018-2025) with image-based drills, AI explanations, bookmarks, and spaced-repetition flashcards. Filter by year, subject, and topic.",
    keywords: [
        "NEET PG",
        "NEET PG question bank",
        "NEET PG previous year papers",
        "NEET PG PYQ",
        "medical PG preparation",
        "CrackLabs",
    ],
    openGraph: {
        title: "NEET PG Question Bank — CrackLabs",
        description:
            "Practice the full NEET PG previous-year bank with image-based drills, AI explanations, and bookmarks.",
        url: "https://cracklabs.app/questions/neet-pg/practice",
        siteName: "CrackLabs",
        type: "website",
    },
    twitter: {
        card: "summary_large_image",
        title: "NEET PG Question Bank — CrackLabs",
        description:
            "Practice 5,000+ NEET PG PYQs with AI explanations and image-based drills.",
    },
    alternates: {
        canonical: "https://cracklabs.app/questions/neet-pg/practice",
    },
};

export default function NeetPgPracticeLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
