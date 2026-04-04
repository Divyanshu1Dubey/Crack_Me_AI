import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const DEFAULT_SUPABASE_URL = 'https://ryuvcdthjnxyetdyjbph.supabase.co';
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || DEFAULT_SUPABASE_URL).trim();
const supabaseAnonKey = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '').trim();

let browserClient: SupabaseClient | null = null;

export const isSupabaseConfigured = () => Boolean(supabaseUrl && supabaseAnonKey);

export const isSupabaseAuthEnabled = () =>
  isSupabaseConfigured() && (process.env.NEXT_PUBLIC_USE_SUPABASE_AUTH ?? 'true') === 'true';

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
