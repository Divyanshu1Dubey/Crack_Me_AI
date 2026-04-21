import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Register',
  description: 'Create your CrackCMS account for UPSC CMS and NEET PG preparation workflows.',
  robots: { index: false, follow: false },
  alternates: { canonical: '/register' },
};

export default function RegisterLayout({ children }: { children: ReactNode }) {
  return children;
}
