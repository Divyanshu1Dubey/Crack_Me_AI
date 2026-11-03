/**
 * /exams/cms — UPSC CMS microsite.
 * Renders the shared ExamMicrosite shell with the CMS theme + content.
 */
import type { Metadata } from 'next';
import { ExamMicrosite } from '@/components/exams/ExamMicrosite';
import { EXAM_CONFIGS } from '@/app/exams/_data';
import { CMS_PYQ_COUNT, CMS_PYQ_YEAR_COUNT, CMS_PYQ_YEARS } from '@/lib/bankStats';

export const metadata: Metadata = {
  title: `UPSC CMS — Crack PYQs ${CMS_PYQ_YEARS}`,
  description:
    `Crack the UPSC Combined Medical Services exam with ${CMS_PYQ_COUNT} PYQs from ${CMS_PYQ_YEARS}, full mock tests, and an AI tutor trained on Harrison, Bailey & Love and Park.`,
  // Same exam as /cms (the maintained landing page): point search engines there.
  alternates: { canonical: '/cms' },
  openGraph: {
    title: 'UPSC CMS Preparation | CrackCMS',
    description: `${CMS_PYQ_COUNT} UPSC CMS PYQs · ${CMS_PYQ_YEAR_COUNT} years of coverage · AI tutor · Full mocks.`,
    url: 'https://www.cracklabs.app/exams/cms',
    siteName: 'CrackCMS',
    type: 'website',
  },
};

export default function CmsMicrositePage() {
  return <ExamMicrosite cfg={EXAM_CONFIGS.cms} />;
}