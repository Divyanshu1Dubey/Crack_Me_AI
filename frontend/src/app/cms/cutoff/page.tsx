import { redirect } from 'next/navigation';

export const metadata: Metadata = {
    title: 'UPSC CMS Cutoff 2026 — Category-Wise Qualifying Marks | CrackCMS',
    description: 'UPSC CMS 2026 cutoff marks by category (General, OBC, SC, ST). Verified from official UPSC sources. Previous year cutoffs (2022-2025) also available.',
    alternates: { canonical: '/cms/cutoff/2026', languages: { 'en-IN': '/cms/cutoff/2026' } },
};

export default function CMSCutoffIndexPage() {
    redirect('/cms/cutoff/2026');
}