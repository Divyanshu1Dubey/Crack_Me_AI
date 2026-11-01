/**
 * /exams/[slug]/page.tsx — catch-all for /exams/<slug>.
 *
 * /exams/cms, /exams/neet-pg and /exams/usmle have dedicated pages (static
 * routes win), so this only sees aliases and unknown slugs: the aliases
 * permanently redirect, anything else is a real 404 (it used to answer 200
 * with an "Exam Not Found" page).
 */
import { notFound, permanentRedirect } from 'next/navigation';
import type { Metadata } from 'next';

type Props = { params: Promise<{ slug: string }> };

const ALIASES: Record<string, string> = {
  'upsc-cms': '/exams/cms',
  neetpg: '/exams/neet-pg',
  'ini-cet': '/ini-cet',
  inicet: '/ini-cet',
  fmge: '/fmge',
};

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function ExamSlugDispatcher({ params }: Props) {
  const { slug } = await params;
  const target = ALIASES[slug.toLowerCase()];
  if (target) permanentRedirect(target);
  notFound();
}
