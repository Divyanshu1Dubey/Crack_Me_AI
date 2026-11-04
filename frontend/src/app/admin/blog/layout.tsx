import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Blog Posts (Admin)',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/blog' },
};

export default function AdminBlogLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
