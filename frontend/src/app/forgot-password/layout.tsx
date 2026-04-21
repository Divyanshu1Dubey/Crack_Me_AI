import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Forgot Password',
  robots: { index: false, follow: false },
  alternates: { canonical: '/forgot-password' },
};

export default function ForgotPasswordLayout({ children }: { children: ReactNode }) {
  return children;
}
