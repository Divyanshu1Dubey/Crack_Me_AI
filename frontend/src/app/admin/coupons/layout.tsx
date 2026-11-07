import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Coupon Codes (Admin)',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/coupons' },
};

export default function AdminCouponsLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
