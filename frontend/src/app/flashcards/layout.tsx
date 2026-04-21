import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Flashcards',
  robots: { index: false, follow: false },
  alternates: { canonical: '/flashcards' },
};

export default function FlashcardsLayout({ children }: { children: ReactNode }) {
  return children;
}
