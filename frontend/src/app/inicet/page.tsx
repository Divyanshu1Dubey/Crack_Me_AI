/**
 * /inicet — INI-CET microsite (full custom landing experience).
 *
 * Sister of /neet-pg — sister visual language (indigo/sky instead of
 * emerald/teal). Pulls LIVE subject/year counts from the API.
 */
import type { Metadata } from 'next';
import IniCetLanding from '@/components/inicet-pg/IniCetLanding';

export const metadata: Metadata = {
  title: 'INI-CET 2026 — AIIMS-Standard Recalls · AI Tutor | CrackCMS',
  description:
    'India\'s dedicated INI-CET (AIIMS / PGIMER / JIPMER / NIMHANS / SCTIMST) preparation platform — image-rich subject recalls, AI tutor, and full mock tests.',
  keywords: [
    'INI-CET 2026',
    'AIIMS PG',
    'INI-CET preparation',
    'AIIMS PG PYQ',
    'PGIMER',
    'JIPMER PG',
    'NIMHANS PG',
  ],
  alternates: { canonical: 'https://www.cracklabs.app/inicet' },
  openGraph: {
    title: 'INI-CET 2026 Preparation | CrackCMS',
    description:
      'AIIMS-grade INI-CET platform · Image-heavy recalls · 19 subjects · AI tutor.',
    url: 'https://www.cracklabs.app/inicet',
    siteName: 'CrackCMS',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'INI-CET 2026 Preparation | CrackCMS',
    description:
      'AIIMS-grade INI-CET platform with image-heavy recalls and AI tutor.',
  },
};

export default function IniCetPage() {
  return <IniCetLanding />;
}