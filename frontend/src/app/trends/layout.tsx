import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Trends',
  robots: { index: false, follow: false },
  alternates: { canonical: '/trends' },
};

export default function TrendsLayout({ children }: { children: ReactNode }) {
  return children;
}
