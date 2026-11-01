import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Announcements',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/announcements' },
};

// The page renders no Sidebar/Header of its own; the shell gives the admin
// tool the app navigation (there was no way back except browser Back).
export default function AdminAnnouncementsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
