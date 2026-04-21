import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || '').trim();
const supabaseAnonKey = (
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  || ''
).trim();

let browserClient: SupabaseClient | null = null;

const INVALID_REFRESH_TOKEN_MARKERS = [
  'invalid refresh token',
  'refresh token not found',
  'refresh token is invalid',
];

export const isSupabaseConfigured = () => Boolean(supabaseUrl && supabaseAnonKey);

export const isSupabaseAuthEnabled = () =>
  isSupabaseConfigured();

export const getSupabaseBrowserClient = () => {
  if (!isSupabaseConfigured()) return null;

  if (!browserClient) {
    browserClient = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
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
