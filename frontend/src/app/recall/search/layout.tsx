import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Recall Search',
  robots: { index: false, follow: false },
  alternates: { canonical: '/recall/search' },
};

// The page renders no Sidebar/Header of its own; the shell gives it the app navigation.
export default function RecallSearchLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
