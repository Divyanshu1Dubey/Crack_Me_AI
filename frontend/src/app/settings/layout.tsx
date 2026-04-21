import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Settings',
  robots: { index: false, follow: false },
  alternates: { canonical: '/settings' },
};

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return children;
}
