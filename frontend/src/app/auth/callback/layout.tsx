import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Auth Callback',
  robots: { index: false, follow: false },
  alternates: { canonical: '/auth/callback' },
};

export default function AuthCallbackLayout({ children }: { children: ReactNode }) {
  return children;
}
