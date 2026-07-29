'use client';

/**
 * BlogAnalytics.tsx — Per-post analytics overlay.
 *
 * Fires `blog_view`, scroll-depth buckets, read-complete (after the user
 * spends ≥60% of `readingTime` seconds on the page and ≥75% scroll), and
 * listens for the share/copy events the share row emits via the
 * data-blog-share attribute.
 *
 * Drop this component inside any BlogPostLayout — it auto-detects the
 * slug from `usePathname()` and reads the reading time from the
 * `data-reading-time` attribute on the article element if present.
 */

import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { analytics } from '@/lib/analytics';

interface Props {
    slug: string;
    category: string;
    readingTimeMinutes: number;
}

export default function BlogAnalytics({ slug, category, readingTimeMinutes }: Props) {
    const pathname = usePathname();
    const enterRef = useRef<number>(0);
    const lastScrollBucket = useRef<number>(0);
    const readCompleteFired = useRef<boolean>(false);

    /* ---- Mount: blog_view --------------------------------------------- */
    useEffect(() => {
        enterRef.current = Date.now();
        analytics.blogView(slug, category, readingTimeMinutes);
        // Attach scroll listener scoped to article element
        const article = document.getElementById('start-reading');
        const onScroll = () => {
            if (!article) return;
            const rect = article.getBoundingClientRect();
            const total = article.offsetHeight;
            const visibleBottom = Math.min(window.innerHeight - rect.top, total);
            const percent = total > 0 ? Math.max(0, (visibleBottom / total) * 100) : 0;
            const bucket =
                percent >= 100 ? 100 : percent >= 75 ? 75 : percent >= 50 ? 50 : percent >= 25 ? 25 : 0;
            if (bucket > lastScrollBucket.current) {
                lastScrollBucket.current = bucket;
                analytics.blogScroll(slug, Math.round(percent));
            }
            // Read-complete gate: 75% scroll + spent ≥60% of expected reading time
            if (!readCompleteFired.current && bucket >= 75) {
                const dwell = (Date.now() - enterRef.current) / 1000;
                if (dwell >= readingTimeMinutes * 60 * 0.6) {
                    readCompleteFired.current = true;
                    analytics.blogReadComplete(slug, Math.round(dwell));
                }
            }
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
        return () => {
            window.removeEventListener('scroll', onScroll);
        };
    }, [pathname, slug, category, readingTimeMinutes]);

    /* ---- Delegated share + copy + comment capture --------------------- */
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            const t = e.target as HTMLElement | null;
            if (!t) return;
            const btn = t.closest<HTMLElement>('[data-blog-share]');
            if (btn) {
                const network = btn.getAttribute('data-blog-share') ?? 'unknown';
                analytics.blogShare(slug, network);
                return;
            }
            const copyBtn = t.closest<HTMLElement>('[data-blog-copy]');
            if (copyBtn) {
                analytics.blogCopyLink(slug);
                return;
            }
            const newsletter = t.closest<HTMLElement>('[data-blog-newsletter]');
            if (newsletter) {
                analytics.blogNewsletter(slug);
                return;
            }
            const cta = t.closest<HTMLElement>('[data-blog-cta]');
            if (cta) {
                const name = cta.getAttribute('data-blog-cta') ?? 'unknown';
                const surface = cta.getAttribute('data-blog-surface') ?? 'unknown';
                analytics.blogCta(slug, name, surface);
                return;
            }
        };
        document.addEventListener('click', handler);
        return () => document.removeEventListener('click', handler);
    }, [slug]);

    /* ---- Comments widget visibility ----------------------------------- */
    useEffect(() => {
        const target = document.querySelector('[data-blog-comments]');
        if (!target) return;
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        analytics.blogComment(slug);
                        observer.disconnect();
                    }
                });
            },
            { threshold: 0.5 },
        );
        observer.observe(target);
        return () => observer.disconnect();
    }, [slug]);

    return null;
}