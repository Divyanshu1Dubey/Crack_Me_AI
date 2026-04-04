import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Login',
  description: 'Sign in to CrackCMS to access your student dashboard or admin panel.',
  robots: {
    index: false,
    follow: false,
  },
  alternates: {
    canonical: '/login',
  },
};

export default function LoginLayout({ children }: { children: ReactNode }) {
  return children;
}