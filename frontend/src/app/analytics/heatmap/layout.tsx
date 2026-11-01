import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Study Heatmap',
  robots: { index: false, follow: false },
  alternates: { canonical: '/analytics/heatmap' },
};

// The page renders no Sidebar/Header of its own; the shell gives its
// loading, error and data states the app navigation.
export default function AnalyticsHeatmapLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
