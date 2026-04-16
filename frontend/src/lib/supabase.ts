import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || '').trim();
const supabaseAnonKey = (
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  || ''
).trim();

let browserClient: SupabaseClient | null = null;

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
