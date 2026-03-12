/**
 * Sentry client-side configuration for CrackCMS frontend.
 * Set NEXT_PUBLIC_SENTRY_DSN environment variable to enable.
 */
import * as Sentry from '@sentry/nextjs';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
    Sentry.init({
        dsn,
        tracesSampleRate: 0.1,
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 0.1,
    });
}
