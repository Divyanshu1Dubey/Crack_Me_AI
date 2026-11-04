import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Answer-Key Review (Admin)',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/review-queue' },
};

export default function AdminReviewQueueLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
