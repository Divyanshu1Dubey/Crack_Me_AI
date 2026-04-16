const DEFAULT_SUPABASE_URL = 'https://ryuvcdthjnxyetdyjbph.supabase.co';

export const getSupabaseConfig = () => {
  const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || DEFAULT_SUPABASE_URL).trim();
  const supabaseKey = (
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
    || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    || ''
  ).trim();

  return {
    supabaseUrl,
    supabaseKey,
    isConfigured: Boolean(supabaseUrl && supabaseKey),
  };
};

export const assertSupabaseConfig = (scope: string) => {
  const config = getSupabaseConfig();
  if (!config.isConfigured) {
    throw new Error(
      `Supabase ${scope} is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY).`,
    );
  }

  return config;
};
