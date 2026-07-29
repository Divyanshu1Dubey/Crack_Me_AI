import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { buildPageMetadata } from '@/lib/metadata';

/**
 * Hub-level layout for every /blog/* route.
 *
 * The route handlers (index + [slug]) set their own per-page metadata;
 * this layout only exports a default fallback so we never leak the root
 * layout title into blog URLs.
 */
export const metadata: Metadata = buildPageMetadata({
    title: 'CrackCMS Blog — Exam Strategy & Last-Minute Prep',
    description:
        'High-yield exam strategy posts for UPSC CMS, NEET PG, INI-CET and FMGE.',
    path: '/blog',
    image: '/cms-circle-logo.png',
});

export default function BlogLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
