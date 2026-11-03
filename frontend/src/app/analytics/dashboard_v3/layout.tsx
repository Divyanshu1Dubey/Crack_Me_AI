import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Analytics Dashboard',
  robots: { index: false, follow: false },
  alternates: { canonical: '/analytics/dashboard_v3' },
};

// The page renders no Sidebar/Header of its own; the shell gives its
// loading, error and data states the app navigation.
export default function AnalyticsDashboardV3Layout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
