import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Textbooks',
  robots: { index: false, follow: false },
  alternates: { canonical: '/textbooks' },
};

export default function TextbooksLayout({ children }: { children: ReactNode }) {
  return children;
}
