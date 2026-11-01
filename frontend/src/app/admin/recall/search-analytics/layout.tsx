import type { Metadata } from 'next';
import type { ReactNode } from 'react';

// Title only: the app shell comes from the parent /admin/recall layout.
export const metadata: Metadata = {
  title: 'Recall Search Analytics',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/recall/search-analytics' },
};

export default function AdminRecallSearchAnalyticsLayout({ children }: { children: ReactNode }) {
  return children;
}
