'use client';

import { useEffect, useRef } from 'react';
import {
    GISCUS_CATEGORY,
    GISCUS_CATEGORY_ID,
    GISCUS_CONFIGURED,
    GISCUS_REPO,
    GISCUS_REPO_ID,
} from '@/components/giscusConfig';

interface CommentsGiscusProps {
    slug: string;
    /**
     * Configured against the public CrackCMS GitHub Discussions repo. If the
     * repo or category changes, update giscusConfig.ts (or wire up env vars).
     */
}

/**
 * Giscus is a GitHub-Discussions-backed comment widget:
 *   - No external trackers (aligns with our privacy-first posture)
 *   - No spam surface (GitHub auth)
 *   - Works in dark mode (we set `data-theme="light"` and let Giscus mirror the
 *     document by toggling via ThemeSync; or pass a custom `theme` string).
 *   - Lazy-loaded on the client only via dynamic `<script>` injection.
 *
 * Configuration:
 *   - repo:        `Divyanshu1Dubey/crackcms-blog` (a public GitHub repo with
 *                  Discussions enabled — see TODO below if it's not yet
 *                  created).
 *   - repoId + categoryId: derived from GitHub Discussions setup (see
 *     giscusConfig.ts). Until they are set, this renders nothing and
 *     BlogPostLayout leaves the comments section out.
 */
export function CommentsGiscus({ slug }: CommentsGiscusProps) {
    const containerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        // Only mount once we know the Giscus IDs.
        if (!GISCUS_REPO_ID || !GISCUS_CATEGORY_ID) return;
        if (!containerRef.current) return;

        // Clean up any previous instance (e.g. on hot reload).
        containerRef.current.innerHTML = '';

        const script = document.createElement('script');
        script.src = 'https://giscus.app/client.js';
        script.async = true;
        script.crossOrigin = 'anonymous';
        script.setAttribute('data-repo', GISCUS_REPO);
        script.setAttribute('data-repo-id', GISCUS_REPO_ID);
        script.setAttribute('data-category', GISCUS_CATEGORY);
        script.setAttribute('data-category-id', GISCUS_CATEGORY_ID);
        script.setAttribute('data-mapping', 'specific');
        script.setAttribute('data-term', slug);
        script.setAttribute('data-strict', '0');
        script.setAttribute('data-reactions-enabled', '1');
        script.setAttribute('data-emit-metadata', '0');
        script.setAttribute('data-input-position', 'top');
        script.setAttribute('data-theme', 'light');
        script.setAttribute('data-lang', 'en');
        script.setAttribute('data-loading', 'lazy');

        containerRef.current.appendChild(script);
    }, [slug]);

    if (!GISCUS_CONFIGURED) return null;

    return (
        <div className="rounded-2xl border border-border bg-card p-4 sm:p-6">
            <div ref={containerRef} className="giscus" />
        </div>
    );
}
