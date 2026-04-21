import type { Metadata } from 'next';
import { Suspense } from 'react';
import LoginClient from './LoginClient';
import EngagingLoader from '@/components/EngagingLoader';

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

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <EngagingLoader
          title="Opening secure sign-in..."
          subtitle="One moment while we prepare your personalized UPSC CMS dashboard."
          fullScreen
        />
      }
    >
      <LoginClient />
    </Suspense>
  );
}
