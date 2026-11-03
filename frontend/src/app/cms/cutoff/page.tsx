import { redirect } from 'next/navigation';
import type { Metadata } from 'next';
import { CMS_CUTOFFS, getAllCmsCutoffYears } from '@/lib/cutoffData';

// Latest year that actually has cutoff figures (the newest cycle can be
// listed before UPSC publishes its cutoff; sending /cms/cutoff there showed
// an empty page).
const latestYearWithData =
    getAllCmsCutoffYears().find((year) => (CMS_CUTOFFS[year]?.cutoffs ?? []).length > 0) ??
    getAllCmsCutoffYears()[0];

export const metadata: Metadata = {
    title: `UPSC CMS Cutoff ${latestYearWithData} — Category-Wise Qualifying Marks`,
    description: 'UPSC CMS cutoff marks by category (General, OBC, SC, ST) with approximate ranges from publicly available UPSC notices for recent years.',
    alternates: { canonical: `/cms/cutoff/${latestYearWithData}`, languages: { 'en-IN': `/cms/cutoff/${latestYearWithData}` } },
};

export default function CMSCutoffIndexPage() {
    redirect(`/cms/cutoff/${latestYearWithData}`);
}
