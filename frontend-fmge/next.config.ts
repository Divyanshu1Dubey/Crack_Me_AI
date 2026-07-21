import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    outputFileTracingRoot: process.cwd().replace(/\\frontend-fmge$/, ""),
    images: {
        remotePatterns: [
            { protocol: "https", hostname: "**.supabase.co" },
            { protocol: "https", hostname: "crackcms-vsthc.ondigitalocean.app" },
        ],
    },
};

export default nextConfig;
