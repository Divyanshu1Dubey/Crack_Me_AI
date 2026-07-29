'use client';

import { useEffect, useRef } from 'react';

interface CommentsGiscusProps {
    slug: string;
    /**
     * Configured against the public CrackCMS GitHub Discussions repo. If the
     * repo or category changes, update GISCUS_REPO / GISCUS_CATEGORY_ID below
     * (or wire up env vars).
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
 *   - repoId + categoryId: derived from GitHub Discussions setup; set once the
 *     repo is configured. Until then, the component renders an inline fallback
 *     so the page never breaks.
 *
 * TODO: enable the actual embed by (1) creating the public `crackcms-blog` repo
 * on GitHub, (2) enabling Discussions on it, and (3) running giscus.app once
 * to fetch the repoId + categoryId for the General category, then uncomment
 * the loader below.
 */
const GISCUS_REPO = 'Divyanshu1Dubey/crackcms-blog';
const GISCUS_REPO_ID = ''; // TODO: fill from giscus.app after repo setup
const GISCUS_CATEGORY_ID = ''; // TODO: fill from giscus.app after repo setup
const GISCUS_CATEGORY = 'General';

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

    return (
        <div className="rounded-2xl border border-border bg-card p-4 sm:p-6">
            {GISCUS_REPO_ID && GISCUS_CATEGORY_ID ? (
                <div ref={containerRef} className="giscus" />
            ) : (
                <div className="text-sm text-muted-foreground leading-relaxed">
                    <p className="font-semibold text-foreground">Comments are opening soon.</p>
                    <p className="mt-2">
                        The CrackCMS blog uses GitHub Discussions for comments (no spam, no third-party
                        trackers). The discussion forum is being set up and comments will appear here
                        automatically once it&apos;s live.
                    </p>
                    <p className="mt-3 text-xs text-muted-foreground">
                        In the meantime, ping us at{' '}
                        <a href="mailto:crackwith.ai@gmail.com" className="text-primary underline">
                            crackwith.ai@gmail.com
                        </a>{' '}
                        or use the in-app AI tutor for any clarification.
                    </p>
                </div>
            )}
        </div>
    );
}
