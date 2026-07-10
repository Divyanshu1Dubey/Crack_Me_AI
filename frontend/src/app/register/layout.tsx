import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { defaultOgImage, pageMetadata, seoKeywords, siteName, siteUrl } from '@/lib/seo';

export const metadata: Metadata = {
  title: pageMetadata['/register'].title,
  description: pageMetadata['/register'].description,
  keywords: [...seoKeywords, 'free UPSC CMS preparation account', 'free medical MCQ practice'],
  robots: { index: true, follow: true },
  alternates: { canonical: '/register' },
  openGraph: {
    type: 'website',
    title: pageMetadata['/register'].title,
    description: pageMetadata['/register'].description,
    url: `${siteUrl}/register`,
    siteName,
    images: [defaultOgImage],
  },
  twitter: {
    card: 'summary_large_image',
    title: pageMetadata['/register'].title,
    description: pageMetadata['/register'].description,
    images: [defaultOgImage],
  },
};

export default function RegisterLayout({ children }: { children: ReactNode }) {
  return children;
}
