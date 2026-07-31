import type { Metadata } from "next";
import { ReactNode } from "react";

export const metadata: Metadata = {
    title: "INI-CET Question Bank — Practice Previous Year Papers | CrackLabs",
    description:
        "Practice 2,500+ INI-CET previous-year questions (2018-2025) with image-based drills, AI explanations, bookmarks, and spaced-repetition flashcards. Filter by institute, year, subject.",
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
            "Practice the full INI-CET previous-year bank with image-based drills and AI explanations.",
        url: "https://cracklabs.app/questions/inicet/practice",
        siteName: "CrackLabs",
        type: "website",
    },
    twitter: {
        card: "summary_large_image",
        title: "INI-CET Question Bank — CrackLabs",
        description:
            "Practice 2,500+ INI-CET PYQs with AI explanations and image-based drills.",
    },
    alternates: {
        canonical: "https://cracklabs.app/questions/inicet/practice",
    },
};

export default function IniCetPracticeLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
