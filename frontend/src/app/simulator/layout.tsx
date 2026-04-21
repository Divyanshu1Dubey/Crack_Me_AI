import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Simulator',
  robots: { index: false, follow: false },
  alternates: { canonical: '/simulator' },
};

export default function SimulatorLayout({ children }: { children: ReactNode }) {
  return children;
}
