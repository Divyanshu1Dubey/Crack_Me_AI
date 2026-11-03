import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Daily Quests',
  robots: { index: false, follow: false },
  alternates: { canonical: '/quests' },
};

// The page renders no Sidebar/Header of its own; the shell gives it the app navigation.
export default function QuestsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
