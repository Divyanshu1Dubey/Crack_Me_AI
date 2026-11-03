'use client';
import { useEffect } from 'react';
import { apiUrl } from '@/lib/apiBase';

// Same base-URL resolution as the Axios client (NEXT_PUBLIC_API_URL, local
// proxy, legacy-host blacklist). The previous copy hard-coded the production
// host for every production build, so preview / staging / local production
// builds kept pinging (and CORS-failing against) api.cracklabs.app.
const HEALTH_URL = apiUrl('/health/');

/**
 * Pings the backend on mount to wake it up after cold starts.
 * Also pings every 4 minutes to keep it responsive while users are browsing.
 */
export default function BackendWarmup() {
    useEffect(() => {
        const ping = () => {
            fetch(HEALTH_URL, { method: 'GET' }).catch(() => {});
        };
        // Immediate ping on page load
        ping();
        // Keep alive every 4 minutes
        const interval = setInterval(ping, 4 * 60 * 1000);
        return () => clearInterval(interval);
    }, []);

    return null;
}
