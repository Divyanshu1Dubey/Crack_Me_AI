import type { Metadata } from 'next';

// Defaults for the /exams/* microsites. No canonical here: /exams itself has
// no page, and a layout canonical is inherited by every child that does not
// set its own.
export const metadata: Metadata = {
    title: 'Medical Exams — UPSC CMS, NEET PG, INI-CET, FMGE, USMLE',
    description:
        'Compare every medical entrance exam — UPSC CMS, NEET PG, INI-CET, FMGE, USMLE and Medical Officer recruitment. Pick the exam track that fits your career goal.',
    openGraph: {
        type: 'website',
        title: 'Medical Exams — UPSC CMS, NEET PG, INI-CET, FMGE, USMLE | CrackCMS',
        description:
            'Compare every medical entrance exam — UPSC CMS, NEET PG, INI-CET, FMGE, USMLE and Medical Officer recruitment.',
        siteName: 'CrackCMS',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Medical Exams — UPSC CMS, NEET PG, INI-CET, FMGE, USMLE | CrackCMS',
        description: 'Compare every major medical entrance exam and pick the right track.',
    },
    robots: { index: true, follow: true },
};

export default function ExamsLayout({ children }: { children: React.ReactNode }) {
    return children;
}
