/**
 * supabase.ts — Browser-side Supabase client for the NEET PG site.
 * Shares the same Supabase project as the CMS site (auth is upserted by email).
 */
import { createBrowserClient } from "@supabase/ssr";

let cached: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseBrowserClient() {
    if (cached) return cached;
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) {
        throw new Error("Supabase env vars missing. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
    }
    cached = createBrowserClient(url, key);
    return cached;
}
