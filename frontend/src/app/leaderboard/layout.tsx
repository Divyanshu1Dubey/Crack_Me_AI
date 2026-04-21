import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Leaderboard',
  robots: { index: false, follow: false },
  alternates: { canonical: '/leaderboard' },
};

export default function LeaderboardLayout({ children }: { children: ReactNode }) {
  return children;
}
