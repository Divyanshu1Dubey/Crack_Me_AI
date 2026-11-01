/**
 * /exams/usmle — USMLE microsite (Beta / waitlist).
 */
import type { Metadata } from 'next';
import { ExamMicrosite } from '@/components/exams/ExamMicrosite';
import { EXAM_CONFIGS } from '@/app/exams/_data';

export const metadata: Metadata = {
  title: 'USMLE — Coming Soon',
  description:
    'USMLE Step 1 and Step 2 CK QBank from CrackCMS — high-yield lists, NBME-style vignettes, biostatistics. Join the waitlist.',
  // Same exam as /usmle: point search engines at the main landing page.
  alternates: { canonical: '/usmle' },
  openGraph: {
    title: 'USMLE Preparation | CrackCMS (Beta)',
    description: 'USMLE QBank coming soon — Step 1, Step 2 CK.',
    url: 'https://www.cracklabs.app/exams/usmle',
    siteName: 'CrackCMS',
    type: 'website',
  },
};

export default function UsmleMicrositePage() {
  return <ExamMicrosite cfg={EXAM_CONFIGS.usmle} />;
}