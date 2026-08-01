'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

/**
 * useRequireAuth — client-side gate for protected pages.
 *
 * Behavior:
 * - While `authLoading` is true, render the caller's `loading` JSX (or nothing).
 * - If the user is unauthenticated, `router.replace` to `/login?next=<current path>`
 *   (replace so the back button doesn't return to a gated page). The login
 *   page already honours `?next=` via LoginClient.tsx.
 * - If `requireAdmin` is true, non-admin users are bounced to `/dashboard`.
 * - Once auth resolves and the user passes the gate, `onReady()` fires (typically
 *   to kick off data fetches).
 *
 * Why a hook: every page used to repeat the same useEffect boilerplate, and
 * most of them lost the `next=` query param, so logged-out users got dropped
 * on `/dashboard` after login instead of returning to the deep link.
 */
export function useRequireAuth(options?: {
    requireAdmin?: boolean;
    loading?: React.ReactNode;
    onReady?: () => void;
}) {
    const { user, loading: authLoading, isAuthenticated } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    const isAdmin =
        !!user &&
        ((user as { role?: string }).role === 'admin' ||
            (user as { is_admin?: boolean }).is_admin === true);

    useEffect(() => {
        if (authLoading) return;

        if (!isAuthenticated) {
            const next = pathname || '/dashboard';
            router.replace(`/login?next=${encodeURIComponent(next)}`);
            return;
        }

        if (options?.requireAdmin && !isAdmin) {
            router.replace('/dashboard');
            return;
        }

        options?.onReady?.();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [authLoading, isAuthenticated, isAdmin, pathname]);

    return {
        ready: !authLoading && isAuthenticated && (!options?.requireAdmin || isAdmin),
        isAdmin,
        user,
        loading: authLoading,
    };
}
