import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    outputFileTracingRoot: process.cwd().replace(/\\frontend-usmle$/, ""),
    images: {
        remotePatterns: [
            { protocol: "https", hostname: "**.supabase.co" },
            { protocol: "https", hostname: "crackcms-vsthc.ondigitalocean.app" },
        ],
    },
};

export default nextConfig;
