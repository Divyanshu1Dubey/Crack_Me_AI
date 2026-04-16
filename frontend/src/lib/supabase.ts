import type { SupabaseClient } from '@supabase/supabase-js';
import { createClient as createSupabaseBrowserClient } from '@/utils/supabase/client';

const DEFAULT_SUPABASE_URL = 'https://ryuvcdthjnxyetdyjbph.supabase.co';
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || DEFAULT_SUPABASE_URL).trim();
const supabasePublishableKey = (
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  || ''
).trim();

let browserClient: SupabaseClient | null = null;

export const isSupabaseConfigured = () => Boolean(supabaseUrl && supabasePublishableKey);

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
