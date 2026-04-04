'use client';
import { useEffect } from 'react';

const DEFAULT_LOCAL_BACKEND_BASE = 'http://localhost:8000';
const DEFAULT_PRODUCTION_BACKEND_BASE = 'https://crackcms-vsthc.ondigitalocean.app';
const LEGACY_UNHEALTHY_API_HOSTS = ['crackcms-vsthc.ondigitalocean.app'];

const resolveBackendBase = () => {
    const configuredApi = (process.env.NEXT_PUBLIC_API_URL || '').trim();
    if (configuredApi) {
        const normalized = configuredApi.replace(/\/+$/, '');
        const configuredBase = normalized.replace(/\/api$/, '');
        if (LEGACY_UNHEALTHY_API_HOSTS.some((host) => configuredBase.includes(host))) {
            return DEFAULT_PRODUCTION_BACKEND_BASE;
        }
        return configuredBase;
    }

    if (process.env.NODE_ENV === 'production') {
        return DEFAULT_PRODUCTION_BACKEND_BASE;
    }

    return DEFAULT_LOCAL_BACKEND_BASE;
};

const BACKEND_BASE = resolveBackendBase();

/**
 * Pings the backend on mount to wake it up after cold starts.
 * Also pings every 4 minutes to keep it responsive while users are browsing.
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
