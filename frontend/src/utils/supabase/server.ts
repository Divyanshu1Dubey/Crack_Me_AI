import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
import { assertSupabaseConfig } from './config';

export const createClient = async () => {
  const { supabaseUrl, supabaseKey } = assertSupabaseConfig('server client');
  const cookieStore = await cookies();

  return createServerClient(
    supabaseUrl,
    supabaseKey,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
          } catch {
            // setAll can be called from Server Components where setting cookies is not allowed.
          }
        },
      },
    },
  );
};
