import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Questions',
  robots: { index: false, follow: false },
  alternates: { canonical: '/questions' },
};

export default function QuestionsLayout({ children }: { children: ReactNode }) {
  return children;
}
