import { NextResponse } from 'next/server';

const BACKEND_URL = 'https://crackcms-backend.onrender.com';

/**
 * GET /api/keep-alive — Pings the backend to prevent Render free tier from sleeping.
 * Use with cron-job.org (free) to call every 5 minutes.
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
