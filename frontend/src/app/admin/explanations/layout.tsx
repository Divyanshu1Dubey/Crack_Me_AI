import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'AI Explanations (Admin)',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/explanations' },
};

export default function AdminExplanationsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
