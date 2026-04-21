import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Dashboard',
  robots: { index: false, follow: false },
  alternates: { canonical: '/dashboard' },
};

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return children;
}
