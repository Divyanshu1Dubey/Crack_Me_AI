import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Topic Notes',
  robots: { index: false, follow: false },
  alternates: { canonical: '/topic-notes' },
};

// The page renders no Sidebar/Header of its own; the shell gives every
// state (loading, non-admin notice, notes) the app navigation.
export default function TopicNotesLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
