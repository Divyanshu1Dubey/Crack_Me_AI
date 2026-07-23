/**
 * /neet-pg — NEET PG microsite (full custom landing experience).
 *
 * Standalone design — completely independent of the shared /exams/[slug]
 * microsite. Pulls LIVE subject/year counts from /api/questions/ and
 * /api/questions/subjects/ so the page always reflects the real QBank.
 *
 * Design language
 *   - Medical emerald/teal palette (distinct from CMS blue / USMLE indigo).
 *   - Cinematic full-bleed hero with animated ECG-style grid overlay.
 *   - Live data cards (subject grid, year tiles) loaded client-side.
 *   - Image-rich: each subject card shows its subject icon + question count.
 *   - Year tiles route into the dedicated NEET PG player.
 *
 * Routes wired
 *   - /questions/neet-pg/practice?year=<YYYY>   — full-paper NEET PG practice
 *   - /questions/neet-pg/practice?subject=<id>  — subject-filtered practice
 *   - /ai-tutor                                  — AI tutor
 *   - /analytics/dashboard_v3                    — analytics
 */
import type { Metadata } from 'next';
import NeetPgLanding from '@/components/neet-pg/NeetPgLanding';

export const metadata: Metadata = {
  title: 'NEET PG 2026 — 2,300+ PYQs · 19 Subjects · AI Tutor | CrackCMS',
  description:
    'India\'s dedicated NEET PG preparation platform — 2,300+ previous year MCQs from 2018-2025 across 19 PG subjects, image-rich recall questions, AI tutor trained on Harrison, Robbins, Bailey & Love, and full mock tests.',
  keywords: [
    'NEET PG 2026',
    'NEET PG preparation',
    'NEET PG PYQ',
    'NEET PG mock test',
    'NEET PG subjects',
    'NEET PG AI tutor',
    'NBE NEET PG',
    'MD MS entrance exam',
  ],
  alternates: { canonical: 'https://www.cracklabs.app/neet-pg' },
  openGraph: {
    title: 'NEET PG 2026 Preparation | CrackCMS',
    description:
      '2,300+ NEET PG PYQs · 19 PG subjects · Image-rich recalls · AI tutor · Full mocks.',
    url: 'https://www.cracklabs.app/neet-pg',
    siteName: 'CrackCMS',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'NEET PG 2026 Preparation | CrackCMS',
    description:
      '2,300+ NEET PG PYQs across 19 subjects with AI tutor & mock tests.',
  },
};

export default function NeetPgPage() {
  return <NeetPgLanding />;
}