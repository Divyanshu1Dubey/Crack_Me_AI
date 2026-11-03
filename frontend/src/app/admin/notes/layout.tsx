import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Topic Notes (Admin)',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/notes' },
};

// The page renders no Sidebar/Header of its own; the shell gives the admin
// tool the app navigation.
export default function AdminNotesLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
