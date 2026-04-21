import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Feedback',
  robots: { index: false, follow: false },
  alternates: { canonical: '/feedback' },
};

export default function FeedbackLayout({ children }: { children: ReactNode }) {
  return children;
}
