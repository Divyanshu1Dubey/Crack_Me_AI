import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Premium Subscription | CrackCMS',
  robots: { index: false, follow: false },
  alternates: { canonical: '/subscription' },
};

export default function SubscriptionLayout({ children }: { children: ReactNode }) {
  return children;
}
