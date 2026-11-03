import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Manage Jobs',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/jobs' },
};

// The page renders no Sidebar/Header of its own; the shell gives the admin
// tool the app navigation.
export default function AdminJobsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
