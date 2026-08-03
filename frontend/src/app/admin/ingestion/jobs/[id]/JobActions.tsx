'use client';

/**
 * JobActions — admin controls for retrying / cancelling an ingestion job.
 *
 * Why a client component: the previous version used `<form action="/api/...">`
 * which submitted a native HTML POST and BYPASSED the centralized Axios
 * client (and therefore the Supabase auth interceptor + DigitalOcean /
 * onrender.com base-URL failover chain). Calling `ingestionAPI.retryJob` /
 * `ingestionAPI.cancelJob` keeps the request authenticated and on the right
 * base URL even if the primary backend is unhealthy.
 */
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ingestionAPI } from '@/lib/api';

export default function JobActions({ id }: { id: number }) {
    const router = useRouter();
    const [busy, setBusy] = useState<'retry' | 'cancel' | null>(null);
    const [error, setError] = useState<string | null>(null);

    const run = async (kind: 'retry' | 'cancel') => {
        if (busy) return;
        const verb = kind === 'retry' ? 'retry' : 'cancel';
        if (!confirm(`${verb[0].toUpperCase() + verb.slice(1)} job #${id}?`)) return;
        setBusy(kind);
        setError(null);
        try {
            if (kind === 'retry') {
                await ingestionAPI.retryJob(id);
            } else {
                await ingestionAPI.cancelJob(id);
            }
            router.refresh();
        } catch (err) {
            console.error(`Failed to ${kind} job:`, err);
            setError(`Could not ${kind} job. Please try again.`);
        } finally {
            setBusy(null);
        }
    };

    return (
        <div className="flex items-center gap-2">
            <button
                type="button"
                onClick={() => run('retry')}
                disabled={busy !== null}
                className="rounded border px-3 py-1 text-sm hover:bg-muted disabled:opacity-50"
            >
                {busy === 'retry' ? 'Retrying…' : 'Retry'}
            </button>
            <button
                type="button"
                onClick={() => run('cancel')}
                disabled={busy !== null}
                className="rounded border px-3 py-1 text-sm hover:bg-muted disabled:opacity-50"
            >
                {busy === 'cancel' ? 'Cancelling…' : 'Cancel'}
            </button>
            {error && <span className="text-xs text-destructive">{error}</span>}
        </div>
    );
}
