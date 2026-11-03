import type { SupabaseClient } from '@supabase/supabase-js';
import { createClient as createSupabaseBrowserClient } from '@/utils/supabase/client';
import { getSupabaseConfig } from '@/utils/supabase/config';
import { isLocalAuthMode } from './localAuth';

let browserClient: SupabaseClient | null = null;

const INVALID_REFRESH_TOKEN_MARKERS = [
  'invalid refresh token',
  'refresh token not found',
  'refresh token is invalid',
];

export const isSupabaseConfigured = () => getSupabaseConfig().isConfigured;

// In local dev auth mode (NEXT_PUBLIC_AUTH_MODE=local) Supabase is switched
// off entirely, even if its keys are present in the environment.
export const isSupabaseAuthEnabled = () =>
  !isLocalAuthMode() && isSupabaseConfigured();

export const getSupabaseBrowserClient = () => {
  if (isLocalAuthMode() || !isSupabaseConfigured()) return null;

  if (!browserClient) {
    browserClient = createSupabaseBrowserClient();
  }

  return browserClient;
};

export const isInvalidRefreshTokenError = (error: unknown): boolean => {
  const message = (
    (error as { message?: string } | null)?.message
    || (error as { error_description?: string } | null)?.error_description
    || ''
  ).toLowerCase();

  return INVALID_REFRESH_TOKEN_MARKERS.some((marker) => message.includes(marker));
};

export const clearSupabaseLocalSession = async () => {
  const client = getSupabaseBrowserClient();
  if (!client) return;

  try {
    await client.auth.signOut({ scope: 'local' });
  } catch {
    // Best-effort cleanup only.
  }
};
