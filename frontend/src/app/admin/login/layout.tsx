import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Admin Login',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/login' },
};

export default function AdminLoginLayout({ children }: { children: ReactNode }) {
  return children;
}
