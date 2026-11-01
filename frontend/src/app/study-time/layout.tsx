import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Study Time',
  robots: { index: false, follow: false },
  alternates: { canonical: '/study-time' },
};

// The page renders no Sidebar/Header of its own; the shell gives it the app navigation.
export default function StudyTimeLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
