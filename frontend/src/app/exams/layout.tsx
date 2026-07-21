import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Medical Exams — UPSC CMS, NEET PG, INI-CET, FMGE, USMLE | CrackCMS',
    description:
        'Compare every medical entrance exam — UPSC CMS, NEET PG, INI-CET, FMGE, USMLE and Medical Officer recruitment. Pick the exam track that fits your career goal.',
    alternates: { canonical: '/exams', languages: { 'en-IN': '/exams' } },
    openGraph: {
        type: 'website',
        url: '/exams',
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
