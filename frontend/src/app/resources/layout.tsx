import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { seoKeywords, siteDescription, siteName, siteUrl } from '@/lib/seo';

export const metadata: Metadata = {
  title: 'UPSC CMS Resources, Syllabus, FAQ and Booklist',
  description:
    'Explore UPSC CMS resources including syllabus guidance, FAQ, official documents, and recommended books for CMS exam and NEET PG aligned medical revision.',
  keywords: [...seoKeywords, 'UPSC CMS syllabus', 'UPSC CMS FAQ', 'UPSC CMS books'],
  alternates: {
    canonical: '/resources',
  },
  openGraph: {
    type: 'article',
    title: 'UPSC CMS Resources and Medical Exam Guide',
    description: siteDescription,
    url: `${siteUrl}/resources`,
    siteName,
    images: ['/crack-cms-logo.jpg'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'UPSC CMS Resources and Medical Exam Guide',
    description: siteDescription,
    images: ['/crack-cms-logo.jpg'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function ResourcesLayout({ children }: { children: ReactNode }) {
  return children;
}
