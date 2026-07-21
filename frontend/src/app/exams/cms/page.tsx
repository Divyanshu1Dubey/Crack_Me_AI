/**
 * /exams/cms — UPSC CMS microsite.
 * Renders the shared ExamMicrosite shell with the CMS theme + content.
 */
import type { Metadata } from 'next';
import { ExamMicrosite } from '@/components/exams/ExamMicrosite';
import { EXAM_CONFIGS } from '@/app/exams/_data';

export const metadata: Metadata = {
  title: 'UPSC CMS — Crack PYQs 2018-2025 | CrackCMS',
  description:
    'Crack the UPSC Combined Medical Services exam with 2,000+ PYQs from 2018-2025, full mock tests, and an AI tutor trained on Harrison, Bailey & Love and Park.',
  alternates: { canonical: 'https://www.cracklabs.app/exams/cms' },
  openGraph: {
    title: 'UPSC CMS Preparation | CrackCMS',
    description: '2,000+ UPSC CMS PYQs · 8 years of coverage · AI tutor · Full mocks.',
    url: 'https://www.cracklabs.app/exams/cms',
    siteName: 'CrackCMS',
    type: 'website',
  },
};

export default function CmsMicrositePage() {
  return <ExamMicrosite cfg={EXAM_CONFIGS.cms} />;
}