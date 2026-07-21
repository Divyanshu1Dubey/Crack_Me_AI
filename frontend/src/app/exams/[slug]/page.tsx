/**
 * /exams/[slug]/page.tsx — Dispatcher for the legacy exam slugs.
 *
 * Routes the existing /exams/upsc-cms, /exams/neet-pg, /exams/usmle,
 * /exams/ini-cet, /exams/fmge URLs to their respective microsite pages.
 * For the three fully-built microsites (cms, neet-pg, usmle) it 308s to
 * the canonical path; ini-cet and fmge still render the legacy info page.
 */
import { redirect } from 'next/navigation';
import type { Metadata } from 'next';

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  // Canonical pages own their metadata; pass-through redirect.
  return { title: 'Redirecting…', robots: { index: false, follow: false } };
}

export default async function ExamSlugDispatcher({ params }: Props) {
  const { slug } = await params;
  // Normalize aliases.
  if (slug === 'upsc-cms') redirect('/exams/cms');
  if (slug === 'neetpg') redirect('/exams/neet-pg');
  // cms / neet-pg / usmle already have dedicated pages — next/dynamic
  // routes hit those first, so this dispatcher only sees unknown slugs.
  return (
    <div className="flex-1 p-8 text-center mt-20">
      <h1 className="text-3xl font-bold mb-4">Exam Not Found</h1>
      <p className="text-muted-foreground mb-6">
        We don&apos;t have a microsite for &quot;{slug}&quot; yet.
      </p>
      <div className="flex justify-center gap-3 flex-wrap">
        <a href="/exams/cms" className="text-primary hover:underline">UPSC CMS</a>
        <span>·</span>
        <a href="/exams/neet-pg" className="text-primary hover:underline">NEET PG</a>
        <span>·</span>
        <a href="/exams/usmle" className="text-primary hover:underline">USMLE</a>
      </div>
    </div>
  );
}