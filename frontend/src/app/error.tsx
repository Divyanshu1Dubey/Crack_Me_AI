'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Report to Sentry / Datadog if available
    if (typeof window !== 'undefined') {
      const w = window as unknown as {
        Sentry?: { captureException: (e: Error) => void };
      };
      if (w.Sentry?.captureException) {
        w.Sentry.captureException(error);
      }
    }
    if (process.env.NODE_ENV !== 'production') {
      console.error('Global error caught:', error);
    }
  }, [error]);

  return (
    <div className="min-h-[calc(100vh-80px)] flex items-center justify-center p-4 sm:p-6 md:p-8">
      <div className="max-w-xl w-full text-center">
        <div
          className="inline-flex items-center justify-center w-20 h-20 sm:w-24 sm:h-24 rounded-3xl bg-destructive/10 text-destructive mb-6 sm:mb-8"
          aria-hidden="true"
        >
          <AlertTriangle className="w-10 h-10 sm:w-12 sm:h-12" />
        </div>

        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight mb-3 sm:mb-4">
          Something went wrong
        </h1>

        <p className="text-base sm:text-lg text-muted-foreground mb-8 sm:mb-10 max-w-md mx-auto">
          We&apos;ve been notified. You can try the action again, or head back to a
          known-good page.
        </p>

        {error.digest && (
          <p className="text-xs font-mono text-muted-foreground mb-6">
            Error ID: {error.digest}
          </p>
        )}

        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
          <Button onClick={reset} size="lg" className="min-h-12 px-6">
            <RefreshCw className="w-4 h-4 mr-2" aria-hidden="true" />
            Try again
          </Button>
          <Button asChild size="lg" variant="outline" className="min-h-12 px-6">
            <Link href="/">
              <Home className="w-4 h-4 mr-2" aria-hidden="true" />
              Go home
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
