import { NextResponse } from 'next/server';

const BACKEND_URL = 'https://crackcms-vsthc.ondigitalocean.app';

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
