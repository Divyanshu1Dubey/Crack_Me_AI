import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Tokens',
  robots: { index: false, follow: false },
  alternates: { canonical: '/tokens' },
};

export default function TokensLayout({ children }: { children: ReactNode }) {
  return children;
}
