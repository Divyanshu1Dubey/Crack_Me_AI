import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Tests',
  robots: { index: false, follow: false },
  alternates: { canonical: '/tests' },
};

export default function TestsLayout({ children }: { children: ReactNode }) {
  return children;
}
