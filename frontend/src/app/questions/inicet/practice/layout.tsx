import type { Metadata } from "next";
import type { ReactNode } from "react";
import { INI_CET_QUESTION_COUNT } from "@/lib/bankStats";

// The bank is a set of exam recalls (mostly 2025), sized in lib/bankStats;
// the page filters by year and subject (no institute filter).
export const metadata: Metadata = {
    title: "INI-CET Question Bank — Practice Previous Year Papers | CrackLabs",
    description:
        `Practice INI-CET recall questions (${INI_CET_QUESTION_COUNT} in the bank) with AI explanations, bookmarks, and spaced-repetition flashcards. Filter by year and subject.`,
    keywords: [
        "INI-CET",
        "INI-CET question bank",
        "INI-CET previous year papers",
        "INI-CET PYQ",
        "AIIMS PG preparation",
        "CrackLabs",
    ],
    openGraph: {
        title: "INI-CET Question Bank — CrackLabs",
        description:
            "Practice the INI-CET recall bank with AI explanations and bookmarks.",
        url: "https://cracklabs.app/questions/inicet/practice",
        siteName: "CrackLabs",
        type: "website",
    },
    twitter: {
        card: "summary_large_image",
        title: "INI-CET Question Bank — CrackLabs",
        description:
            `Practice ${INI_CET_QUESTION_COUNT} INI-CET recall questions with AI explanations.`,
    },
    alternates: {
        canonical: "https://cracklabs.app/questions/inicet/practice",
    },
};

export default function IniCetPracticeLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
