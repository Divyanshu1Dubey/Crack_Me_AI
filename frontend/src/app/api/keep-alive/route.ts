import { NextResponse } from 'next/server';

const DEFAULT_BACKEND_BASE_URL = 'https://crackcms-vsthc.ondigitalocean.app';

const resolveBackendBaseUrl = () => {
    const configured = (
        process.env.BACKEND_BASE_URL
        || process.env.BACKEND_API_URL
        || process.env.NEXT_PUBLIC_API_URL
        || ''
    ).trim();

    if (!configured) return DEFAULT_BACKEND_BASE_URL;
    const normalized = configured.replace(/\/+$/, '');
    return normalized.endsWith('/api') ? normalized.slice(0, -4) : normalized;
};

const BACKEND_URL = resolveBackendBaseUrl();

/**
 * GET /api/keep-alive — Pings the backend to prevent it from sleeping.
 * Use with cron-job.org (free) or your scheduler to call every 5 minutes.
 */
export async function GET() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/health/`, {
            method: 'GET',
            signal: AbortSignal.timeout(30000),
        });
        return NextResponse.json({ status: 'ok', backend: res.status }, { status: 200 });
    } catch {
        return NextResponse.json({ status: 'waking', backend: 'timeout' }, { status: 200 });
    }
}
