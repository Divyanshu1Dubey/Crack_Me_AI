'use client';
import { useEffect } from 'react';

const BACKEND_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/api$/, '');

/**
 * Pings the backend on mount to wake up Render free tier (cold start ~30s).
 * Also pings every 4 minutes to keep it alive while users are browsing.
 */
export default function BackendWarmup() {
    useEffect(() => {
        const ping = () => {
            fetch(`${BACKEND_BASE}/api/health/`, { method: 'GET' }).catch(() => {});
        };
        // Immediate ping on page load
        ping();
        // Keep alive every 4 minutes
        const interval = setInterval(ping, 4 * 60 * 1000);
        return () => clearInterval(interval);
    }, []);

    return null;
}
