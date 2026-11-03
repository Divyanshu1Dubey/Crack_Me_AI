import type { Metadata } from "next";
import type { ReactNode } from "react";
import { NEET_PG_QUESTION_COUNT } from "@/lib/bankStats";

// The bank is mostly exam recalls, sized in lib/bankStats (the site-wide
// figure), not a 2018-2025 previous-year set.
export const metadata: Metadata = {
    title: "NEET PG Question Bank — Practice Previous Year Papers | CrackLabs",
    description:
        `Practice ${NEET_PG_QUESTION_COUNT} NEET PG questions (mostly exam recalls) with AI explanations, bookmarks, and spaced-repetition flashcards. Filter by year, subject, and topic.`,
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
            "Practice the NEET PG question bank with image-based drills, AI explanations, and bookmarks.",
        url: "https://cracklabs.app/questions/neet-pg/practice",
        siteName: "CrackLabs",
        type: "website",
    },
    twitter: {
        card: "summary_large_image",
        title: "NEET PG Question Bank — CrackLabs",
        description:
            `Practice ${NEET_PG_QUESTION_COUNT} NEET PG questions with AI explanations.`,
    },
    alternates: {
        canonical: "https://cracklabs.app/questions/neet-pg/practice",
    },
};

export default function NeetPgPracticeLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
