import { NextResponse } from 'next/server';

/**
 * GET /api/keep-alive — Pings the backend to prevent Render free tier from sleeping.
 * Use with cron-job.org (free) to call every 5 minutes.
 */
export async function GET() {
    const backendUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/api$/, '');
    try {
        const res = await fetch(`${backendUrl}/api/health/`, {
            method: 'GET',
            signal: AbortSignal.timeout(30000),
        });
        return NextResponse.json({ status: 'ok', backend: res.status }, { status: 200 });
    } catch {
        return NextResponse.json({ status: 'waking', backend: 'timeout' }, { status: 200 });
    }
}
