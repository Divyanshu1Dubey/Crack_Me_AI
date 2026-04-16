import { createBrowserClient } from '@supabase/ssr';
import { assertSupabaseConfig } from './config';

export const createClient = () => {
  const { supabaseUrl, supabaseKey } = assertSupabaseConfig('browser client');

  return createBrowserClient(
    supabaseUrl,
    supabaseKey,
    {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    },
  );
};
