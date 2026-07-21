/**
 * /exams/neet-pg — NEET PG microsite (NEW standalone design on the same
 * subdomain, per the user's spec).
 *
 * Uses the same ExamMicrosite shell as CMS/USMLE but with the NEET PG theme
 * (emerald/teal), 19 PG subjects, and 5 years of NEET PG PYQs (2020-2025).
 */
import type { Metadata } from 'next';
import { ExamMicrosite } from '@/components/exams/ExamMicrosite';
import { EXAM_CONFIGS } from '@/app/exams/_data';

export const metadata: Metadata = {
  title: 'NEET PG — Crack PYQs 2020-2025 | CrackCMS',
  description:
    'Crack NEET PG with 1,200+ PYQs from 2020-2025, 19 PG subjects mapped to high-yield topics, full mocks and an AI tutor. Standalone NEET PG microsite.',
  alternates: { canonical: 'https://www.cracklabs.app/exams/neet-pg' },
  openGraph: {
    title: 'NEET PG Preparation | CrackCMS',
    description:
      '1,200+ NEET PG PYQs · 19 PG subjects · High-yield topic maps · AI tutor.',
    url: 'https://www.cracklabs.app/exams/neet-pg',
    siteName: 'CrackCMS',
    type: 'website',
  },
};

export default function NeetPgMicrositePage() {
  return <ExamMicrosite cfg={EXAM_CONFIGS['neet-pg']} />;
}