import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Recall Admin',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/recall' },
};

// /admin/recall and /admin/recall/search-analytics render no Sidebar/Header
// of their own; the shell gives both the app navigation.
export default function AdminRecallLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
