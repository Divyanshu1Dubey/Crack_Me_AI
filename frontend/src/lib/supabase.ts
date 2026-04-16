import type { SupabaseClient } from '@supabase/supabase-js';
import { createClient as createSupabaseBrowserClient } from '@/utils/supabase/client';
import { getSupabaseConfig } from '@/utils/supabase/config';

let browserClient: SupabaseClient | null = null;

export const isSupabaseConfigured = () => getSupabaseConfig().isConfigured;

export const isSupabaseAuthEnabled = () =>
  isSupabaseConfigured()
  && (process.env.NEXT_PUBLIC_AUTH_PROVIDER || '').toLowerCase() === 'supabase'
  && (process.env.NEXT_PUBLIC_USE_SUPABASE_AUTH ?? 'false') === 'true';

export const getSupabaseBrowserClient = () => {
  if (!isSupabaseConfigured()) return null;

  if (!browserClient) {
    browserClient = createSupabaseBrowserClient();
  }

  return browserClient;
};
