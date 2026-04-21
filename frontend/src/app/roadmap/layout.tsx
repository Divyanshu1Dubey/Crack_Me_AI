import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Roadmap',
  robots: { index: false, follow: false },
  alternates: { canonical: '/roadmap' },
};

export default function RoadmapLayout({ children }: { children: ReactNode }) {
  return children;
}
