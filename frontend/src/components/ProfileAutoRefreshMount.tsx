'use client';
/**
 * ProfileAutoRefreshMount — wraps the authed app in useProfileAutoRefresh
 * so refreshing tokens / subscription state happens automatically and isn't
 * gated on any /specific/ page being mounted.
 *
 * This is the glue that fixes the textbook complaint "tokens didn't refresh
 * at midnight": the user keeps the app open in a tab overnight, the hook
 * polls every 5 minutes, and the next morning their daily counter is fresh.
 *
 * Lives in src/components so it can be imported into the root layout (which
 * is a server component). All the actual logic lives in
 * `useProfileAutoRefresh` — this file is just a client boundary.
 */
import { useProfileAutoRefresh } from '@/lib/useProfileAutoRefresh';

export function ProfileAutoRefreshMount(): null {
    useProfileAutoRefresh();
    return null;
}

export default ProfileAutoRefreshMount;
