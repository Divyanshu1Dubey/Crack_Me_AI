import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Confirm Email',
  robots: { index: false, follow: false },
  alternates: { canonical: '/verify-email' },
};

export default function VerifyEmailLayout({ children }: { children: ReactNode }) {
  return children;
}
