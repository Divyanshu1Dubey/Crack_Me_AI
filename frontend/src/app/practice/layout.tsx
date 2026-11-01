import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Practice',
  robots: { index: false, follow: false },
  alternates: { canonical: '/practice' },
};

// The page renders no Sidebar/Header of its own; the shell gives it (and its
// Suspense fallback) the app navigation.
export default function PracticeLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
