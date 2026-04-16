import { Suspense } from 'react';
import AuthCallbackClient from './AuthCallbackClient';

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen grid place-items-center bg-background text-muted-foreground">Completing sign in...</div>}>
      <AuthCallbackClient />
    </Suspense>
  );
}
