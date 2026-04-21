import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Analytics',
  robots: { index: false, follow: false },
  alternates: { canonical: '/analytics' },
};

export default function AnalyticsLayout({ children }: { children: ReactNode }) {
  return children;
}
