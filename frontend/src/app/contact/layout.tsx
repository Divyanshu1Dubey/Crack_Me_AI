import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { defaultOgImage, pageMetadata, siteName, siteUrl } from '@/lib/seo';

export const metadata: Metadata = {
  title: pageMetadata['/contact'].title,
  description: pageMetadata['/contact'].description,
  alternates: { canonical: '/contact' },
  robots: { index: true, follow: true },
  openGraph: {
    type: 'website',
    title: pageMetadata['/contact'].title,
    description: pageMetadata['/contact'].description,
    url: `${siteUrl}/contact`,
    siteName,
    images: [defaultOgImage],
  },
};

export default function ContactLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
