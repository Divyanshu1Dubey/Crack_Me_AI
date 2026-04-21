import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'AI Tutor',
  robots: { index: false, follow: false },
  alternates: { canonical: '/ai-tutor' },
};

export default function AITutorLayout({ children }: { children: ReactNode }) {
  return children;
}
