'use client';

/**
 * /ai-tutor route error boundary — catches any render-time exception in the
 * chat thread (e.g. legacy session rows with malformed fields) and renders
 * a friendly recovery card instead of the global "Something went wrong" page
 * that blanks the entire app.
 *
 * The user can keep the chat sidebar (New Chat button) and the page header,
 * which means they can start a fresh conversation without losing context.
 */

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle, RefreshCw, MessageSquare, Home } from 'lucide-react';

export default function AITutorError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        if (process.env.NODE_ENV !== 'production') {
            // eslint-disable-next-line no-console
            console.error('AI Tutor page crashed:', error);
        }
        // Best-effort: report to Sentry if loaded via window
        if (typeof window !== 'undefined') {
            const w = window as unknown as {
                Sentry?: { captureException: (e: Error) => void };
            };
            try { w.Sentry?.captureException?.(error); } catch { /* noop */ }
        }
    }, [error]);

    return (
        <div className="min-h-screen bg-slate-50/60 dark:bg-slate-950 flex items-center justify-center p-6">
            <div className="max-w-md w-full bg-card border border-border rounded-3xl p-8 shadow-2xl text-center">
                <div className="w-16 h-16 rounded-2xl mx-auto mb-5 flex items-center justify-center"
                    style={{ background: 'rgba(239, 68, 68, 0.12)' }}>
                    <AlertTriangle className="w-8 h-8 text-red-500" aria-hidden="true" />
                </div>
                <h1 className="text-xl font-bold mb-2">AI Tutor hit a snag</h1>
                <p className="text-sm text-muted-foreground mb-1">
                    One of your saved chat messages couldn&apos;t render. The rest of CrackCMS
                    is unaffected.
                </p>
                <p className="text-xs text-muted-foreground mb-6">
                    Try refreshing the chat — your other conversations stay safe.
                </p>

                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                    <button
                        onClick={() => reset()}
                        className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-sm transition-all"
                    >
                        <RefreshCw className="w-4 h-4" aria-hidden="true" />
                        Refresh Chat
                    </button>
                    <Link
                        href="/ai-tutor"
                        className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:hover:bg-slate-100 dark:text-black font-bold text-sm transition-all"
                    >
                        <MessageSquare className="w-4 h-4" aria-hidden="true" />
                        Start Fresh Chat
                    </Link>
                    <Link
                        href="/"
                        className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-border hover:bg-muted text-sm font-bold transition-all"
                    >
                        <Home className="w-4 h-4" aria-hidden="true" />
                        Home
                    </Link>
                </div>

                {error?.digest && (
                    <p className="mt-6 text-[11px] text-muted-foreground font-mono">
                        ref: {error.digest}
                    </p>
                )}
            </div>
        </div>
    );
}
