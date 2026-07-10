import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { defaultOgImage, pageMetadata, seoKeywords, siteName, siteUrl } from '@/lib/seo';

export const metadata: Metadata = {
  title: pageMetadata['/subscription'].title,
  description: pageMetadata['/subscription'].description,
  keywords: [...seoKeywords, 'CrackCMS premium', 'UPSC CMS premium plan', 'medical exam test series price'],
  robots: { index: true, follow: true },
  alternates: { canonical: '/subscription' },
  openGraph: {
    type: 'website',
    title: pageMetadata['/subscription'].title,
    description: pageMetadata['/subscription'].description,
    url: `${siteUrl}/subscription`,
    siteName,
    images: [defaultOgImage],
  },
  twitter: {
    card: 'summary_large_image',
    title: pageMetadata['/subscription'].title,
    description: pageMetadata['/subscription'].description,
    images: [defaultOgImage],
  },
};

export default function SubscriptionLayout({ children }: { children: ReactNode }) {
  return children;
}
