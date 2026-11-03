import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Connect Google Sign-in',
  robots: { index: false, follow: false },
  alternates: { canonical: '/connect-google' },
};

export default function ConnectGoogleLayout({ children }: { children: ReactNode }) {
  return children;
}
