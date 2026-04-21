import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Reset Password',
  robots: { index: false, follow: false },
  alternates: { canonical: '/reset-password' },
};

export default function ResetPasswordLayout({ children }: { children: ReactNode }) {
  return children;
}
