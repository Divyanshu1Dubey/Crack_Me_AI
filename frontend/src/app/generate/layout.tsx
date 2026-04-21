import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Generate',
  robots: { index: false, follow: false },
  alternates: { canonical: '/generate' },
};

export default function GenerateLayout({ children }: { children: ReactNode }) {
  return children;
}
