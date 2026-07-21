'use client';

import { AlertTriangle } from 'lucide-react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1rem',
          background: '#f8fafc',
          color: '#0f172a',
        }}
      >
        <div style={{ maxWidth: '28rem', width: '100%', textAlign: 'center' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '5rem',
              height: '5rem',
              borderRadius: '1.5rem',
              background: 'rgba(239, 68, 68, 0.1)',
              color: '#ef4444',
              marginBottom: '1.5rem',
            }}
            aria-hidden="true"
          >
            <AlertTriangle style={{ width: '2.5rem', height: '2.5rem' }} />
          </div>

          <h1
            style={{
              fontSize: '1.875rem',
              fontWeight: 700,
              marginBottom: '0.75rem',
              lineHeight: 1.2,
            }}
          >
            Critical error
          </h1>

          <p
            style={{
              fontSize: '1rem',
              color: '#64748b',
              marginBottom: '1.5rem',
            }}
          >
            The application failed to load. Please refresh the page.
          </p>

          {error.digest && (
            <p
              style={{
                fontSize: '0.75rem',
                fontFamily: 'monospace',
                color: '#94a3b8',
                marginBottom: '1rem',
              }}
            >
              Error ID: {error.digest}
            </p>
          )}

          <button
            onClick={() => reset()}
            style={{
              padding: '0.75rem 1.5rem',
              borderRadius: '0.5rem',
              border: 'none',
              background: '#1d4ed8',
              color: 'white',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '0.875rem',
              minHeight: '3rem',
              minWidth: '8rem',
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
