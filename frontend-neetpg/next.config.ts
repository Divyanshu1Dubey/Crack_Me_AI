import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    // Allow monorepo root tracing — same trick the main CMS frontend uses.
    outputFileTracingRoot: process.cwd().replace(/\\frontend-neetpg$/, ""),
    images: {
        remotePatterns: [
            { protocol: "https", hostname: "**.supabase.co" },
            { protocol: "https", hostname: "crackcms-vsthc.ondigitalocean.app" },
        ],
    },
};

export default nextConfig;
