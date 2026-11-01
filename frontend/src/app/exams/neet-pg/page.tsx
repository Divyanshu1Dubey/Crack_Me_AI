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
import { NEET_PG_QUESTION_COUNT } from '@/lib/bankStats';

export const metadata: Metadata = {
  title: 'NEET PG — Recall PYQs, Mocks & AI Tutor',
  description:
    `Crack NEET PG with ${NEET_PG_QUESTION_COUNT} questions (mostly exam recalls), 19 PG subjects mapped to high-yield topics, full mocks and an AI tutor. Standalone NEET PG microsite.`,
  // Same exam as /neet-pg: point search engines at the main landing page.
  alternates: { canonical: '/neet-pg' },
  openGraph: {
    title: 'NEET PG Preparation | CrackCMS',
    description:
      `${NEET_PG_QUESTION_COUNT} NEET PG questions · 19 PG subjects · High-yield topic maps · AI tutor.`,
    url: 'https://www.cracklabs.app/exams/neet-pg',
    siteName: 'CrackCMS',
    type: 'website',
  },
};

export default function NeetPgMicrositePage() {
  return <ExamMicrosite cfg={EXAM_CONFIGS['neet-pg']} />;
}